from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = r"C:\Users\Alex\Downloads\competitor-bot-standalone\river-interface-464015-q9-74db16f8f5ed.json"

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_ID = "1RseTzj2Ve7J90TKB06lCEY2-xEJtQx3X"

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

drive_service = build("drive", "v3", credentials=creds)

results = drive_service.files().list(
    q=f"'{FOLDER_ID}' in parents",
    supportsAllDrives=True,
    includeItemsFromAllDrives=True,
    corpora="allDrives",
    fields="files(id, name)"
).execute()

files = results.get("files", [])
print(f"Found {len(files)} files:")
for f in files:
    print(f"- {f['name']} ({f['id']})")
