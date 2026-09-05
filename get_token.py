from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes=SCOPES)

credentials = flow.run_local_server(port=0)
print("Access token:", credentials.token)
print("Refresh token:", credentials.refresh_token)