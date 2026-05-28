import os
import json
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from logger import setup_logger

logger = setup_logger()

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_FILE = "tokens/youtube_credentials.json"
TOKEN_FILE = "tokens/youtube_token.json"


def authenticate_youtube():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("YouTube token refreshed")
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE} — run: python main.py --auth"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("YouTube authentication completed")

        os.makedirs("tokens", exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def get_youtube_client():
    creds = authenticate_youtube()
    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(video_path, script, topic, config):
    youtube = get_youtube_client()

    title = script.get("title", topic["title"])
    if len(title) > 100:
        title = title[:97] + "..."

    description = f"{script.get('description', topic['core_message'])}\n\n{script.get('hashtags', '#motivation #shorts')}"
    tags = config["youtube"]["tags"] + topic.get("keywords", [])

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],
            "categoryId": config["youtube"]["category_id"],
        },
        "status": {
            "privacyStatus": config["youtube"]["privacy"],
            "madeForKids": config["youtube"]["made_for_kids"],
        },
    }

    media = MediaFileUpload(video_path, chunksize=5 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    logger.info(f"Uploading: {title}")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    url = f"https://www.youtube.com/shorts/{video_id}"
    logger.info(f"Uploaded successfully: {url}")
    return video_id, url
