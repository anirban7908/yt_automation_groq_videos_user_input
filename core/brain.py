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
        }
        return role_map.get(niche, "highly informative educator")

    def repair_json(self, json_str):
        try:
            json_str = re.sub(r"^[^{]*", "", json_str)
            json_str = re.sub(r"[^}]*$", "", json_str)
            return json.loads(json_str)
        except:
            return None

    def generate_meta_prompt(self, niche, source_text, expert_role):
        print(f"🕵️‍♂️ AI Strategist: Analyzing '{niche}' news to build custom persona...")

        meta_prompt = f"""
            TASK: You are a Master YouTube Shorts Strategist. 
            I am going to give you a raw news story about {niche}.
            You need to invent a highly specific, engaging Persona/Role for the scriptwriter, and identify the core subject of the video.
            
            NEWS STORY: "{source_text[:1500]}"
            
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
        pre_hashtags = task.get("predefined_hashtags", "#Shorts #Viral")

        # 🟢 FIX: Numbering correctly ordered and Anchor Rule properly integrated
        prompt = f"""
            ROLE: {sys_prompt}
            TASK: You are a {expert_role} and a master of YouTube Shorts retention. Read the provided source material and write a highly informative, engaging, high-tension script. You MUST explain complex topics or news in simple terms so a general audience can learn something new. If the news is boring, make it sound interesting and crispy. Keep the script between 60 seconds minimum and 75 seconds maximum.
            SOURCE: "{source}"
            
            REQUIREMENTS:
            1. **THE HOOK (CRITICAL)**: The first sentence MUST be a pattern-interrupt. Start with a phrase like "What if I told you..." or make a bold, shocking, or mysterious claim to immediately stop the viewer from scrolling. Do NOT ask generic theoretical questions.
            
            2. **TONE, STORYTELLING & PACING (CRITICAL FOR VOICEOVER)**: 
                - Follow your assigned ROLE strictly. Write the way people actually speak.
                - Do not sound like Wikipedia. Use short, punchy sentences.
                - **OPTIMIZED RULE**: Transform dry or boring news into a highly captivating, fast-paced narrative. Use creative phrasing and analogies to explain facts, but NEVER invent or exaggerate the underlying data.
                - Build tension using words like "terrifying," "bizarre," "hidden," or "breakthrough."
                - You MUST use heavy punctuation (..., —, ?, !) to force the AI voice engine to pause, breathe, build suspense, and sound human.
            
            3. **STRICTLY FACTUAL (NO FLUFF)**: This is an educational/news channel. 
                - DO NOT include personal stories, "I" statements, or motivational fluff from the source. 
                - Extract ONLY hard facts, history, science, or news updates. If the article is an interview, ignore the person and explain the subject matter objectively.
                

            4. **SCENE STRUCTURE**: Break the story into 4-6 distinct SCENES. Each scene must be 7 to 8 seconds of spoken 'text'.
            
            5. **VISUALS & B-ROLL (THE "DUMB SEARCH" & ANCHOR RULES)**:
                - Stock video sites (like Pexels) are extremely literal. They DO NOT understand abstract concepts, double meanings, data, or sci-fi.
                - **THE DOUBLE-MEANING & DATA TRAP**: NEVER use words that have human equivalents (e.g., "spots/spotless" will pull cleaning/skincare videos). NEVER search for "graphs", "charts", or "news updates" (it will pull office supplies and newspapers).
                - You MUST translate concepts into BASIC, PHYSICAL, CINEMATIC scenery.
                    - BAD: "Sunspot activity graph", "Spotless sun surface", "Economy chart", "Fermi paradox"
                    - GOOD: "Cinematic glowing sun in space", "Telescope pointing at night sky", "Wall street building", "Dark creepy forest"
                - **THE ANCHOR**: The core subject of this video is "{core_subject}". Every single visual search keyword MUST explicitly include this subject or tie directly to it physically to avoid random off-topic videos.
                - Pace visuals based on scene length:
                    - SHORT scene (under 10 words): EXACTLY 1 search phrase ('image_count': 1).
                    - MODERATE scene (10-18 words): EXACTLY 2 search phrases ('image_count': 2).
                    - LONG scene (18+ words): EXACTLY 3 search phrases ('image_count': 3).
                - **NO DUPLICATES**: NEVER repeat a search phrase. Every phrase must be 100% unique.
            
            6. **METADATA & SEO**:
                - 'title': MUST be "Clickbait" style. High curiosity. Max 50 chars.
                - 'description': 3-sentence summary + call to action.
                - 'hashtags': Use these exactly: {pre_hashtags}, and add 5 more specific ones.
                - 'tags': An array of 10-15 highly searched SEO keywords.
            
            7. **CTA & OUTRO**: 
                - The FINAL SCENE must drive an explicit call to action ending with the exact phrase: "Please like, share, and subscribe!"
                - **CRITICAL**: You MUST still output the 'keywords' array and 'image_count' for this final scene. Apply the "Dumb Search Rule" tied to the "{core_subject}" anchor, completely ignoring the word "subscribe" to prevent makeup vlogger videos. Do not loop the script; end naturally.
            
            OUTPUT FORMAT (JSON ONLY):
            {{
                "title": "Viral Title Here",
                "description": "Short summary...",
                "hashtags": "#Tag1 #Tag2...",
                "tags": ["keyword1", "keyword2", "keyword3"],
                "scenes": [
                    {{
                        "text": "Your narration here...",
                        "keywords": ["Dynamic phrase 1", "Dynamic phrase 2"],
                        "image_count": 2
                    }}
                ]
            }}
        """

        try:
            print(f"🧠 Groq Director: Segmenting {niche.upper()} story...")
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You output ONLY valid JSON dictionaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
                response_format={"type": "json_object"},
            )

            response_content = chat_completion.choices[0].message.content
            data = self.repair_json(response_content)

            if not data or "scenes" not in data:
                raise ValueError("Invalid JSON structure from AI")

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
