import json
import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service():
    raw = os.environ["GDRIVE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

def upload_file(file_path: str, folder_id: str):
    service = get_drive_service()
    path = Path(file_path)

    metadata = {
        "name": path.name,
        "parents": [folder_id],
    }

    media = MediaFileUpload(str(path), resumable=True)
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id,name,webViewLink")
        .execute()
    )
    return created

def upload_text_content(filename: str, content: str, folder_id: str):
    temp_dir = Path("data/tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / filename
    temp_file.write_text(content, encoding="utf-8")
    return upload_file(str(temp_file), folder_id)