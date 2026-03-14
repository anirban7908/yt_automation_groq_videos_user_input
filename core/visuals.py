import os
import time
import requests
import random
import re
import json
from core.db_manager import DBManager
from dotenv import load_dotenv
from PIL import Image
import io
from groq import Groq

load_dotenv()


class VisualScout:
    def __init__(self):
        self.db = DBManager()
        self.unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
        self.pexels_key = os.getenv("PEXELS_API_KEY")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY")
        self.ai_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.ai_model = "llama-3.3-70b-versatile"

        # Track downloaded clip IDs to prevent the same clip appearing twice
        self._used_pexels_ids = set()
        self._used_pixabay_ids = set()
        self._used_nasa_ids = set()

    # ─────────────────────────────────────────────
    # NASA KEYWORD TRIGGER LIST
    # Any keyword containing one of these words
    # (case-insensitive, partial match) gets routed
    # to NASA *first* before falling back to Pexels.
    # ─────────────────────────────────────────────
    NASA_TRIGGERS = {
        "asteroid",
        "meteor",
        "meteorite",
        "comet",
        "nebula",
        "galaxy",
        "cosmos",
        "cosmic",
        "rocket",
        "spacecraft",
        "space shuttle",
        "shuttle",
        "iss",
        "space station",
        "mars",
        "moon",
        "lunar",
        "planet",
        "planetary",
        "saturn",
        "jupiter",
        "venus",
        "mercury",
        "uranus",
        "neptune",
        "solar flare",
        "solar storm",
        "sun corona",
        "corona",
        "sunspot",
        "black hole",
        "neutron star",
        "pulsar",
        "quasar",
        "dark matter",
        "hubble",
        "james webb",
        "webb telescope",
        "milky way",
        "orbit",
        "orbital",
        "astronaut",
        "spacewalk",
        "earth from space",
        "aurora borealis",
        "aurora australis",
        "northern lights",
        "supernova",
        "exoplanet",
        "deep space",
        "space debris",
        "launch pad",
        "launch",
        "capsule",
        "lander",
        "rover",
        "curiosity",
        "perseverance",
        "telescope",
        "observatory",
        "star cluster",
        "globular cluster",
        "interstellar",
        "galactic",
        "stellar",
        "dwarf star",
        "red giant",
        "space exploration",
        "nasa",
        "esa",
        "spacex",
        "space",
    }

    # ─────────────────────────────────────────────
    # NICHE → FALLBACK SOURCE ORDER
    # Used ONLY when keyword-level routing doesn't
    # match a specific source. This is the tiebreaker.
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

    # ─────────────────────────────────────────────
    # KEYWORD → SOURCE ROUTER
    # ─────────────────────────────────────────────

    def _route_source_order(self, keyword, niche):
        """
        Returns the ordered list of sources to try for this specific keyword.

        Logic:
          1. Check if the keyword contains any NASA trigger word
             → if yes, put "nasa" at the front of the list
          2. Otherwise fall back to the niche-level source order

        This means "asteroid" in a history_world video still hits NASA first,
        and "Lakota village" in a space video still hits Pexels first.
        """
        kw_lower = keyword.lower()

        # Check for NASA triggers (any substring match)
        is_nasa_keyword = any(trigger in kw_lower for trigger in self.NASA_TRIGGERS)

        if is_nasa_keyword:
            # NASA first, then standard video sources as fallback
            print(f"      🛰️  NASA route detected for: '{keyword}'")
            return [
                "nasa",
                "pixabay_video",
                "pexels_video",
                "pixabay_image",
                "unsplash_image",
                "pexels_image",
            ]

        # Standard niche-based order
        return self.NICHE_SOURCE_ORDER.get(niche, self.NICHE_SOURCE_ORDER["default"])

    # ─────────────────────────────────────────────
    # AI CANDIDATE SELECTOR
    # ─────────────────────────────────────────────

    def is_valid_image(self, content):
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
            return True
        except:
            return False

    def _ai_choose_best_visual(self, keyword, candidates, source_type):
        """
        Asks Groq (Llama 3.3) to pick the most relevant visual from a list of candidates.
        Returns the index of the chosen candidate, or 0 if the AI fails.
        """
        if not candidates or len(candidates) <= 1:
            return 0

        options_for_ai = []
        for i, c in enumerate(candidates):
            options_for_ai.append(
                {
                    "index": i,
                    "description": c.get("description", "No description available"),
                }
            )

        prompt = f"""
        TASK: You are an expert video editor. You must choose the best stock {source_type} for a scene about: "{keyword}".
        
        AVAILABLE OPTIONS:
        {json.dumps(options_for_ai, indent=2)}
        
        INSTRUCTIONS:
        1. Read the descriptions of the available {source_type}s.
        2. Pick the ONE index that best matches the physical subject "{keyword}".
        3. Output ONLY a valid JSON object containing the chosen 'index'.
        
        EXAMPLE OUTPUT:
        {{"index": 2}}
        """

        print(f"      🧠 AI reviewing {len(candidates)} {source_type} candidates...")
        try:
            chat_completion = self.ai_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You output ONLY valid JSON dictionaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.ai_model,
                response_format={"type": "json_object"},
            )

            result = json.loads(chat_completion.choices[0].message.content)
            chosen_index = int(result.get("index", 0))

            if 0 <= chosen_index < len(candidates):
                print(f"      🎯 AI selected option {chosen_index}.")
                return chosen_index

        except Exception as e:
            print(f"      ⚠️ AI Selection Failed ({e}). Falling back to option 0.")

        return 0

    # ─────────────────────────────────────────────
    # VIDEO SOURCES
    # ─────────────────────────────────────────────

    def use_nasa_search(self, query, path):
        """
        NASA Image & Video Library — FREE, no API key required.
        Searches for videos first, falls back to images.
        Uses AI to select the most relevant result.
        Skips already-used NASA asset IDs to prevent duplicate clips.
        """
        print(f"      🚀 NASA Library: hunting for '{query}'...")
        try:
            search_url = (
                f"https://images-api.nasa.gov/search"
                f"?q={requests.utils.quote(query)}"
                f"&media_type=video"
                f"&page_size=10"
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

            # Filter out already-used NASA assets
            fresh_items = [
                item
                for item in items
                if item.get("data", [{}])[0].get("nasa_id", "")
                not in self._used_nasa_ids
            ]
            if not fresh_items:
                print(f"      ⚠️ All NASA results already used. Skipping.")
                return False

            # Build candidates for AI
            candidates = []
            for item in fresh_items[:5]:
                data = item.get("data", [{}])[0]
                candidates.append(
                    {
                        "description": f"Title: {data.get('title', '')}. Desc: {data.get('description', '')}",
                        "raw": item,
                    }
                )

            # Let AI choose
            chosen_index = self._ai_choose_best_visual(query, candidates, "NASA asset")
            item = candidates[chosen_index]["raw"]
            nasa_id = item.get("data", [{}])[0].get("nasa_id", "")

            asset_url = item["href"]
            asset_res = requests.get(asset_url, timeout=10)
            if asset_res.status_code != 200:
                return False

            links = asset_res.json()
            mp4_links = [l for l in links if l.endswith(".mp4")]
            jpg_links = [l for l in links if l.endswith(".jpg") or l.endswith(".jpeg")]

            if mp4_links:
                content = requests.get(mp4_links[0], timeout=60).content
                save_path = path.replace(".jpg", ".mp4")
                with open(save_path, "wb") as f:
                    f.write(content)
                self._used_nasa_ids.add(nasa_id)
                print(f"      ✅ NASA Video Secured. [ID: {nasa_id}]")
                return save_path

            elif jpg_links:
                content = requests.get(jpg_links[0], timeout=15).content
                if self.is_valid_image(content):
                    save_path = (
                        path if path.endswith(".jpg") else path.replace(".mp4", ".jpg")
                    )
                    with open(save_path, "wb") as f:
                        f.write(content)
                    self._used_nasa_ids.add(nasa_id)
                    print(f"      ✅ NASA Image Secured. [ID: {nasa_id}]")
                    return save_path

        except Exception as e:
            print(f"      ❌ NASA Search Failed: {e}")

        return False

    def use_pexels_video_search(self, query, path):
        """
        Search Pexels for portrait MP4 videos.
        Uses AI to select the best match.
        Skips already-used video IDs to prevent duplicate clips.
        """
        if not self.pexels_key:
            return False
        print(f"      🎥 Pexels Video: hunting for '{query}'...")
        try:
            url = (
                f"https://api.pexels.com/videos/search"
                f"?query={requests.utils.quote(query)}"
                f"&per_page=15"
                f"&orientation=portrait"
            )
            res = requests.get(
                url, headers={"Authorization": self.pexels_key}, timeout=30
            )

            videos = res.json().get("videos", [])
            if res.status_code == 200 and videos:
                # Filter out already-used video IDs
                fresh_videos = [
                    v for v in videos if v.get("id") not in self._used_pexels_ids
                ]
                if not fresh_videos:
                    print(f"      ⚠️ All Pexels results for '{query}' already used.")
                    return False

                # Build candidates for AI (max 5 fresh ones)
                candidates = []
                for v in fresh_videos[:5]:
                    candidates.append(
                        {
                            "description": v.get("url", "")
                            .split("/")[-2]
                            .replace("-", " "),
                            "raw": v,
                        }
                    )

                # Let AI choose
                chosen_index = self._ai_choose_best_visual(query, candidates, "video")
                chosen_video = candidates[chosen_index]["raw"]

                mp4_files = [
                    v
                    for v in chosen_video["video_files"]
                    if v["file_type"] == "video/mp4"
                ]

                if mp4_files:
                    mp4_files = sorted(
                        mp4_files,
                        key=lambda x: x.get("width", 0) * x.get("height", 0),
                        reverse=True,
                    )
                    content = requests.get(mp4_files[0]["link"], timeout=60).content
                    with open(path, "wb") as f:
                        f.write(content)
                    self._used_pexels_ids.add(chosen_video["id"])
                    print(f"      ✅ Pexels Video Secured. [ID: {chosen_video['id']}]")
                    return path
        except Exception as e:
            print(f"      ❌ Pexels Video Failed: {e}")
        return False

    def use_pixabay_video_search(self, query, path):
        """
        Search Pixabay for MP4 videos.
        Uses AI to select the best match.
        Skips already-used video IDs to prevent duplicate clips.
        """
        if not self.pixabay_key:
            return False
        print(f"      🎥 Pixabay Video: hunting for '{query}'...")
        try:
            url = (
                f"https://pixabay.com/api/videos/"
                f"?key={self.pixabay_key}"
                f"&q={requests.utils.quote(query)}"
                f"&video_type=film&per_page=15"
            )
            res = requests.get(url, timeout=30)

            hits = res.json().get("hits", [])
            if res.status_code == 200 and hits:
                # Filter out already-used video IDs
                fresh_hits = [
                    h for h in hits if h.get("id") not in self._used_pixabay_ids
                ]
                if not fresh_hits:
                    print(f"      ⚠️ All Pixabay results for '{query}' already used.")
                    return False

                # Build candidates for AI
                candidates = []
                for hit in fresh_hits[:5]:
                    candidates.append({"description": hit.get("tags", ""), "raw": hit})

                # Let AI choose
                chosen_index = self._ai_choose_best_visual(query, candidates, "video")
                chosen_video = candidates[chosen_index]["raw"]

                videos = chosen_video.get("videos", {})
                for quality in ["large", "medium", "small", "tiny"]:
                    if quality in videos and videos[quality].get("url"):
                        content = requests.get(
                            videos[quality]["url"], timeout=60
                        ).content
                        with open(path, "wb") as f:
                            f.write(content)
                        self._used_pixabay_ids.add(chosen_video["id"])
                        print(
                            f"      ✅ Pixabay Video Secured ({quality}). [ID: {chosen_video['id']}]"
                        )
                        return path
        except Exception as e:
            print(f"      ❌ Pixabay Video Failed: {e}")
        return False

    # ─────────────────────────────────────────────
    # IMAGE SOURCES
    # ─────────────────────────────────────────────

    def use_unsplash_image_search(self, query, path):
        """Search Unsplash for portrait images and use AI to select the best match."""
        if not self.unsplash_key:
            return False
        print(f"      📸 Unsplash Image: hunting for '{query}'...")
        try:
            url = f"https://api.unsplash.com/search/photos?query={requests.utils.quote(query)}&per_page=5&orientation=portrait"
            headers = {"Authorization": f"Client-ID {self.unsplash_key}"}
            res = requests.get(url, headers=headers, timeout=30)

            results = res.json().get("results", [])
            if res.status_code == 200 and results:
                candidates = []
                for img in results[:5]:
                    desc = img.get("alt_description") or img.get(
                        "description", "No description"
                    )
                    candidates.append({"description": desc, "raw": img})

                chosen_index = self._ai_choose_best_visual(query, candidates, "image")
                chosen_image = candidates[chosen_index]["raw"]

                img_url = chosen_image["urls"]["regular"]
                content = requests.get(img_url, timeout=20).content
                if self.is_valid_image(content):
                    save_path = (
                        path if path.endswith(".jpg") else path.replace(".mp4", ".jpg")
                    )
                    with open(save_path, "wb") as f:
                        f.write(content)
                    print("      ✅ Unsplash Image Secured.")
                    return save_path
        except Exception as e:
            print(f"      ❌ Unsplash Image Failed: {e}")
        return False

    def use_pexels_image_search(self, query, path):
        """Search Pexels for portrait photos and use AI to select the best match."""
        if not self.pexels_key:
            return False
        print(f"      📸 Pexels Image: hunting for '{query}'...")
        try:
            url = f"https://api.pexels.com/v1/search?query={requests.utils.quote(query)}&per_page=5&orientation=portrait"
            res = requests.get(
                url, headers={"Authorization": self.pexels_key}, timeout=30
            )

            photos = res.json().get("photos", [])
            if res.status_code == 200 and photos:
                candidates = []
                for p in photos[:5]:
                    candidates.append(
                        {
                            "description": p.get(
                                "alt", p.get("url", "").split("/")[-2].replace("-", " ")
                            ),
                            "raw": p,
                        }
                    )

                chosen_index = self._ai_choose_best_visual(query, candidates, "image")
                chosen_image = candidates[chosen_index]["raw"]

                img_url = chosen_image["src"]["large"]
                content = requests.get(img_url, timeout=20).content
                if self.is_valid_image(content):
                    save_path = (
                        path if path.endswith(".jpg") else path.replace(".mp4", ".jpg")
                    )
                    with open(save_path, "wb") as f:
                        f.write(content)
                    print("      ✅ Pexels Image Secured.")
                    return save_path
        except Exception as e:
            print(f"      ❌ Pexels Image Failed: {e}")
        return False

    def use_pixabay_image_search(self, query, path):
        """Search Pixabay for photos and use AI to select the best match."""
        if not self.pixabay_key:
            return False
        print(f"      📸 Pixabay Image: hunting for '{query}'...")
        try:
            url = (
                f"https://pixabay.com/api/"
                f"?key={self.pixabay_key}"
                f"&q={requests.utils.quote(query)}"
                f"&image_type=photo&per_page=5"
            )
            res = requests.get(url, timeout=30)

            hits = res.json().get("hits", [])
            if res.status_code == 200 and hits:
                candidates = []
                for hit in hits[:5]:
                    candidates.append(
                        {"description": hit.get("tags", "No tags"), "raw": hit}
                    )

                chosen_index = self._ai_choose_best_visual(query, candidates, "image")
                chosen_image = candidates[chosen_index]["raw"]

                img_url = chosen_image.get(
                    "largeImageURL", chosen_image.get("webformatURL")
                )
                if img_url:
                    content = requests.get(img_url, timeout=20).content
                    if self.is_valid_image(content):
                        save_path = (
                            path
                            if path.endswith(".jpg")
                            else path.replace(".mp4", ".jpg")
                        )
                        with open(save_path, "wb") as f:
                            f.write(content)
                        print("      ✅ Pixabay Image Secured.")
                        return save_path
        except Exception as e:
            print(f"      ❌ Pixabay Image Failed: {e}")
        return False

    def search_google_images(self, query, path):
        """Scrape Google Images as a last-resort fallback only."""
        print(f"      🌍 Google Image (last resort): hunting for '{query}'...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
        }
        try:
            url = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=isch&udm=2"
            res = requests.get(url, headers=headers, timeout=10)
            matches = re.findall(r'"(https?://[^"]+?\.(?:jpg|jpeg|png))"', res.text)
            if matches:
                for img_url in matches[:5]:
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

        # Reset duplicate guards for this job
        self._used_pexels_ids = set()
        self._used_pixabay_ids = set()
        self._used_nasa_ids = set()

        print(f"🎬 Visual Scout active | niche='{niche}' | {len(scenes)} scenes")
        print(f"🛰️  Per-keyword source routing enabled (NASA triggers active)")

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

                # ── Per-keyword source routing ──────────────────────────
                # Each keyword independently decides its source order.
                # NASA keywords → NASA first.
                # Everything else → niche-based order.
                source_order = self._route_source_order(kw, niche)

                # ── Primary attempt: keyword-routed source chain ────────
                for source_name in source_order:
                    result = self._try_source(source_name, kw, base_filename, folder)
                    if result:
                        saved_path = result
                        print(f"      📦 Source used: {source_name}")
                        break
                    time.sleep(1)

                # ── Fallback 1: retry other keywords from same scene ────
                if not saved_path:
                    for fallback_kw in keywords:
                        if fallback_kw == kw:
                            continue
                        print(
                            f"      ⚠️ '{kw}' failed. Retrying with alt keyword '{fallback_kw}'..."
                        )
                        fallback_order = self._route_source_order(fallback_kw, niche)
                        for source_name in fallback_order[:3]:
                            result = self._try_source(
                                source_name, fallback_kw, base_filename, folder
                            )
                            if result:
                                saved_path = result
                                print(
                                    f"      📦 Fallback source used: {source_name} (kw: '{fallback_kw}')"
                                )
                                break
                        if saved_path:
                            break

                # ── Fallback 2: simplify keyword to first noun only ─────
                if not saved_path:
                    simplified = kw.split()[0] if kw.split() else kw
                    if simplified != kw:
                        print(
                            f"      ⚠️ Retrying with simplified keyword: '{simplified}'..."
                        )
                        simple_order = self._route_source_order(simplified, niche)
                        for source_name in simple_order[:3]:
                            result = self._try_source(
                                source_name, simplified, base_filename, folder
                            )
                            if result:
                                saved_path = result
                                print(
                                    f"      📦 Simplified fallback: {source_name} (kw: '{simplified}')"
                                )
                                break

                # ── Fallback 3: Google Images last resort ───────────────
                if not saved_path:
                    print(f"      ⚠️ All API sources failed. Trying Google Images...")
                    path_jpg = os.path.join(folder, base_filename + ".jpg")
                    result = self.search_google_images(kw, path_jpg)
                    if result:
                        saved_path = result
                        print(f"      📦 Google Images fallback used.")

                # ── Last resort: black placeholder ──────────────────────
                if not saved_path:
                    print(f"      ❌ All sources exhausted. Using black placeholder.")
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
