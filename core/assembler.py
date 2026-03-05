import os
import gc
import random
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

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

    # ─────────────────────────────────────────────────────────────
    # 🎬 IMAGE EFFECTS ENGINE
    # Applies cinematic motion and color effects to static images
    # so they feel like living video rather than slideshow stills.
    # ─────────────────────────────────────────────────────────────

    def _apply_image_effects(self, clip, img_duration):
        """
        Randomly selects and applies a cinematic effect to a static ImageClip.
        All effects are applied frame-by-frame using numpy for RAM efficiency.
        Returns an animated clip of the same duration.
        """
        effect = random.choice(
            [
                "ken_burns_zoom_in",
                "ken_burns_zoom_out",
                "pan_left_right",
                "pan_right_left",
                "pan_top_bottom",
                "fade_in",
                "fade_out",
                "fade_in_out",
                "gaussian_blur_reveal",
                "color_grade_warm",
                "color_grade_cool",
                "vignette",
                "slow_zoom_with_fade",
                "slide_wipe_left",
            ]
        )

        print(f"         ✨ Applying effect: {effect}")

        W, H = 1080, 1920  # 9:16 portrait for Shorts
        fps = 24
        total_frames = int(img_duration * fps)

        # Get base frame as numpy array
        base_frame = clip.get_frame(0)
        # Ensure correct size
        pil_base = Image.fromarray(base_frame).resize((W, H), Image.LANCZOS)
        base_np = np.array(pil_base)

        def make_frames(effect_name):
            frames = []
            for fi in range(total_frames):
                t = fi / fps
                progress = fi / max(total_frames - 1, 1)  # 0.0 → 1.0
                img = pil_base.copy()

                # ── KEN BURNS: Slow zoom in from 100% to 115% ──
                if effect_name == "ken_burns_zoom_in":
                    scale = 1.0 + 0.15 * progress
                    new_w = int(W * scale)
                    new_h = int(H * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - W) // 2
                    top = (new_h - H) // 2
                    img = img.crop((left, top, left + W, top + H))

                # ── KEN BURNS: Slow zoom out from 115% to 100% ──
                elif effect_name == "ken_burns_zoom_out":
                    scale = 1.15 - 0.15 * progress
                    new_w = int(W * scale)
                    new_h = int(H * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - W) // 2
                    top = (new_h - H) // 2
                    img = img.crop((left, top, left + W, top + H))

                # ── PAN: Slide left to right across a wider image ──
                elif effect_name == "pan_left_right":
                    wide = img.resize((int(W * 1.2), H), Image.LANCZOS)
                    max_offset = wide.width - W
                    offset = int(max_offset * progress)
                    img = wide.crop((offset, 0, offset + W, H))

                # ── PAN: Slide right to left ──
                elif effect_name == "pan_right_left":
                    wide = img.resize((int(W * 1.2), H), Image.LANCZOS)
                    max_offset = wide.width - W
                    offset = int(max_offset * (1 - progress))
                    img = wide.crop((offset, 0, offset + W, H))

                # ── PAN: Slide top to bottom ──
                elif effect_name == "pan_top_bottom":
                    tall = img.resize((W, int(H * 1.2)), Image.LANCZOS)
                    max_offset = tall.height - H
                    offset = int(max_offset * progress)
                    img = tall.crop((0, offset, W, offset + H))

                # ── FADE IN: Black to image ──
                elif effect_name == "fade_in":
                    fade_duration = min(1.0, img_duration * 0.4)
                    alpha = min(1.0, t / fade_duration)
                    black = Image.new("RGB", (W, H), (0, 0, 0))
                    img = Image.blend(black, img, alpha)

                # ── FADE OUT: Image to black ──
                elif effect_name == "fade_out":
                    fade_start = img_duration * 0.6
                    alpha = 1.0 - max(
                        0.0,
                        min(
                            1.0, (t - fade_start) / (img_duration - fade_start + 0.001)
                        ),
                    )
                    black = Image.new("RGB", (W, H), (0, 0, 0))
                    img = Image.blend(black, img, alpha)

                # ── FADE IN + OUT: Black → image → black ──
                elif effect_name == "fade_in_out":
                    fade = min(1.0, img_duration * 0.3)
                    alpha_in = min(1.0, t / fade)
                    alpha_out = 1.0 - max(
                        0.0, min(1.0, (t - (img_duration - fade)) / (fade + 0.001))
                    )
                    alpha = min(alpha_in, alpha_out)
                    black = Image.new("RGB", (W, H), (0, 0, 0))
                    img = Image.blend(black, img, alpha)

                # ── GAUSSIAN BLUR REVEAL: Blurry → sharp over time ──
                elif effect_name == "gaussian_blur_reveal":
                    blur_radius = max(0, 12 * (1 - progress))
                    if blur_radius > 0.5:
                        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

                # ── COLOR GRADE: Warm (golden hour feel) ──
                elif effect_name == "color_grade_warm":
                    r, g, b = img.split()
                    r = ImageEnhance.Brightness(r).enhance(1.15)
                    b = ImageEnhance.Brightness(b).enhance(0.85)
                    img = Image.merge("RGB", (r, g, b))
                    img = ImageEnhance.Contrast(img).enhance(1.1)
                    img = ImageEnhance.Color(img).enhance(1.2)

                # ── COLOR GRADE: Cool (cinematic blue tone) ──
                elif effect_name == "color_grade_cool":
                    r, g, b = img.split()
                    r = ImageEnhance.Brightness(r).enhance(0.88)
                    b = ImageEnhance.Brightness(b).enhance(1.12)
                    img = Image.merge("RGB", (r, g, b))
                    img = ImageEnhance.Contrast(img).enhance(1.15)
                    img = ImageEnhance.Color(img).enhance(0.9)

                # ── VIGNETTE: Dark edges draw focus to center ──
                elif effect_name == "vignette":
                    vignette = Image.new("RGB", (W, H), (0, 0, 0))
                    mask = Image.new("L", (W, H), 0)
                    draw = ImageDraw.Draw(mask)
                    margin = 0.35
                    draw.ellipse(
                        [
                            int(W * margin),
                            int(H * margin),
                            int(W * (1 - margin)),
                            int(H * (1 - margin)),
                        ],
                        fill=255,
                    )
                    mask = mask.filter(ImageFilter.GaussianBlur(radius=200))
                    img = Image.composite(img, vignette, mask)

                # ── SLOW ZOOM + FADE IN: Combines Ken Burns with fade ──
                elif effect_name == "slow_zoom_with_fade":
                    scale = 1.0 + 0.12 * progress
                    new_w = int(W * scale)
                    new_h = int(H * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - W) // 2
                    top = (new_h - H) // 2
                    img = img.crop((left, top, left + W, top + H))
                    fade = min(1.0, img_duration * 0.3)
                    alpha = min(1.0, t / fade)
                    black = Image.new("RGB", (W, H), (0, 0, 0))
                    img = Image.blend(black, img, alpha)

                # ── WIPE: Slide in from left ──
                elif effect_name == "slide_wipe_left":
                    wipe_w = int(W * min(1.0, progress * 2))
                    black = Image.new("RGB", (W, H), (0, 0, 0))
                    black.paste(img.crop((0, 0, wipe_w, H)), (0, 0))
                    img = black

                frames.append(np.array(img))
            return frames

        frames = make_frames(effect)

        def make_frame(t):
            fi = min(int(t * fps), total_frames - 1)
            return frames[fi]

        animated_clip = clip.with_duration(img_duration)
        animated_clip = animated_clip.transform(
            lambda get_frame, t: make_frame(t), apply_to="video"
        )
        return animated_clip

    # ─────────────────────────────────────────────────────────────
    # CLIP LOADER — detects static images and applies effects
    # ─────────────────────────────────────────────────────────────

    def _make_clip(self, path, img_duration):
        """Load, resize, crop visuals. Static images get cinematic effects applied."""
        try:
            if not os.path.exists(path):
                print(f"⚠️ Missing Visual File: {path}")
                return None

            if path.endswith(".mp4"):
                # ── VIDEO FILE: loop or trim to fit duration ──
                clip = VideoFileClip(path, audio=False)
                if clip.duration < img_duration:
                    clip = vfx.Loop(duration=img_duration).apply(clip)
                else:
                    clip = clip.subclipped(0, img_duration)

                # Standardize to 9:16
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

            else:
                # ── STATIC IMAGE: resize, crop, then apply cinematic effect ──
                clip = ImageClip(path).with_duration(img_duration)

                # Standardize to 9:16 first
                clip = clip.resized(height=1920)
                if clip.w < 1080:
                    clip = clip.resized(width=1080)
                clip = clip.cropped(
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                    width=1080,
                    height=1920,
                )

                # 🎬 Apply random cinematic effect
                clip = self._apply_image_effects(clip, img_duration)
                return clip

        except Exception as e:
            print(f"⚠️ Error processing visual {path}: {e}")
            return None

    def _write_base_video(self, scenes, folder):
        """
        PHASE 1: Stitch raw video clips and audio together.
        NO text overlays here to save RAM.
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
        if target_lang.strip().lower() == "hindi":
            print(
                "🚫 Hindi language detected. Skipping Whisper and on-screen captions."
            )
            shutil.copy(base_path, out_path)
            return

        self._load_whisper()
        print(f"📝 Processing audio for English captions...")

        result = self.model.transcribe(
            full_audio_path, word_timestamps=True, fp16=False
        )
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

        FONT_PATH = r"C:\Windows\Fonts\arial.ttf"

        try:
            caption_font = ImageFont.truetype(FONT_PATH, 90)
            title_font = ImageFont.truetype(FONT_PATH, 80)
        except Exception as e:
            print("⚠️ Font not found, falling back to default.")
            caption_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        import textwrap

        wrapped_title = "\n".join(textwrap.wrap(video_title, width=20))

        def draw_frame(get_frame, t):
            frame = get_frame(t)

            active_word = None
            for w in words:
                if w["start"] <= t <= w["end"] and w["end"] > w["start"]:
                    active_word = w["word"].strip().upper()
                    break

            show_title = t <= 3.0

            if not active_word and not show_title:
                return frame

            img = Image.fromarray(frame)
            draw = ImageDraw.Draw(img)

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
        final_video = base_video.transform(draw_frame)
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

        print(f"🎞️ Assembling {len(scenes)} segments with cinematic image effects...")

        base_path, full_audio_path = self._write_base_video(scenes, folder)
        if not base_path:
            return

        out_path = os.path.join(folder, "FINAL_VIDEO.mp4")
        time.sleep(1)

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
