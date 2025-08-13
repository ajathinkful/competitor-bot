import os
from google.oauth2 import service_account

class GoogleService:
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        # add any other scopes you need here
    ]

    SERVICE_ACCOUNT_FILE = r"C:\Users\Alex\Downloads\competitor-bot-standalone\river-interface-464015-q9-74db16f8f5ed.json"

    def __init__(self):
        self.creds = self._authorize()

    def _authorize(self):
        creds = service_account.Credentials.from_service_account_file(
            self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES
        )
        return creds
