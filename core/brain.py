import json
import re
import os
from groq import Groq
from core.ai_core import AIEngine
from core.db_manager import DBManager
from dotenv import load_dotenv

load_dotenv()


class ScriptGenerator:
    def __init__(self, **kwargs):
        self.db = DBManager()
        self.ai = AIEngine()

    def get_expert_role(self, niche):
        role_map = {
            "space": "authoritative science and astronomy communicator",
            "tech_ai": "sharp futurist and technology analyst",
            "psychology": "insightful psychology and human behavior expert",
            "health_wellness": "credible health and medical journalist who explains science simply",
            "animals_nature": "passionate wildlife documentary narrator in the style of David Attenborough",
            "finance_economy": "sharp financial analyst who explains money and markets in plain language",
            "bizarre_facts": "captivating storyteller obsessed with the world's strangest true facts",
            "history_world": "authoritative world historian who brings forgotten stories to life",
        }
        return role_map.get(niche, "highly informative educator")

    def repair_json(self, json_str):
        try:
            json_str = re.sub(r"^[^{]*", "", json_str)
            json_str = re.sub(r"[^}]*$", "", json_str)
            return json.loads(json_str)
        except:
            return None

    def validate_script(self, data):
        if not data or "scenes" not in data:
            return False, "Missing scenes key"

        scenes = data["scenes"]
        if not (6 <= len(scenes) <= 8):
            return False, f"Wrong scene count: {len(scenes)} (expected 6-8)"

        BANNED_EXACT = {
            "nazi",
            "hitler",
            # "subscribe button",
            "like button",
            "comment button",
            "female portrait",
            "male portrait",
            "war room",
            "propaganda",
            "abstract",
            "concept",
            "symbol",
            "icon",
            "background",
            "texture",
        }

        # These words anywhere in a keyword = invalid (non-filmable CGI/design terms)
        BANNED_CONTAINS = {
            "animated",
            "animation",
            "infographic",
            "diagram",
            "3d",
            "illustration",
            "visualization",
            "render",
        }

        for i, scene in enumerate(scenes):
            if not scene.get("text"):
                return False, f"Scene {i} missing text"
            if not scene.get("keywords") or not isinstance(scene["keywords"], list):
                return False, f"Scene {i} missing keywords"

            count = scene.get("image_count", 0)

            # 🟢 Allow up to 4 images for faster pacing
            if count not in [1, 2, 3, 4]:
                return False, f"Scene {i} has invalid image_count: {count}"

            if len(scene["keywords"]) != count:
                return (
                    False,
                    f"Scene {i}: keywords count ({len(scene['keywords'])}) doesn't match image_count ({count})",
                )

            # 🟢 NEW: Validate trigger words
            trigger_words = scene.get("trigger_words", [])
            if len(trigger_words) != count:
                return (
                    False,
                    f"Scene {i}: trigger_words count ({len(trigger_words)}) doesn't match image_count ({count})",
                )

            # (Keep your existing BANNED_EXACT logic below this)
            for kw in scene["keywords"]:
                kw_lower = kw.strip().lower()
                if kw_lower in BANNED_EXACT:
                    return False, f"Scene {i} contains banned keyword: '{kw}'"
                for banned_word in BANNED_CONTAINS:
                    if banned_word in kw_lower:
                        return (
                            False,
                            f"Scene {i} contains non-filmable term '{banned_word}' in keyword: '{kw}'",
                        )

        return True, "OK"

    def generate_narration(self, sys_prompt, expert_role, source, niche, feedback=""):
        """
        Generates the spoken voiceover script — English only, 90-110 seconds, 6-8 scenes.
        Optional feedback param used when user requests a script regeneration with notes.
        """
        print(f"✍️ Narration Writer: Crafting English script...")

        feedback_section = (
            f"\n\nUSER FEEDBACK TO ADDRESS IN THIS VERSION:\n{feedback}"
            if feedback
            else ""
        )

        prompt = f"""
            ROLE: {sys_prompt}
            TASK: You are a {expert_role} and a master of YouTube Shorts retention. Read the source material and write a highly informative, engaging, high-tension voiceover script. Explain complex topics in simple terms. Keep total length between 90-110 seconds of spoken narration.
            SOURCE: "{source}"{feedback_section}

            RULES:
            1. HOOK: Scene 1 MUST open with a pattern-interrupt like "Stop scrolling...", "What if I told you...", or a bold shocking claim. No generic questions.
            2. TONE: Write the way people actually speak. Short punchy sentences. Use (..., —, !, ?) for voiceover rhythm and suspense. You may use words like "terrifying", "bizarre", "breakthrough" but NEVER invent or exaggerate facts.
            3. FACTS ONLY: No personal stories, no "I" statements, no motivational fluff. Facts, science, history, news only.
            4. LANGUAGE: Write entirely in ENGLISH. Use simple conversational language, NOT formal or academic.
            5. STRUCTURE: Write exactly 6-8 scenes. Each scene = 10-13 seconds of spoken narration (~25-35 words).
            6. FINAL SCENE: Must end with the exact phrase: "Please like, share, and subscribe!"

            OUTPUT FORMAT — plain numbered list, nothing else:
            Scene 1: [narration text]
            Scene 2: [narration text]
            ...
            Scene 8: [narration text]
            """

        try:
            response = self.ai.generate(
                system_prompt=f"You are {sys_prompt}. Write ONLY the numbered scene list. No JSON, no extra commentary.",
                user_prompt=prompt,
                require_json=False,
            )
            return response.strip()
        except Exception as e:
            print(f"❌ Narration Error: {e}")
            return None

    def generate_packaging(
        self,
        narration_text,
        core_subject,
        niche,
        pre_hashtags,
        pexels_style,
        feedback="",
    ):
        """
        Takes finished narration text and generates JSON with visual keywords + metadata.
        Optional feedback param passes user notes directly into the keyword generation too.
        """
        print(f"📦 Packaging Agent: Generating keywords and metadata...")

        feedback_section = (
            f"\n\n            USER FEEDBACK TO APPLY TO KEYWORDS AND METADATA:\n            {feedback}"
            if feedback
            else ""
        )

        prompt = f"""
            TASK: You are a stock footage coordinator and SEO expert. Given the finished script scenes below, output a JSON object with visual keywords and metadata.

            FINISHED SCRIPT:
            {narration_text}
            {feedback_section}

            KEYWORD RULES:
            - Every keyword must describe ONE single REAL, PHYSICAL, FILMABLE subject that actually exists in stock footage libraries.
            - Keywords must be 2-4 words MAX. Format: [subject] + ONE cinematic modifier (lighting OR angle OR setting).
            - STRICT NO DUPLICATE RULE: Scan ALL keywords across ALL scenes. Replace duplicates.
            - 🔴 NO MICROSCOPIC/INVISIBLE SUBJECTS: You CANNOT film "peptides", "enzymes", "stomach acid", "viruses", or "genes". If the text mentions these, YOU MUST substitute a generic human equivalent (e.g., use "scientist in lab", "doctor hospital", "medicine pill", "medical scan").
            - 🔴 NO ABSTRACT CONCEPTS: Never use keywords like "complicated equation", "cure", or "breakthrough". Use literal physical objects.
            - FAST PACING RULE: Change the visual every 1-2 sentences to maintain high retention!
                - Under 10 words = image_count: 1
                - 10-18 words = image_count: 2
                - 18-28 words = image_count: 3
                - 28+ words = image_count: 4
            - keywords array length MUST equal image_count exactly.

            TRIGGER WORDS (Perfect Sync Magic):
            - For each keyword, you MUST provide a "trigger_word" from the text. This is the exact word where the video clip should cut.
            - The trigger_words array length MUST equal image_count exactly.
            - The first trigger_word in a scene MUST be the very first word of the scene's text.
            - The following trigger_words should be the exact noun or verb that relates to the visual.
            - Example Text: "The megalodon was massive, but it was made of cartilage like your ears."
            - Example Keywords: ["massive shark underwater", "human ear close up"]
            - Example Trigger Words: ["The", "cartilage"]

            STOCK FOOTAGE REALITY CHECK — style for this video: "{pexels_style}"
            Ask yourself: "Can I find this exact shot on Pexels or Pixabay right now?" If NO → simplify.

            METADATA RULES (all fields strictly in ENGLISH):
            - title: clickbait style, max 50 characters, high curiosity
            - description: 3 sentences summarizing the video + call to action
            - hashtags: use these exactly: {pre_hashtags}, then add 5 more specific ones
            - tags: array of 10-15 highly searched SEO keywords

            OUTPUT ONLY valid JSON:
            {{
                "title": "...",
                "description": "...",
                "hashtags": "...",
                "tags": ["...", "..."],
                "scenes": [
                    {{
                        "text": "exact scene narration copied here",
                        "keywords": ["subject cinematic modifier", "subject cinematic modifier"],
                        "trigger_words": ["FirstWord", "ImpactWord"],
                        "image_count": 2
                    }}
                ]
            }}
        """

        try:
            response = self.ai.generate(
                system_prompt="You output ONLY valid JSON dictionaries. Copy scene text exactly as given.",
                user_prompt=prompt,
                require_json=True,
            )
            return self.repair_json(response)
        except Exception as e:
            print(f"❌ Packaging Error: {e}")
            return None

    def generate_meta_prompt(self, niche, source_text, expert_role):
        print(f"🕵️‍♂️ AI Strategist: Analyzing '{niche}' story to build custom persona...")

        meta_prompt = f"""
            TASK: You are a Master YouTube Shorts Strategist.
            I am going to give you a raw news story about {niche}.
            You need to invent a highly specific, engaging Persona/Role for the scriptwriter, and identify the core subject of the video.

            NEWS STORY: "{source_text}"

            REQUIREMENTS:
            1. 'system_prompt': Write a 3-sentence persona. You MUST adopt the tone of a {expert_role}. Ignore any personal anecdotes or fluff in the news.
            2. 'core_subject': In 1 to 3 words, what is the exact physical subject of this news? (e.g., "Deep Space", "Cybersecurity", "Ancient Egypt").

            OUTPUT ONLY JSON:
            {{
                "system_prompt": "Your custom persona here...",
                "core_subject": "subject here"
            }}
        """
        try:
            response = self.ai.generate(
                system_prompt="You output ONLY valid JSON dictionaries.",
                user_prompt=meta_prompt,
                require_json=True,
            )
            return self.repair_json(response)
        except Exception as e:
            print(f"❌ Meta-Prompting Error: {e}")
            return {
                "system_prompt": f"You are a {expert_role} creating YouTube Shorts.",
                "core_subject": "General News",
            }

    # ─────────────────────────────────────────────
    # INTERNAL PIPELINE RUNNER
    # ─────────────────────────────────────────────

    def _run_script_pipeline(self, task, feedback=""):
        """
        Internal: runs the full narration → packaging → validate pipeline for a task.
        Accepts optional feedback string to bake user notes into the narration prompt.
        Returns validated data dict on success. Raises ValueError on any failure.
        """
        niche = task.get("niche", "general")
        source = task.get("content", "")[:3000]
        expert_role = self.get_expert_role(niche)
        meta_data = self.generate_meta_prompt(niche, source, expert_role)

        sys_prompt = meta_data.get("system_prompt", f"You are a {expert_role}.")
        core_subject = meta_data.get("core_subject", niche)
        pre_hashtags = task.get("hashtags", "#Shorts #Viral")
        pexels_style = task.get("pexels_style", "realistic")

        print(f"🧠 AI Director: Segmenting {niche.upper()} story...")

        narration_text = self.generate_narration(
            sys_prompt, expert_role, source, niche, feedback
        )
        if not narration_text:
            raise ValueError("Narration generation failed")
        print(f"✅ Narration complete. Sending to packaging agent...")

        data = self.generate_packaging(
            narration_text, core_subject, niche, pre_hashtags, pexels_style, feedback
        )
        if not data:
            raise ValueError("Packaging generation failed")

        is_valid, reason = self.validate_script(data)
        if not is_valid:
            raise ValueError(f"Script validation failed: {reason}")

        print(f"✅ Script validated successfully.")
        return data

    def _save_script_to_db(self, task, data):
        """Writes validated script data to DB and creates metadata file."""
        meta_filename = f"metadata_{task['_id']}.txt"
        with open(meta_filename, "w", encoding="utf-8") as f:
            f.write(f"TITLE: {data.get('title')}\nHASHTAGS: {data.get('hashtags')}")

        raw_tags = data.get("tags", [])
        formatted_tags = (
            ", ".join(raw_tags) if isinstance(raw_tags, list) else str(raw_tags)
        )

        self.db.collection.update_one(
            {"_id": task["_id"]},
            {
                "$set": {
                    "script_data": data["scenes"],
                    "title": data.get("title", task["title"]),
                    "ai_description": data.get("description"),
                    "ai_hashtags": data.get("hashtags"),
                    "ai_tags": formatted_tags,
                    "status": "scripted",
                }
            },
        )
        print("✅ Script saved to DB.")

    # ─────────────────────────────────────────────
    # INTERACTIVE METHODS — called by main.py
    # ─────────────────────────────────────────────

    def generate_script_for_task(self, task):
        """
        Generates a script for the given task dict WITHOUT saving to DB yet.
        Called by main.py interactive loop to generate a preview for user review.
        Returns the data dict on success, or None on failure.
        """
        try:
            return self._run_script_pipeline(task)
        except Exception as e:
            print(f"❌ Brain Error: {e}")
            return None

    def regenerate_with_feedback(self, task, feedback):
        """
        Re-runs the pipeline with user feedback baked into the narration prompt.
        Called by main.py when user rejects a script and provides improvement notes.
        Returns new data dict on success, or None on failure.
        """
        try:
            return self._run_script_pipeline(task, feedback=feedback)
        except Exception as e:
            print(f"❌ Regeneration Error: {e}")
            return None

    def approve_and_save(self, task, data):
        """
        Called by main.py after user approves a script.
        Saves the approved script to DB and marks task as scripted.
        """
        try:
            self._save_script_to_db(task, data)
            print("✅ Script Segmented! AI generated unique search arrays for visuals.")
        except Exception as e:
            print(f"❌ Save Error: {e}")

    # ─────────────────────────────────────────────
    # LEGACY AUTOMATED METHOD
    # ─────────────────────────────────────────────

    def generate_script(self):
        """
        Legacy automated mode — fetches the next pending task from DB and processes it.
        Used when running without interactive approval (e.g. scheduled/cron runs).
        """
        task = self.db.collection.find_one({"status": "pending"})
        if not task:
            print("📭 No pending tasks.")
            return

        try:
            data = self._run_script_pipeline(task)
            self._save_script_to_db(task, data)
            print("✅ Script Segmented! AI generated unique search arrays for visuals.")
        except Exception as e:
            print(f"❌ Brain Error: {e}")
