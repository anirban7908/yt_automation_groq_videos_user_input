import os
import pickle
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from core.db_manager import DBManager


class YouTubeUploader:
    def __init__(self):
        self.db = DBManager()
        self.SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.client_secrets_file = "client_secrets.json"
        self.token_file = "token.pickle"
        self.youtube = self.get_authenticated_service()

        # 🟢 NEW: Map your 'niche' to YouTube Category IDs
        # Reference: https://gist.github.com/dgp/1b24bf2961521bd75d6c
        self.CATEGORY_MAP = {
            "motivation": "22",  # People & Blogs (Best for lifestyle/motivation)
            "tech": "28",  # Science & Technology
            "space": "28",  # Science & Technology
            "nature": "15",  # Pets & Animals (Best for wildlife/nature)
            "history": "27",  # Education (Best for history/facts)
            "general": "24",  # Entertainment (Fallback)
        }

    def get_authenticated_service(self):
        creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_file, "wb") as token:
                pickle.dump(creds, token)

        return build(self.api_service_name, self.api_version, credentials=creds)

    def upload_video(self):
        # Fetch the most recent packaged task
        task = self.db.collection.find_one(
            {"status": "completed_packaged"}, sort=[("created_at", -1)]
        )
        if not task:
            print("📭 No packaged videos found to upload.")
            return

        print(f"🚀 Starting Upload for: {task['title']}")

        video_path = task.get("final_video_path")
        if not os.path.exists(video_path):
            print("❌ Error: Video file not found on disk.")
            return

        # 🟢 DYNAMIC CATEGORY LOGIC
        niche = task.get("niche", "general").lower()
        category_id = self.CATEGORY_MAP.get(niche, "22")

        print(f"   🏷️ Niche: {niche} -> YouTube Category ID: {category_id}")

        # 🟢 SANITIZE DESCRIPTION
        raw_description = f"{task['ai_description'][:4000]}\n\n#Shorts\n\nSource: {task.get('source_url', '')}"
        clean_description = raw_description.replace("<", "").replace(">", "")

        request_body = {
            "snippet": {
                "categoryId": category_id,
                "title": task["title"][:100],
                "description": clean_description,
                "tags": task.get("tags", "").split(",") + ["Shorts", niche],
            },
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
        }

        # 🟢 THE FIX: Use 4MB Chunks (Robust against connection drops)
        CHUNK_SIZE = 4 * 1024 * 1024
        media = MediaFileUpload(video_path, chunksize=CHUNK_SIZE, resumable=True)

        request = self.youtube.videos().insert(
            part="snippet,status", body=request_body, media_body=media
        )

        print("   ⏳ Uploading...")
        response = None
        retries = 0

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    print(f"      Uploaded {int(status.progress() * 100)}%")
            except Exception as e:
                # 🟢 RETRY LOGIC for Connection Resets
                print(f"      ⚠️ Connection interrupted ({e}). Retrying in 5s...")
                retries += 1
                time.sleep(5)
                if retries > 10:
                    print("      ❌ Too many failures. Aborting.")
                    return

        if response and "id" in response:
            video_id = response["id"]
            print(f"   ✅ Upload Successful! Video ID: {video_id}")

            self.db.collection.update_one(
                {"_id": task["_id"]},
                {
                    "$set": {
                        "status": "uploaded",
                        "youtube_id": video_id,
                        "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                },
            )
        else:
            print(f"   ❌ Upload failed: {response}")


if __name__ == "__main__":
    uploader = YouTubeUploader()
    uploader.upload_video()
