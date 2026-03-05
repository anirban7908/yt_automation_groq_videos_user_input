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
        self.pixabay_key = os.getenv("PIXABAY_API_KEY")

    # ─────────────────────────────────────────────
    # NICHE → SOURCE ORDER MAP
    # ─────────────────────────────────────────────
    NICHE_SOURCE_ORDER = {
        "space": [
            "nasa",
            "pixabay_video",
            "pexels_video",
            "pixabay_image",
            "unsplash_image",
            "pexels_image",
        ],
        "tech_ai": [
            "pexels_video",
            "pixabay_video",
            "unsplash_image",
            "pexels_image",
            "pixabay_image",
        ],
        "psychology": [
            "pexels_video",
            "unsplash_image",
            "pexels_image",
            "pixabay_video",
            "pixabay_image",
        ],
        "geography": [
            "pixabay_video",
            "pexels_video",
            "unsplash_image",
            "pixabay_image",
            "pexels_image",
        ],
        "worldnews": [
            "pexels_video",
            "pixabay_video",
            "unsplash_image",
            "pexels_image",
            "pixabay_image",
        ],
        "home_decor": [
            "pexels_video",
            "unsplash_image",
            "pexels_image",
            "pixabay_video",
            "pixabay_image",
        ],
        "indian_history": [
            "pixabay_video",
            "unsplash_image",
            "pixabay_image",
            "pexels_video",
            "pexels_image",
        ],
        "science_facts": [
            "pixabay_video",
            "pexels_video",
            "nasa",
            "pixabay_image",
            "unsplash_image",
        ],
        "health_wellness": [
            "pexels_video",
            "pixabay_video",
            "unsplash_image",
            "pexels_image",
            "pixabay_image",
        ],
        "animals_nature": [
            "pixabay_video",
            "pexels_video",
            "unsplash_image",
            "pixabay_image",
            "pexels_image",
        ],
        "finance_economy": [
            "pexels_video",
            "pixabay_video",
            "unsplash_image",
            "pexels_image",
            "pixabay_image",
        ],
        "bizarre_facts": [
            "pixabay_video",
            "pexels_video",
            "unsplash_image",
            "pixabay_image",
            "pexels_image",
        ],
        "history_world": [
            "pixabay_video",
            "unsplash_image",
            "pixabay_image",
            "pexels_video",
            "pexels_image",
        ],
        "default": [
            "pexels_video",
            "pixabay_video",
            "unsplash_image",
            "pixabay_image",
            "pexels_image",
        ],
    }

    def is_valid_image(self, content):
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
            return True
        except:
            return False

    # ─────────────────────────────────────────────
    # VIDEO SOURCES
    # ─────────────────────────────────────────────

    def use_nasa_search(self, query, path):
        """NASA Image & Video Library — FREE, no API key required."""
        print(f"      🚀 NASA Library: hunting for '{query}'...")
        try:
            search_url = (
                f"https://images-api.nasa.gov/search"
                f"?q={requests.utils.quote(query)}"
                f"&media_type=video"
                f"&page_size=5"
            )
            res = requests.get(search_url, timeout=15)
            if res.status_code != 200:
                return False

            items = res.json().get("collection", {}).get("items", [])

            # Fall back to images if no videos found
            if not items:
                search_url = search_url.replace("media_type=video", "media_type=image")
                res = requests.get(search_url, timeout=15)
                items = res.json().get("collection", {}).get("items", [])
                if not items:
                    return False

            item = random.choice(items[:3])
            asset_url = item["href"]
            asset_res = requests.get(asset_url, timeout=10)
            if asset_res.status_code != 200:
                return False

            links = asset_res.json()
            mp4_links = [l for l in links if l.endswith(".mp4")]
            jpg_links = [l for l in links if l.endswith(".jpg") or l.endswith(".jpeg")]

            if mp4_links:
                content = requests.get(mp4_links[0], timeout=30).content
                save_path = path.replace(".jpg", ".mp4")
                with open(save_path, "wb") as f:
                    f.write(content)
                print("      ✅ NASA Video Secured.")
                return save_path

            elif jpg_links:
                content = requests.get(jpg_links[0], timeout=15).content
                if self.is_valid_image(content):
                    save_path = (
                        path if path.endswith(".jpg") else path.replace(".mp4", ".jpg")
                    )
                    with open(save_path, "wb") as f:
                        f.write(content)
                    print("      ✅ NASA Image Secured.")
                    return save_path

        except Exception as e:
            print(f"      ❌ NASA Search Failed: {e}")

        return False

    def use_pexels_video_search(self, query, path):
        """Search Pexels for portrait MP4 videos."""
        if not self.pexels_key:
            return False
        print(f"      🎥 Pexels Video: hunting for '{query}'...")
        try:
            url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation=portrait"
            res = requests.get(
                url, headers={"Authorization": self.pexels_key}, timeout=30
            )
            if res.status_code == 200 and res.json().get("videos"):
                for video in res.json()["videos"][:3]:
                    mp4_files = [
                        v for v in video["video_files"] if v["file_type"] == "video/mp4"
                    ]
                    if mp4_files:
                        mp4_files = sorted(
                            mp4_files,
                            key=lambda x: x.get("width", 0) * x.get("height", 0),
                            reverse=True,
                        )
                        content = requests.get(mp4_files[0]["link"], timeout=20).content
                        with open(path, "wb") as f:
                            f.write(content)
                        print("      ✅ Pexels Video Secured.")
                        return path
        except Exception as e:
            print(f"      ❌ Pexels Video Failed: {e}")
        return False

    def use_pixabay_video_search(self, query, path):
        """Search Pixabay for MP4 videos."""
        if not self.pixabay_key:
            return False
        print(f"      🎥 Pixabay Video: hunting for '{query}'...")
        try:
            url = (
                f"https://pixabay.com/api/videos/"
                f"?key={self.pixabay_key}"
                f"&q={requests.utils.quote(query)}"
                f"&video_type=film&per_page=5"
            )
            res = requests.get(url, timeout=30)
            if res.status_code == 200:
                hits = res.json().get("hits", [])
                if hits:
                    video = random.choice(hits[:3])
                    videos = video.get("videos", {})
                    for quality in ["large", "medium", "small", "tiny"]:
                        if quality in videos and videos[quality].get("url"):
                            content = requests.get(
                                videos[quality]["url"], timeout=20
                            ).content
                            with open(path, "wb") as f:
                                f.write(content)
                            print(f"      ✅ Pixabay Video Secured ({quality}).")
                            return path
        except Exception as e:
            print(f"      ❌ Pixabay Video Failed: {e}")
        return False

    # ─────────────────────────────────────────────
    # IMAGE SOURCES
    # ─────────────────────────────────────────────

    def use_unsplash_image_search(self, query, path):
        """Search Unsplash for images."""
        if not self.unsplash_key:
            return False
        print(f"      🖼️ Unsplash Image: hunting for '{query}'...")
        try:
            url = f"https://api.unsplash.com/search/photos?query={query}&per_page=5&client_id={self.unsplash_key}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200 and res.json()["results"]:
                img_url = random.choice(res.json()["results"][:3])["urls"]["regular"]
                content = requests.get(img_url).content
                if self.is_valid_image(content):
                    with open(path, "wb") as f:
                        f.write(content)
                    print("      ✅ Unsplash Image Secured.")
                    return path
        except Exception as e:
            print(f"      ❌ Unsplash Image Failed: {e}")
        return False

    def use_pixabay_image_search(self, query, path):
        """Search Pixabay for images."""
        if not self.pixabay_key:
            return False
        print(f"      🖼️ Pixabay Image: hunting for '{query}'...")
        try:
            url = (
                f"https://pixabay.com/api/"
                f"?key={self.pixabay_key}"
                f"&q={requests.utils.quote(query)}"
                f"&image_type=photo&orientation=vertical"
                f"&per_page=5&safesearch=true"
            )
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                hits = res.json().get("hits", [])
                if hits:
                    hit = random.choice(hits[:3])
                    img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                    if img_url:
                        content = requests.get(img_url, timeout=10).content
                        if self.is_valid_image(content):
                            with open(path, "wb") as f:
                                f.write(content)
                            print("      ✅ Pixabay Image Secured.")
                            return path
        except Exception as e:
            print(f"      ❌ Pixabay Image Failed: {e}")
        return False

    def use_pexels_image_search(self, query, path):
        """Search Pexels for images."""
        if not self.pexels_key:
            return False
        print(f"      🖼️ Pexels Image: hunting for '{query}'...")
        try:
            url = f"https://api.pexels.com/v1/search?query={query}&per_page=5"
            res = requests.get(
                url, headers={"Authorization": self.pexels_key}, timeout=10
            )
            if res.status_code == 200 and res.json()["photos"]:
                img_url = random.choice(res.json()["photos"][:3])["src"]["large2x"]
                content = requests.get(img_url).content
                if self.is_valid_image(content):
                    with open(path, "wb") as f:
                        f.write(content)
                    print("      ✅ Pexels Image Secured.")
                    return path
        except Exception as e:
            print(f"      ❌ Pexels Image Failed: {e}")
        return False

    def search_google_images(self, query, path):
        """Scrape Google Images as hero image for Scene 0."""
        print(f"      🌍 Google Image: hunting for '{query}'...")
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
                            print("      ✅ Google Image Secured.")
                            return path
                    except:
                        continue
        except Exception as e:
            print(f"      ❌ Google Image Failed: {e}")
        return False

    # ─────────────────────────────────────────────
    # SOURCE DISPATCHER
    # ─────────────────────────────────────────────

    def _try_source(self, source_name, query, base_filename, folder):
        """Calls the right API based on source_name. Returns saved path or False."""
        if source_name == "nasa":
            path = os.path.join(folder, base_filename + ".mp4")
            return self.use_nasa_search(query, path)
        elif source_name == "pexels_video":
            path = os.path.join(folder, base_filename + ".mp4")
            return self.use_pexels_video_search(query, path)
        elif source_name == "pixabay_video":
            path = os.path.join(folder, base_filename + ".mp4")
            return self.use_pixabay_video_search(query, path)
        elif source_name == "unsplash_image":
            path = os.path.join(folder, base_filename + ".jpg")
            return self.use_unsplash_image_search(query, path)
        elif source_name == "pixabay_image":
            path = os.path.join(folder, base_filename + ".jpg")
            return self.use_pixabay_image_search(query, path)
        elif source_name == "pexels_image":
            path = os.path.join(folder, base_filename + ".jpg")
            return self.use_pexels_image_search(query, path)
        return False

    # ─────────────────────────────────────────────
    # MAIN DOWNLOAD ORCHESTRATOR
    # ─────────────────────────────────────────────

    def download_visuals(self):
        task = self.db.collection.find_one({"status": "voiced"})
        if not task:
            return

        scenes = task.get("script_data", [])
        folder = task["folder_path"]
        niche = task.get("niche", "default").lower()

        source_order = self.NICHE_SOURCE_ORDER.get(
            niche, self.NICHE_SOURCE_ORDER["default"]
        )
        print(f"🎬 Visual Scout: niche='{niche}' | source order: {source_order}")
        print(f"🎬 Processing {len(scenes)} scenes...")

        updated_scenes = []

        for i, scene in enumerate(scenes):
            video_title_fallback = task.get("title", "Breaking News")
            keywords = scene.get("keywords", [video_title_fallback])
            count = scene.get("image_count", 1)
            visual_paths = []

            for j in range(count):
                kw = keywords[j % len(keywords)]
                base_filename = f"scene_{i}_visual_{j}"
                print(f"\n   🖼️  Scene {i+1}, Visual {j+1}/{count} → '{kw}'")
                time.sleep(2)
                saved_path = None

                # ── STEP 1: Hero image for Scene 0 Visual 0 ──
                if i == 0 and j == 0:
                    path_jpg = os.path.join(folder, base_filename + ".jpg")
                    result = self.search_google_images(kw, path_jpg)
                    if result:
                        saved_path = result

                # ── STEP 2+: Try sources in niche-specific order ──
                if not saved_path:
                    for source_name in source_order:
                        result = self._try_source(
                            source_name, kw, base_filename, folder
                        )
                        if result:
                            saved_path = result
                            break
                        time.sleep(1)

                # ── FALLBACK: Retry with other keywords from same scene ──
                if not saved_path:
                    for fallback_kw in keywords:
                        if fallback_kw != kw:
                            print(
                                f"      ⚠️ '{kw}' failed everywhere. Retrying with '{fallback_kw}'..."
                            )
                            for source_name in source_order[:3]:
                                result = self._try_source(
                                    source_name, fallback_kw, base_filename, folder
                                )
                                if result:
                                    saved_path = result
                                    break
                            if saved_path:
                                break

                # ── LAST RESORT: Black placeholder ──
                if not saved_path:
                    print(f"      ❌ All sources failed. Using placeholder.")
                    path_jpg = os.path.join(folder, base_filename + ".jpg")
                    Image.new("RGB", (1080, 1920), (10, 10, 10)).save(path_jpg)
                    saved_path = path_jpg

                visual_paths.append(saved_path)

            scene["image_paths"] = visual_paths
            updated_scenes.append(scene)
            time.sleep(1)

        self.db.collection.update_one(
            {"_id": task["_id"]},
            {"$set": {"script_data": updated_scenes, "status": "ready_to_assemble"}},
        )
        print("\n✅ Visuals Secured.")
