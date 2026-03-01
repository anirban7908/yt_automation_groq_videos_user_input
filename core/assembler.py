import os
import gc
import whisper
import moviepy.video.fx as vfx
from moviepy import (
    AudioFileClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)
from core.db_manager import DBManager
import time
import torch
import shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Dynamically find the absolute path to your project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class VideoAssembler:
    def __init__(self):
        self.db = DBManager()
        torch.set_num_threads(2)
        self.model = None

    def _load_whisper(self):
        if self.model is None:
            print("🧠 Loading Whisper model...")
            self.model = whisper.load_model("base")

    def _unload_whisper(self):
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("🧹 Whisper model unloaded from memory.")

    def _make_clip(self, path, img_duration):
        """Load, resize, crop, and forcefully loop visuals to match exact duration."""
        try:
            if not os.path.exists(path):
                print(f"⚠️ Missing Visual File: {path}")
                return None

            if path.endswith(".mp4"):
                clip = VideoFileClip(path, audio=False)
                # 🟢 THE FIX: Force short videos to loop until they hit the exact img_duration
                if clip.duration < img_duration:
                    clip = vfx.Loop(duration=img_duration).apply(clip)
                else:
                    clip = clip.subclipped(0, img_duration)
            else:
                clip = ImageClip(path).with_duration(img_duration)

            # Standardize to 9:16 (1080x1920) for Shorts
            clip = clip.resized(height=1920)
            if clip.w < 1080:
                clip = clip.resized(width=1080)
            clip = clip.cropped(
                x_center=clip.w / 2,
                y_center=clip.h / 2,
                width=1080,
                height=1920,
            )
            return clip
        except Exception as e:
            print(f"⚠️ Error processing visual {path}: {e}")
            return None

    def _write_base_video(self, scenes, folder):
        """
        PHASE 1: Stitch the raw video clips and audio together.
        NO text overlays happen here to save RAM.
        """
        scene_files = []

        for i, scene in enumerate(scenes):
            audio_path = os.path.normpath(
                os.path.join(PROJECT_ROOT, scene["audio_path"])
            )
            if not os.path.exists(audio_path):
                continue

            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            visual_paths = scene.get("image_paths", [])

            if not visual_paths:
                audio_clip.close()
                continue

            img_duration = duration / len(visual_paths)
            scene_clips = []

            for raw_path in visual_paths:
                path = os.path.normpath(os.path.join(PROJECT_ROOT, raw_path))
                clip = self._make_clip(path, img_duration)
                if clip is not None:
                    scene_clips.append(clip)

            if not scene_clips:
                audio_clip.close()
                continue

            scene_video = concatenate_videoclips(
                scene_clips, method="chain"
            ).with_audio(audio_clip)

            temp_path = os.path.join(folder, f"_temp_scene_{i}.mp4")
            print(f"   💾 Writing raw scene {i+1}/{len(scenes)} to disk...")

            try:
                scene_video.write_videofile(
                    temp_path,
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    bitrate="4000k",
                    threads=2,
                    preset="ultrafast",
                    logger=None,
                )
                scene_files.append(temp_path)
            except Exception as e:
                print(f"⚠️ Failed to write scene {i}: {e}")
            finally:
                try:
                    scene_video.close()
                except:
                    pass
                try:
                    audio_clip.close()
                except:
                    pass
                for c in scene_clips:
                    try:
                        c.close()
                    except:
                        pass
                gc.collect()

        if not scene_files:
            print("\n🚨 CRITICAL: No scene files were successfully written!")
            return None, None

        print("🔗 Concatenating temporary scene files into base video...")
        temp_clips = [VideoFileClip(p) for p in scene_files]
        base_video = concatenate_videoclips(temp_clips, method="chain")

        base_path = os.path.join(folder, "_BASE_VIDEO_TEMP.mp4")
        full_audio_path = os.path.join(folder, "FULL_AUDIO_TEMP.mp3")

        base_video.audio.write_audiofile(full_audio_path, logger=None)

        base_video.write_videofile(
            base_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            bitrate="4000k",
            threads=2,
            preset="ultrafast",
            logger="bar",
        )

        for c in temp_clips:
            try:
                c.close()
            except:
                pass
        try:
            base_video.close()
        except:
            pass
        gc.collect()

        for p in scene_files:
            try:
                os.remove(p)
            except:
                pass

        return base_path, full_audio_path

    def _draw_text_on_video(
        self, base_path, full_audio_path, out_path, video_title, target_lang
    ):
        """
        PHASE 2: Frame-by-frame Text Burn-in.
        Bypasses MoviePy's CompositeVideoClip memory leak entirely.
        """
        # 🟢 THE HINDI OVERRIDE: Skip all text generation to save rendering time
        import shutil

        if target_lang.strip().lower() == "hindi":
            print(
                "🚫 Hindi language detected. Skipping Whisper and on-screen captions."
            )
            shutil.copy(base_path, out_path)
            return

        # 🟢 CRITICAL FIX: Load the model into memory for English videos
        self._load_whisper()

        print(f"📝 Processing audio for English captions...")

        # Standard English transcription
        result = self.model.transcribe(
            full_audio_path, word_timestamps=True, fp16=False
        )

        # 🟢 Free up RAM immediately after transcribing
        self._unload_whisper()

        words = []
        for segment in result["segments"]:
            for word in segment.get("words", []):
                words.append(word)

        if not words:
            print("⚠️ No word timestamps found. Skipping captions.")
            shutil.copy(base_path, out_path)
            return

        print("📝 Cleaning timestamps...")
        for i in range(len(words)):
            if i < len(words) - 1:
                words[i]["end"] = min(words[i]["end"], words[i + 1]["start"])

        # 🟢 Safely defaulting to Arial for pure English text
        FONT_PATH = r"C:\Windows\Fonts\arial.ttf"

        # Load fonts for PIL
        try:
            caption_font = ImageFont.truetype(FONT_PATH, 90)
            title_font = ImageFont.truetype(FONT_PATH, 80)
        except Exception as e:
            print("⚠️ Font not found, falling back to default.")
            caption_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        # Split long title into multiple lines so it fits on screen
        import textwrap

        wrapped_title = "\n".join(textwrap.wrap(video_title, width=20))

        def draw_frame(get_frame, t):
            """This function is called for every single frame of the video."""
            frame = get_frame(t)

            active_word = None
            for w in words:
                if w["start"] <= t <= w["end"] and w["end"] > w["start"]:
                    active_word = w["word"].strip().upper()
                    break

            show_title = t <= 3.0

            if not active_word and not show_title:
                return frame

            # Convert numpy array to PIL Image
            img = Image.fromarray(frame)
            draw = ImageDraw.Draw(img)

            # Draw Title Hook (Top Center)
            if show_title:
                bbox = draw.multiline_textbbox((0, 0), wrapped_title, font=title_font)
                x = (1080 - (bbox[2] - bbox[0])) / 2
                draw.multiline_text(
                    (x, 300),
                    wrapped_title,
                    font=title_font,
                    fill="yellow",
                    stroke_width=5,
                    stroke_fill="black",
                    align="center",
                )

            # Draw Whisper Captions (Bottom Center)
            if active_word:
                bbox = draw.textbbox((0, 0), active_word, font=caption_font)
                x = (1080 - (bbox[2] - bbox[0])) / 2
                draw.text(
                    (x, 1500),
                    active_word,
                    font=caption_font,
                    fill="white",
                    stroke_width=4,
                    stroke_fill="black",
                )

            return np.array(img)

        print("🎨 Burning text directly into video frames...")
        from moviepy import VideoFileClip

        base_video = VideoFileClip(base_path)

        # Apply the custom frame transformation
        final_video = base_video.transform(draw_frame)

        # Explicitly pass the original audio track back in
        final_video = final_video.with_audio(base_video.audio)

        final_video.write_videofile(
            out_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            bitrate="4000k",
            threads=2,
            preset="ultrafast",
            logger="bar",
        )

        try:
            final_video.close()
            base_video.close()
        except:
            pass
        import gc

        gc.collect()

    def assemble(self):
        task = self.db.collection.find_one({"status": "ready_to_assemble"})
        if not task:
            return

        scenes = task.get("script_data", [])
        folder = os.path.normpath(os.path.join(PROJECT_ROOT, task["folder_path"]))
        target_lang = task.get("target_language", "English")
        video_title = task.get("title", "Breaking News").upper()
        os.makedirs(folder, exist_ok=True)

        print(f"🎞️ Assembling {len(scenes)} segments with PIL optimization...")

        base_path, full_audio_path = self._write_base_video(scenes, folder)
        if not base_path:
            return

        out_path = os.path.join(folder, "FINAL_VIDEO.mp4")
        time.sleep(1)

        # Execute the Frame-by-Frame text burn-in
        self._draw_text_on_video(
            base_path, full_audio_path, out_path, video_title, target_lang
        )

        for temp in [base_path, full_audio_path]:
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except:
                    pass

        self.db.collection.update_one(
            {"_id": task["_id"]},
            {"$set": {"status": "ready_to_upload", "final_video_path": out_path}},
        )
        print(f"🎉 Synchronized Video Ready: {out_path}")
        print("🧹 Cleaned up all temporary files.")
