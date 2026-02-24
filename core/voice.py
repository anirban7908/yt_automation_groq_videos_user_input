import edge_tts
import os
from mutagen.mp3 import MP3
from core.db_manager import DBManager


class VoiceEngine:
    def __init__(self):
        self.db = DBManager()
        # Removed the redundant self.voice_map since scraper.py handles this now

    async def generate_audio(self):
        task = self.db.collection.find_one({"status": "scripted"})
        if not task:
            return

        folder = task.get("folder_path")
        scenes = task.get("script_data", [])
        niche = task.get("niche", "general").lower()

        # Determine the best voice for this video's emotional tone from the DB
        selected_voice = task.get("voice_model", "en-US-GuyNeural")

        print(
            f"🎙️ Generating Audio ({len(scenes)} segments) using {selected_voice} for niche '{niche}'..."
        )

        updated_scenes = []
        for i, scene in enumerate(scenes):
            filename = f"voice_{i}.mp3"
            path = os.path.join(folder, filename)
            text = scene["text"]

            try:
                # 🟢 Apply the dynamically selected voice from the database
                communicate = edge_tts.Communicate(text, selected_voice, rate="+10%")
                await communicate.save(path)

                duration = MP3(path).info.length

                scene["audio_path"] = path
                scene["duration"] = duration

                # 🟢 FIX: We no longer override the image_count with math.
                # We trust the 4 images assigned by brain.py
                img_count = scene.get("image_count", 4)
                img_duration = duration / img_count

                updated_scenes.append(scene)
                print(
                    f"   Seg {i+1}: {duration:.1f}s -> {img_count} visuals (~{img_duration:.1f}s each)"
                )

            except Exception as e:
                print(f"   ❌ Failed scene {i}: {e}")

        self.db.collection.update_one(
            {"_id": task["_id"]},
            {"$set": {"script_data": updated_scenes, "status": "voiced"}},
        )
        print("✅ Audio Generation Complete.")
