import os
import time
import requests
import random
import re
from core.db_manager import DBManager
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv()


class VisualScout:
    def __init__(self):
        self.db = DBManager()
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
        self.pexels_key = os.getenv("PEXELS_API_KEY")

    def is_valid_image(self, content):
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
            return True
        except:
            return False

    # 🟢 NEW: Fetch Actual B-Roll Video from Pexels with Aesthetic Modifier
    def use_pexels_video_search(self, query, path):
        if not self.pexels_key:
            return False

        print(f"      🎥 Pexels Video Search: hunting for '{query}'...")
        try:
            # We append 'aesthetic' to force higher-quality, cinematic results
            safe_query = f"{query} aesthetic"
            url = f"https://api.pexels.com/videos/search?query={safe_query}&per_page=5&orientation=portrait"
            res = requests.get(
                url, headers={"Authorization": self.pexels_key}, timeout=10
            )

            if res.status_code == 200 and res.json().get("videos"):
                videos = res.json()["videos"]
                if videos:
                    video_files = videos[0]["video_files"]
                    mp4_files = [
                        v for v in video_files if v["file_type"] == "video/mp4"
                    ]

                    if mp4_files:
                        mp4_files = sorted(
                            mp4_files,
                            key=lambda x: x.get("width", 0) * x.get("height", 0),
                            reverse=True,
                        )
                        video_url = mp4_files[0]["link"]

                        content = requests.get(video_url, timeout=20).content
                        with open(path, "wb") as f:
                            f.write(content)
                        print("      ✅ Pexels Video Secured.")
                        return True
        except Exception as e:
            print(f"      ❌ Pexels Video Search Failed: {e}")

        return False

    def use_stock_search(self, query, path):
        # 1. Unsplash (Fallback for images)
        if self.unsplash_key:
            try:
                url = f"https://api.unsplash.com/search/photos?query={query}&per_page=3&client_id={self.unsplash_key}"
                res = requests.get(url, timeout=5)
                if res.status_code == 200 and res.json()["results"]:
                    img_url = random.choice(res.json()["results"])["urls"]["regular"]
                    content = requests.get(img_url).content
                    if self.is_valid_image(content):
                        with open(path, "wb") as f:
                            f.write(content)
                        return True
            except:
                pass

        # 2. Pexels Image (Fallback)
        if self.pexels_key:
            try:
                url = f"https://api.pexels.com/v1/search?query={query}&per_page=3"
                res = requests.get(
                    url, headers={"Authorization": self.pexels_key}, timeout=5
                )
                if res.status_code == 200 and res.json()["photos"]:
                    img_url = random.choice(res.json()["photos"])["src"]["large2x"]
                    content = requests.get(img_url).content
                    if self.is_valid_image(content):
                        with open(path, "wb") as f:
                            f.write(content)
                        return True
            except:
                pass
        return False

    def search_google_images(self, query, path):
        print(f"      🌍 Web Search (Image): hunting for '{query}'...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        }

        try:
            url = f"https://www.google.com/search?q={query}&tbm=isch&udm=2"
            res = requests.get(url, headers=headers, timeout=10)
            matches = re.findall(r'"(https?://[^"]+?\.(?:jpg|jpeg|png))"', res.text)

            if matches:
                for img_url in matches[:3]:
                    try:
                        img_url = img_url.encode().decode("unicode_escape")
                        img_data = requests.get(
                            img_url, headers=headers, timeout=5
                        ).content
                        if self.is_valid_image(img_data):
                            with open(path, "wb") as f:
                                f.write(img_data)
                            print("      ✅ Web Image Secured.")
                            return True
                    except:
                        continue
        except Exception as e:
            print(f"      ❌ Web Search Failed: {e}")

        return False

    def download_visuals(self):
        task = self.db.collection.find_one({"status": "voiced"})
        if not task:
            return

        scenes = task.get("script_data", [])
        folder = task["folder_path"]
        print(f"🎬 Visual Scout: Processing {len(scenes)} scenes...")

        updated_scenes = []

        for i, scene in enumerate(scenes):
            # 🟢 THE FIX: If the AI drops the keywords, fallback to the video's actual title!
            video_title_fallback = task.get("title", "Breaking News")
            keywords = scene.get("keywords", [video_title_fallback])
            count = scene.get("image_count", 1)

            visual_paths = []

            for j in range(count):
                kw = keywords[j % len(keywords)]
                base_filename = f"scene_{i}_visual_{j}"
                print(f"   🖼️ Scene {i+1} (Visual {j+1}/{count}): Search '{kw}'")

                saved_path = None

                # 1. Hero Image Force Web Search (Scene 0, Image 0)
                if i == 0 and j == 0:
                    path_jpg = os.path.join(folder, base_filename + ".jpg")
                    if self.search_google_images(kw, path_jpg):
                        saved_path = path_jpg

                # 2. Try Pexels Video (.mp4)
                if not saved_path:
                    path_mp4 = os.path.join(folder, base_filename + ".mp4")
                    if self.use_pexels_video_search(kw, path_mp4):
                        saved_path = path_mp4

                # 3. Fallback to Stock Images (.jpg)
                if not saved_path:
                    path_jpg = os.path.join(folder, base_filename + ".jpg")
                    if self.use_stock_search(kw, path_jpg):
                        saved_path = path_jpg

                # 4. Fallback to other keywords if specific one failed entirely
                if not saved_path:
                    for fallback_kw in keywords:
                        if fallback_kw != kw:
                            print(
                                f"      ⚠️ '{kw}' failed. Retrying video with '{fallback_kw}'..."
                            )
                            path_mp4 = os.path.join(folder, base_filename + ".mp4")
                            if self.use_pexels_video_search(fallback_kw, path_mp4):
                                saved_path = path_mp4
                                break

                # 5. Final Fallback: Placeholder Image
                if not saved_path:
                    print(f"      ❌ All searches failed. Using placeholder.")
                    path_jpg = os.path.join(folder, base_filename + ".jpg")
                    Image.new("RGB", (1080, 1920), (10, 10, 10)).save(path_jpg)
                    saved_path = path_jpg

                visual_paths.append(saved_path)

            # Updated key from 'image_paths' to 'image_paths' (kept same for backward compatibility with db)
            scene["image_paths"] = visual_paths
            updated_scenes.append(scene)
            time.sleep(1)

        self.db.collection.update_one(
            {"_id": task["_id"]},
            {"$set": {"script_data": updated_scenes, "status": "ready_to_assemble"}},
        )
        print("✅ Visuals Secured.")
