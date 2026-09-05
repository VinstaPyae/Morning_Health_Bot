import os
import requests
from datetime import datetime, timedelta, timezone

SG_OFFSET = timedelta(hours=8)

def get_access_token():
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data = {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]

def fetch_steps_yesterday(access_token):
    now_local = datetime.now(timezone.utc) + SG_OFFSET
    today = now_local.date()
    yesterday = today - timedelta(days=1)

    def civil_date(d):
        return {"date": {"year": d.year, "month": d.month, "day": d.day}}

    body = {
        "range": {
            "start": civil_date(yesterday),
            "end": civil_date(today),
        }
    }

    response = requests.post(
        "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp",
        headers={"Authorization": f"Bearer {access_token}"},
        json=body,
    )
    response.raise_for_status()
    return response.json()

def fetch_sleep_last_night(access_token):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    filter_str = (
        f'sleep.interval.end_time >= "{start}" '
        f'AND sleep.interval.end_time < "{end}"'
    )

    response = requests.get(
        "https://health.googleapis.com/v4/users/me/dataTypes/sleep/dataPoints",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"filter": filter_str},
    )
    response.raise_for_status()
    return response.json()

# if __name__ == "__main__":
#     token = get_access_token()

#     steps = fetch_steps_yesterday(token)
#     print("=== STEPS ===")
#     print(steps)

#     sleep = fetch_sleep_last_night(token)
#     print("=== SLEEP ===")
#     print(sleep)

def summarize_health_data(steps_data, sleep_data):
    total_steps = 0
    for point in steps_data.get("rollupDataPoints", []):
        total_steps += int(point.get("steps", {}).get("countSum", 0))

    sleep_points = sleep_data.get("dataPoints", [])
    if not sleep_points:
        return total_steps, "No sleep data recorded."

    sleep = sleep_points[0]["sleep"]

    interval = sleep.get("interval", {})
    start_utc = interval.get("startTime")
    end_utc = interval.get("endTime")

    def to_local_time_str(utc_str):
        dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ")
        dt_local = dt.replace(tzinfo=timezone.utc) + SG_OFFSET
        return dt_local.strftime("%I:%M %p").lstrip("0")

    bedtime = to_local_time_str(start_utc) if start_utc else "unknown"
    wake_time = to_local_time_str(end_utc) if end_utc else "unknown"

    summary = sleep.get("summary", {})

    minutes_in_period = int(summary.get("minutesInSleepPeriod", 0))
    minutes_asleep = int(summary.get("minutesAsleep", 0))
    minutes_awake = int(summary.get("minutesAwake", 0))
    minutes_to_fall_asleep = int(summary.get("minutesToFallAsleep", 0))

    # Sleep efficiency: percentage of time in bed actually spent asleep
    efficiency = round((minutes_asleep / minutes_in_period) * 100, 1) if minutes_in_period else 0

    # Break down time spent in each sleep stage
    stage_minutes = {}
    for stage in summary.get("stagesSummary", []):
        stage_minutes[stage["type"]] = int(stage["minutes"])

    deep = stage_minutes.get("DEEP", 0)
    rem = stage_minutes.get("REM", 0)
    light = stage_minutes.get("LIGHT", 0)
    deep_pct = round((deep / minutes_asleep) * 100, 1) if minutes_asleep else 0
    rem_pct = round((rem / minutes_asleep) * 100, 1) if minutes_asleep else 0
    light_pct = round((light / minutes_asleep) * 100, 1) if minutes_asleep else 0
    num_awakenings = len(sleep.get("shortAwakenings", []))

    sleep_summary = (
        f"Went to bed at {bedtime}, woke at {wake_time}. "
        f"{minutes_asleep // 60}h {minutes_asleep % 60}m asleep "
        f"(efficiency {efficiency}%). "
        f"Deep: {deep}m ({deep_pct}%), REM: {rem}m ({rem_pct}%), Light: {light}m ({light_pct}%). "
        f"Took {minutes_to_fall_asleep}m to fall asleep, "
        f"woke briefly {num_awakenings} times."
    )

    return total_steps, sleep_summary

def generate_morning_message(total_steps, sleep_summary):
    prompt = (
        f"You are analyzing someone's sleep and activity data as a knowledgeable, "
        f"straight-talking health-aware friend — not a cheerleader.\n\n"
        f"Data:\n"
        f"Steps yesterday: {total_steps}\n"
        f"Sleep: {sleep_summary}\n\n"
        f"For reference, healthy adult sleep typically has roughly "
        f"13-23% deep sleep, 20-25% REM sleep, and sleep efficiency above 85%. "
        f"Frequent brief awakenings (10+) can indicate a restless night even "
        f"when total sleep time and efficiency look fine.\n\n"
        f"Write a short morning message (3-4 sentences) that: "
        f"(1) makes ONE specific, genuinely analytical observation comparing "
        f"their actual numbers to these healthy ranges — not generic praise, "
        f"(2) if something stands out as unusual or worth watching (e.g. high "
        f"awakening count despite good efficiency), name it plainly, "
        f"(3) ends with one concrete, actionable suggestion for tonight or today, "
        f"not just encouragement. "
        f"Keep it warm but substantive — like a friend who actually knows sleep "
        f"science, not empty positivity. No bullet points or headers."
    )

    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def send_telegram_message(text):
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
    )
    response.raise_for_status()
    return response.json()

# if __name__ == "__main__":
#     token = get_access_token()
#     steps_data = fetch_steps_yesterday(token)
#     sleep_data = fetch_sleep_last_night(token)

#     total_steps, sleep_summary = summarize_health_data(steps_data, sleep_data)
#     print("Steps:", total_steps)
#     print("Sleep summary:", sleep_summary)

#     message = generate_morning_message(total_steps, sleep_summary)
#     print("=== AI MESSAGE ===")
#     print(message)


# if __name__ == "__main__":
#     token = get_access_token()
#     steps_data = fetch_steps_yesterday(token)
#     sleep_data = fetch_sleep_last_night(token)

#     total_steps, sleep_summary = summarize_health_data(steps_data, sleep_data)
#     print("Steps:", total_steps)
#     print("Sleep summary:", sleep_summary)

#     message = generate_morning_message(total_steps, sleep_summary)
#     print("=== AI MESSAGE ===")
#     print(message)

if __name__ == "__main__":
    token = get_access_token()
    steps_data = fetch_steps_yesterday(token)
    sleep_data = fetch_sleep_last_night(token)

    total_steps, sleep_summary = summarize_health_data(steps_data, sleep_data)
    print("Steps:", total_steps)
    print("Sleep summary:", sleep_summary)

    message = generate_morning_message(total_steps, sleep_summary)
    print("=== AI MESSAGE ===")
    print(message)

    send_telegram_message(message)
    print("Sent to Telegram!")