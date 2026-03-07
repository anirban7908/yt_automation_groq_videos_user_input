import os
import gc
import random
import textwrap
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

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

NICHE_STYLES = {
    "space": {
        "allowed_transitions": ["crossfade", "zoom_cut", "light_leak"],
        "color_grade": {
            "r": 0.85,
            "g": 0.90,
            "b": 1.20,
            "contrast": 1.3,
            "saturation": 1.4,
        },
        "film_grain": 0.3,
        "light_leak_color": (80, 60, 180),
    },
    "tech_ai": {
        "allowed_transitions": ["crossfade", "whip_pan", "zoom_cut"],
        "color_grade": {
            "r": 0.80,
            "g": 0.95,
            "b": 1.25,
            "contrast": 1.25,
            "saturation": 0.9,
        },
        "film_grain": 0.15,
        "light_leak_color": (40, 120, 255),
    },
    "psychology": {
        "allowed_transitions": ["crossfade", "zoom_cut"],
        "color_grade": {
            "r": 1.0,
            "g": 0.92,
            "b": 0.85,
            "contrast": 1.15,
            "saturation": 0.85,
        },
        "film_grain": 0.2,
        "light_leak_color": (180, 100, 60),
    },
    "geography": {
        "allowed_transitions": ["crossfade", "whip_pan", "zoom_cut", "light_leak"],
        "color_grade": {
            "r": 1.05,
            "g": 1.10,
            "b": 0.90,
            "contrast": 1.2,
            "saturation": 1.5,
        },
        "film_grain": 0.1,
        "light_leak_color": (255, 200, 80),
    },
    "worldnews": {
        "allowed_transitions": ["crossfade", "zoom_cut"],
        "color_grade": {
            "r": 0.90,
            "g": 0.90,
            "b": 0.90,
            "contrast": 1.3,
            "saturation": 0.75,
        },
        "film_grain": 0.25,
        "light_leak_color": (200, 200, 200),
    },
    "home_decor": {
        "allowed_transitions": ["crossfade", "zoom_cut"],
        "color_grade": {
            "r": 1.10,
            "g": 1.05,
            "b": 0.92,
            "contrast": 1.1,
            "saturation": 1.2,
        },
        "film_grain": 0.05,
        "light_leak_color": (255, 220, 150),
    },
    "indian_history": {
        "allowed_transitions": ["crossfade", "zoom_cut", "light_leak"],
        "color_grade": {
            "r": 1.15,
            "g": 0.95,
            "b": 0.70,
            "contrast": 1.2,
            "saturation": 1.1,
        },
        "film_grain": 0.4,
        "light_leak_color": (200, 120, 30),
    },
    "science_facts": {
        "allowed_transitions": ["crossfade", "whip_pan", "zoom_cut"],
        "color_grade": {
            "r": 0.90,
            "g": 1.10,
            "b": 1.15,
            "contrast": 1.2,
            "saturation": 1.3,
        },
        "film_grain": 0.15,
        "light_leak_color": (100, 220, 255),
    },
    "health_wellness": {
        "allowed_transitions": ["crossfade", "zoom_cut"],
        "color_grade": {
            "r": 0.95,
            "g": 1.10,
            "b": 0.95,
            "contrast": 1.1,
            "saturation": 1.2,
        },
        "film_grain": 0.05,
        "light_leak_color": (150, 255, 150),
    },
    "animals_nature": {
        "allowed_transitions": ["crossfade", "whip_pan", "zoom_cut", "light_leak"],
        "color_grade": {
            "r": 0.95,
            "g": 1.15,
            "b": 0.85,
            "contrast": 1.2,
            "saturation": 1.6,
        },
        "film_grain": 0.1,
        "light_leak_color": (255, 230, 100),
    },
    "finance_economy": {
        "allowed_transitions": ["crossfade", "zoom_cut"],
        "color_grade": {
            "r": 0.95,
            "g": 0.95,
            "b": 0.95,
            "contrast": 1.2,
            "saturation": 0.8,
        },
        "film_grain": 0.1,
        "light_leak_color": (220, 180, 60),
    },
    "bizarre_facts": {
        "allowed_transitions": ["crossfade", "whip_pan", "zoom_cut", "light_leak"],
        "color_grade": {
            "r": 1.10,
            "g": 0.85,
            "b": 1.10,
            "contrast": 1.35,
            "saturation": 1.4,
        },
        "film_grain": 0.35,
        "light_leak_color": (180, 50, 200),
    },
    "history_world": {
        "allowed_transitions": ["crossfade", "zoom_cut", "light_leak"],
        "color_grade": {
            "r": 1.15,
            "g": 1.00,
            "b": 0.75,
            "contrast": 1.15,
            "saturation": 0.9,
        },
        "film_grain": 0.45,
        "light_leak_color": (180, 130, 50),
    },
    "default": {
        "allowed_transitions": ["crossfade", "zoom_cut"],
        "color_grade": {
            "r": 1.0,
            "g": 1.0,
            "b": 1.0,
            "contrast": 1.1,
            "saturation": 1.1,
        },
        "film_grain": 0.1,
        "light_leak_color": (255, 255, 255),
    },
}


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

    def _find_best_start(self, video_path, required_duration):
        try:
            import cv2

            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 24
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            total_duration = total_frames / fps
            max_start = total_duration - required_duration
            if max_start <= 0.5:
                cap.release()
                return 0.0
            prev_frame = None
            frame_scores = []
            for fi in range(0, total_frames, 3):
                cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
                ret, frame = cap.read()
                if not ret:
                    break
                small = cv2.resize(frame, (64, 64))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                if prev_frame is not None:
                    diff = cv2.absdiff(gray, prev_frame)
                    score = float(np.mean(diff))
                    timestamp = fi / fps
                    if timestamp <= max_start:
                        frame_scores.append((timestamp, score))
                prev_frame = gray
            cap.release()
            if not frame_scores:
                return 0.0
            top_moments = sorted(frame_scores, key=lambda x: x[1], reverse=True)[:5]
            best_start = random.choice(top_moments)[0]
            print(f"         🎯 Smart start: {best_start:.1f}s (skipped boring intro)")
            return best_start
        except ImportError:
            print("         ⚠️ OpenCV not installed. Run: pip install opencv-python")
            try:
                clip = VideoFileClip(video_path, audio=False)
                total = clip.duration
                clip.close()
                max_start = max(0.0, total - required_duration)
                return random.uniform(0, max_start * 0.6) if max_start > 1 else 0.0
            except:
                return 0.0
        except Exception as e:
            print(f"         ⚠️ Scene detection error: {e}. Using start=0.")
            return 0.0

    def _apply_color_grade(self, pil_image, grade):
        r, g, b = pil_image.split()
        r = ImageEnhance.Brightness(r).enhance(grade.get("r", 1.0))
        g = ImageEnhance.Brightness(g).enhance(grade.get("g", 1.0))
        b = ImageEnhance.Brightness(b).enhance(grade.get("b", 1.0))
        img = Image.merge("RGB", (r, g, b))
        img = ImageEnhance.Contrast(img).enhance(grade.get("contrast", 1.0))
        img = ImageEnhance.Color(img).enhance(grade.get("saturation", 1.0))
        return img

    def _apply_film_grain(self, frame_np, intensity=0.15):
        if intensity <= 0:
            return frame_np
        noise = np.random.randint(
            -int(30 * intensity), int(30 * intensity), frame_np.shape, dtype=np.int16
        )
        return np.clip(frame_np.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    def _apply_image_effects(self, clip, img_duration):
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
        print(f"         ✨ Image effect: {effect}")
        W, H = 1080, 1920
        fps = 24
        total_frames = int(img_duration * fps)
        base_frame = clip.get_frame(0)
        pil_base = Image.fromarray(base_frame).resize((W, H), Image.LANCZOS)

        def make_frames(effect_name):
            frames = []
            for fi in range(total_frames):
                t = fi / fps
                progress = fi / max(total_frames - 1, 1)
                img = pil_base.copy()

                if effect_name == "ken_burns_zoom_in":
                    scale = 1.0 + 0.15 * progress
                    new_w, new_h = int(W * scale), int(H * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    img = img.crop(
                        (
                            (new_w - W) // 2,
                            (new_h - H) // 2,
                            (new_w - W) // 2 + W,
                            (new_h - H) // 2 + H,
                        )
                    )
                elif effect_name == "ken_burns_zoom_out":
                    scale = 1.15 - 0.15 * progress
                    new_w, new_h = int(W * scale), int(H * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    img = img.crop(
                        (
                            (new_w - W) // 2,
                            (new_h - H) // 2,
                            (new_w - W) // 2 + W,
                            (new_h - H) // 2 + H,
                        )
                    )
                elif effect_name == "pan_left_right":
                    wide = img.resize((int(W * 1.2), H), Image.LANCZOS)
                    offset = int((wide.width - W) * progress)
                    img = wide.crop((offset, 0, offset + W, H))
                elif effect_name == "pan_right_left":
                    wide = img.resize((int(W * 1.2), H), Image.LANCZOS)
                    offset = int((wide.width - W) * (1 - progress))
                    img = wide.crop((offset, 0, offset + W, H))
                elif effect_name == "pan_top_bottom":
                    tall = img.resize((W, int(H * 1.2)), Image.LANCZOS)
                    offset = int((tall.height - H) * progress)
                    img = tall.crop((0, offset, W, offset + H))
                elif effect_name == "fade_in":
                    alpha = min(1.0, t / min(1.0, img_duration * 0.4))
                    img = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), img, alpha)
                elif effect_name == "fade_out":
                    fade_start = img_duration * 0.6
                    alpha = 1.0 - max(
                        0.0,
                        min(
                            1.0, (t - fade_start) / (img_duration - fade_start + 0.001)
                        ),
                    )
                    img = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), img, alpha)
                elif effect_name == "fade_in_out":
                    fade = min(1.0, img_duration * 0.3)
                    alpha_in = min(1.0, t / fade)
                    alpha_out = 1.0 - max(
                        0.0, min(1.0, (t - (img_duration - fade)) / (fade + 0.001))
                    )
                    img = Image.blend(
                        Image.new("RGB", (W, H), (0, 0, 0)),
                        img,
                        min(alpha_in, alpha_out),
                    )
                elif effect_name == "gaussian_blur_reveal":
                    blur_radius = max(0, 12 * (1 - progress))
                    if blur_radius > 0.5:
                        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
                elif effect_name == "color_grade_warm":
                    r, g, b = img.split()
                    r = ImageEnhance.Brightness(r).enhance(1.15)
                    b = ImageEnhance.Brightness(b).enhance(0.85)
                    img = ImageEnhance.Color(
                        ImageEnhance.Contrast(Image.merge("RGB", (r, g, b))).enhance(
                            1.1
                        )
                    ).enhance(1.2)
                elif effect_name == "color_grade_cool":
                    r, g, b = img.split()
                    r = ImageEnhance.Brightness(r).enhance(0.88)
                    b = ImageEnhance.Brightness(b).enhance(1.12)
                    img = ImageEnhance.Color(
                        ImageEnhance.Contrast(Image.merge("RGB", (r, g, b))).enhance(
                            1.15
                        )
                    ).enhance(0.9)
                elif effect_name == "vignette":
                    vignette = Image.new("RGB", (W, H), (0, 0, 0))
                    mask = Image.new("L", (W, H), 0)
                    m = 0.35
                    ImageDraw.Draw(mask).ellipse(
                        [int(W * m), int(H * m), int(W * (1 - m)), int(H * (1 - m))],
                        fill=255,
                    )
                    mask = mask.filter(ImageFilter.GaussianBlur(radius=200))
                    img = Image.composite(img, vignette, mask)
                elif effect_name == "slow_zoom_with_fade":
                    scale = 1.0 + 0.12 * progress
                    new_w, new_h = int(W * scale), int(H * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    img = img.crop(
                        (
                            (new_w - W) // 2,
                            (new_h - H) // 2,
                            (new_w - W) // 2 + W,
                            (new_h - H) // 2 + H,
                        )
                    )
                    fade = min(1.0, img_duration * 0.3)
                    img = Image.blend(
                        Image.new("RGB", (W, H), (0, 0, 0)), img, min(1.0, t / fade)
                    )
                elif effect_name == "slide_wipe_left":
                    wipe_w = int(W * min(1.0, progress * 2))
                    black = Image.new("RGB", (W, H), (0, 0, 0))
                    black.paste(img.crop((0, 0, wipe_w, H)), (0, 0))
                    img = black

                frames.append(np.array(img))
            return frames

        frames = make_frames(effect)

        def make_frame(t):
            return frames[min(int(t * fps), total_frames - 1)]

        return clip.with_duration(img_duration).transform(
            lambda gf, t: make_frame(t), apply_to="video"
        )

    def _make_transition_frames(self, clip_a, clip_b, transition, leak_color):
        W, H, fps = 1080, 1920, 24
        durations = {
            "crossfade": 0.25,
            "whip_pan": 0.15,
            "light_leak": 0.20,
            "zoom_cut": 0.10,
        }
        duration = durations.get(transition, 0.2)
        n_frames = int(duration * fps)
        frames = []
        try:
            for fi in range(n_frames):
                progress = fi / n_frames
                t_a = min(
                    clip_a.duration - 0.01,
                    max(0, clip_a.duration - duration + (fi / fps)),
                )
                t_b = min(clip_b.duration - 0.01, max(0, fi / fps))
                frame_a = clip_a.get_frame(t_a)
                frame_b = clip_b.get_frame(t_b)

                if transition == "crossfade":
                    out = np.clip(
                        frame_a.astype(np.float32) * (1 - progress)
                        + frame_b.astype(np.float32) * progress,
                        0,
                        255,
                    ).astype(np.uint8)
                elif transition == "whip_pan":
                    blur_r = int(40 * np.sin(progress * np.pi))
                    base = frame_a if progress < 0.5 else frame_b
                    pil = Image.fromarray(base)
                    if blur_r > 0:
                        pil = pil.filter(ImageFilter.GaussianBlur(radius=blur_r))
                    out = np.array(pil)
                elif transition == "light_leak":
                    base = frame_a if progress < 0.5 else frame_b
                    alpha = float(np.sin(progress * np.pi)) * 0.7
                    out = np.array(
                        Image.blend(
                            Image.fromarray(base),
                            Image.new("RGB", (W, H), leak_color),
                            alpha,
                        )
                    )
                elif transition == "zoom_cut":
                    scale = 1.15 - (0.15 * progress)
                    new_w, new_h = int(W * scale), int(H * scale)
                    pil = Image.fromarray(frame_b).resize((new_w, new_h), Image.LANCZOS)
                    left, top = (new_w - W) // 2, (new_h - H) // 2
                    out = np.array(pil.crop((left, top, left + W, top + H)))
                else:
                    out = frame_b

                frames.append(out)
        except Exception as e:
            print(f"      ⚠️ Transition '{transition}' error: {e}")
        return frames

    def _make_clip(self, path, img_duration, niche_style):
        try:
            if not os.path.exists(path):
                print(f"⚠️ Missing Visual File: {path}")
                return None

            grade = niche_style.get("color_grade", {})

            if path.endswith(".mp4"):
                best_start = self._find_best_start(path, img_duration)
                clip = VideoFileClip(path, audio=False)

                if clip.duration < img_duration:
                    clip = vfx.Loop(duration=img_duration).apply(clip)
                    clip = clip.subclipped(0, img_duration)
                else:
                    end = min(best_start + img_duration, clip.duration)
                    clip = clip.subclipped(best_start, end)

                if grade:

                    def grade_video_frame(get_frame, t):
                        return np.array(
                            self._apply_color_grade(
                                Image.fromarray(get_frame(t)), grade
                            )
                        )

                    clip = clip.transform(grade_video_frame, apply_to="video")

                clip = clip.resized(height=1920)
                if clip.w < 1080:
                    clip = clip.resized(width=1080)
                clip = clip.cropped(
                    x_center=clip.w / 2, y_center=clip.h / 2, width=1080, height=1920
                )
                return clip

            else:
                clip = ImageClip(path).with_duration(img_duration)
                clip = clip.resized(height=1920)
                if clip.w < 1080:
                    clip = clip.resized(width=1080)
                clip = clip.cropped(
                    x_center=clip.w / 2, y_center=clip.h / 2, width=1080, height=1920
                )

                if grade:
                    base_frame = clip.get_frame(0)
                    graded = np.array(
                        self._apply_color_grade(Image.fromarray(base_frame), grade)
                    )
                    clip = clip.transform(lambda gf, t: graded, apply_to="video")

                clip = self._apply_image_effects(clip, img_duration)
                return clip

        except Exception as e:
            print(f"⚠️ Error processing visual {path}: {e}")
            return None

    def _write_base_video(self, scenes, folder, niche):
        niche_style = NICHE_STYLES.get(niche, NICHE_STYLES["default"])
        allowed_transitions = niche_style.get("allowed_transitions", ["crossfade"])
        grain_intensity = niche_style.get("film_grain", 0.1)
        leak_color = niche_style.get("light_leak_color", (255, 255, 255))

        print(
            f"🎨 Style: '{niche}' | transitions: {allowed_transitions} | grain: {grain_intensity}"
        )

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
                clip = self._make_clip(path, img_duration, niche_style)
                if clip is not None:
                    scene_clips.append(clip)

            if not scene_clips:
                audio_clip.close()
                continue

            if len(scene_clips) > 1:
                final_clips = [scene_clips[0]]
                for ci in range(1, len(scene_clips)):
                    clip_a = final_clips[-1]
                    clip_b = scene_clips[ci]
                    transition = random.choice(allowed_transitions)
                    trans_frames = self._make_transition_frames(
                        clip_a, clip_b, transition, leak_color
                    )
                    if trans_frames:
                        fps = 24
                        trans_dur = len(trans_frames) / fps
                        captured = trans_frames
                        trans_clip = ImageClip(trans_frames[0]).with_duration(trans_dur)
                        trans_clip = trans_clip.transform(
                            lambda gf, t, fr=captured: fr[
                                min(int(t * fps), len(fr) - 1)
                            ],
                            apply_to="video",
                        )
                        final_clips.append(trans_clip)
                    final_clips.append(clip_b)
                scene_clips = final_clips

            if grain_intensity > 0:
                grained = []
                for clip in scene_clips:
                    gi = grain_intensity
                    grained.append(
                        clip.transform(
                            lambda gf, t, g=gi: self._apply_film_grain(gf(t), g),
                            apply_to="video",
                        )
                    )
                scene_clips = grained

            scene_video = concatenate_videoclips(
                scene_clips, method="chain"
            ).with_audio(audio_clip)
            temp_path = os.path.join(folder, f"_temp_scene_{i}.mp4")
            print(f"   💾 Writing scene {i+1}/{len(scenes)} to disk...")

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
        if target_lang.strip().lower() == "hindi":
            print("🚫 Hindi detected. Skipping Whisper captions.")
            shutil.copy(base_path, out_path)
            return

        self._load_whisper()
        print("📝 Processing audio for English captions...")
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
        except:
            print("⚠️ Font not found, falling back to default.")
            caption_font = ImageFont.load_default()
            title_font = ImageFont.load_default()

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
        from moviepy import VideoFileClip as VFC

        base_video = VFC(base_path)
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
        niche = task.get("niche", "default").lower()
        os.makedirs(folder, exist_ok=True)

        print(f"🎞️ Assembling {len(scenes)} scenes | niche: '{niche}'")

        base_path, full_audio_path = self._write_base_video(scenes, folder, niche)
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
