import json
import re
import os
from groq import Groq
from core.db_manager import DBManager
from dotenv import load_dotenv

load_dotenv()


class ScriptGenerator:
    def __init__(self):
        self.db = DBManager()
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    def get_expert_role(self, niche):
        role_map = {
            "comics": "highly energetic pop-culture and comic book expert",
            "space": "authoritative science and astronomy communicator",
            "mysteries": "suspenseful investigative narrator of the unknown",
            "tech_ai": "sharp futurist and technology analyst",
            "psychology": "insightful psychology and human behavior expert",
            "geography": "engaging geography and world-culture explorer",
            "worldnews": "professional and objective global news anchor",
            "home_decor": "creative interior designer and DIY renovation expert",
            "indian_history": "knowledgeable historian and captivating storyteller of India's past",
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
        if not (4 <= len(scenes) <= 6):
            return False, f"Wrong scene count: {len(scenes)}"

        for i, scene in enumerate(scenes):
            if not scene.get("text"):
                return False, f"Scene {i} missing text"
            if not scene.get("keywords") or not isinstance(scene["keywords"], list):
                return False, f"Scene {i} missing keywords"
            if scene.get("image_count", 0) not in [1, 2, 3]:
                return (
                    False,
                    f"Scene {i} has invalid image_count: {scene.get('image_count')}",
                )
            if len(scene["keywords"]) != scene["image_count"]:
                return (
                    False,
                    f"Scene {i}: keywords count ({len(scene['keywords'])}) doesn't match image_count ({scene.get('image_count')})",
                )

        return True, "OK"

    def generate_narration(self, sys_prompt, expert_role, source, target_lang, niche):
        print(f"✍️ Narration Writer: Crafting {target_lang.upper()} script...")

        prompt = f"""
            ROLE: {sys_prompt}
            TASK: You are a {expert_role} and a master of YouTube Shorts retention. Read the source material and write a highly informative, engaging, high-tension voiceover script. Explain complex topics in simple terms. Keep total length between 60-75 seconds of spoken narration.
            SOURCE: "{source}"

            RULES:
            1. HOOK: Scene 1 MUST open with a pattern-interrupt like "Stop scrolling...", "What if I told you...", or a bold shocking claim. No generic questions.
            2. TONE: Write the way people actually speak. Short punchy sentences. Use (..., —, !, ?) for voiceover rhythm and suspense. You may use words like "terrifying", "bizarre", "breakthrough" but NEVER invent or exaggerate facts.
            3. FACTS ONLY: No personal stories, no "I" statements, no motivational fluff. Facts, science, history, news only.
            4. LANGUAGE: Write entirely in {target_lang.upper()}. Use simple conversational language, NOT formal or academic. Keep English tech/business words (AI, Startup, Robot, etc.) as-is mixed naturally into sentences.
            5. STRUCTURE: Write exactly 4-6 scenes. Each scene = 7-8 seconds of spoken narration.
            6. FINAL SCENE: Must end with the exact phrase: "Please like, share, and subscribe!"

            OUTPUT FORMAT — plain numbered list, nothing else:
            Scene 1: [narration text]
            Scene 2: [narration text]
            Scene 3: [narration text]
            Scene 4: [narration text]
            Scene 5: [narration text]
            Scene 6: [narration text]
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": f"You are {sys_prompt}. Write ONLY the numbered scene list. No JSON, no extra commentary.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Narration Error: {e}")
            return None

    def generate_packaging(
        self, narration_text, core_subject, niche, target_lang, pre_hashtags
    ):
        print(f"📦 Packaging Agent: Generating keywords and metadata...")

        prompt = f"""
            TASK: You are a stock footage coordinator and SEO expert. Given the finished script scenes below, output a JSON object with visual keywords and metadata.

            FINISHED SCRIPT:
            {narration_text}

            KEYWORD RULES:
            - Every keyword must be 1-3 plain English nouns that describe a PHYSICAL, FILMABLE object or place.
            - Core subject anchor: "{core_subject}". At least one keyword per scene must physically relate to this.
            - Niche: "{niche}". If niche needs illustrated style (like "comics"), prefix keywords with "comic" or "animated".
            - NEVER use: "graphs", "charts", "news", "newspaper", "county", "area", "place", "energy" (too abstract).
            - STRICT NO DUPLICATE RULE: Scan ALL keywords across ALL scenes before finalizing. If a phrase appears more than once, replace the duplicate with a visually distinct alternative. "Oil Field" can appear ONCE maximum across the entire script.
            - VISUAL SPECIFICITY RULE: Each keyword must be specific enough that a photographer would know exactly what to film. BAD: "Energy", "Equipment", "Area". GOOD: "Oil Derrick", "Steel Pipeline", "Gas Pump".
            - LOCATION RULE: If the story is about a specific country or region, at least 2 keywords across the script must reflect the location visually (e.g., "Taiwan street", "Asian village", "East Asia city").
            - SCENE VARIETY RULE: Consecutive scenes must NOT share similar keywords. Alternate between close-up subjects and wide environment shots.
            - image_count rule: count the words in each scene's narration text.
                - Under 10 words = image_count: 1, exactly 1 keyword
                - 10-18 words = image_count: 2, exactly 2 keywords
                - 18+ words = image_count: 3, exactly 3 keywords
            - keywords array length MUST equal image_count exactly.

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
                        "keywords": ["English noun", "English noun"],
                        "image_count": 2
                    }}
                ]
            }}
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You output ONLY valid JSON dictionaries. Copy scene text exactly as given.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
                response_format={"type": "json_object"},
            )
            return self.repair_json(chat_completion.choices[0].message.content)
        except Exception as e:
            print(f"❌ Packaging Error: {e}")
            return None

    def generate_meta_prompt(self, niche, source_text, expert_role):
        print(f"🕵️‍♂️ AI Strategist: Analyzing '{niche}' news to build custom persona...")

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
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": meta_prompt}],
                model=self.model,
                response_format={"type": "json_object"},
            )
            return self.repair_json(chat_completion.choices[0].message.content)
        except Exception as e:
            print(f"❌ Meta-Prompting Error: {e}")
            return {
                "system_prompt": f"You are a {expert_role} creating YouTube Shorts.",
                "core_subject": "General News",  # 🟢 FIX: Clean string fallback
            }

    def generate_script(self):
        task = self.db.collection.find_one({"status": "pending"})
        if not task:
            print("📭 No pending tasks.")
            return

        niche = task.get("niche", "general")
        source = task.get("content", "")[:3000]
        source_url = task.get("source_url", "https://news.google.com")

        expert_role = self.get_expert_role(niche)
        meta_data = self.generate_meta_prompt(niche, source, expert_role)

        sys_prompt = meta_data.get("system_prompt", f"You are a {expert_role}.")
        core_subject = meta_data.get("core_subject", niche)
        pre_hashtags = task.get("hashtags", "#Shorts #Viral")
        target_lang = task.get("target_language", "English")

        try:
            print(f"🧠 Groq Director: Segmenting {niche.upper()} story...")

            # --- CALL 2A: Narration only ---
            narration_text = self.generate_narration(
                sys_prompt, expert_role, source, target_lang, niche
            )
            if not narration_text:
                raise ValueError("Narration generation failed")
            print(f"✅ Narration complete. Sending to packaging agent...")

            # --- CALL 2B: Keywords + metadata ---
            data = self.generate_packaging(
                narration_text, core_subject, niche, target_lang, pre_hashtags
            )
            if not data:
                raise ValueError("Packaging generation failed")

            # --- Validate ---
            is_valid, reason = self.validate_script(data)
            if not is_valid:
                raise ValueError(f"Script validation failed: {reason}")
            print(f"✅ Script validated successfully.")

            # --- Save to DB ---
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
            print("✅ Script Segmented! AI generated unique search arrays for visuals.")

        except Exception as e:
            print(f"❌ Brain Error: {e}")
