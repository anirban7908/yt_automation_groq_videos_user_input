import requests
import feedparser
import random
import datetime
import re
import json
import os
from groq import Groq
from core.db_manager import DBManager
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()


class NewsScraper:
    def __init__(self):
        self.db = DBManager()
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

        self.MASTER_NICHES = {
            # ════════════════════════════════════════════════════════
            # KEPT NICHES — RSS fixed, pexels_style added
            # ════════════════════════════════════════════════════════
            "space": {
                "rss_feeds": [
                    "https://www.space.com/feeds/all",
                    "https://universetoday.com/feed",
                    "https://phys.org/rss-feed/space-news/",
                    "https://www.nasa.gov/feeds/iotd-feed/",
                    "https://spacenews.com/feed/",
                    "https://scitechdaily.com/feed/",
                ],
                "pexels_style": "realistic",
                "hashtags": "#Space #Astronomy #Universe #BlackHole #NASA #Cosmos #Astrophysics",
                "en_voice": "en-GB-RyanNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "tech_ai": {
                "rss_feeds": [
                    "https://www.theverge.com/rss/index.xml",
                    "https://techcrunch.com/feed/",
                    "https://venturebeat.com/category/ai/feed/",
                    "https://www.artificialintelligence-news.com/feed/",
                    "https://www.wired.com/feed/tag/ai/latest/rss",
                ],
                "pexels_style": "futuristic",
                "hashtags": "#AI #ArtificialIntelligence #Cyberpunk #TechNews #FutureTech #Robotics",
                "en_voice": "en-US-GuyNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "psychology": {
                "rss_feeds": [
                    "https://www.sciencedaily.com/rss/mind_brain/psychology.xml",
                    "https://www.psypost.org/feed/",
                    "https://neurosciencenews.com/neuroscience-topics/psychology/feed/",
                    "https://digest.bps.org.uk/feed/",
                    "https://www.apa.org/news/psycport/psycport.rss",
                ],
                "pexels_style": "human",
                "hashtags": "#Psychology #BodyLanguage #DarkPsychology #MindTricks #Manipulation #MentalHealth",
                "en_voice": "en-US-BrianNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            "geography": {
                "rss_feeds": [
                    "https://www.atlasobscura.com/feeds/latest",
                    "https://www.earth.com/feed/",
                    "https://www.smithsonianmag.com/rss/travel/",
                    "https://geoawesomeness.com/feed/",
                    "https://www.lonelyplanet.com/feed",
                ],
                "pexels_style": "location",
                "hashtags": "#Geography #HiddenPlaces #AtlasObscura #Forbidden #TravelFacts",
                "en_voice": "en-AU-WilliamNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "worldnews": {
                "rss_feeds": [
                    "http://feeds.bbci.co.uk/news/world/rss.xml",
                    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
                    "https://www.aljazeera.com/xml/rss/all.xml",
                    "https://feeds.npr.org/1004/rss.xml",
                    "https://feeds.reuters.com/reuters/worldNews",
                ],
                "pexels_style": "documentary",
                "hashtags": "#WorldNews #GlobalNews #BreakingNews #CurrentEvents #Geopolitics #NewsUpdate",
                "en_voice": "en-US-SteffanNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            "home_decor": {
                "rss_feeds": [
                    "https://www.apartmenttherapy.com/feed",
                    "https://design-milk.com/feed/",
                    "https://www.dezeen.com/interiors/feed/",
                    "https://www.housebeautiful.com/rss/all.xml",
                    "https://www.houzz.com/ideabooks/rss",
                ],
                "pexels_style": "interior",
                "hashtags": "#HomeDecor #InteriorDesign #Renovation #DIYHome #HouseMakeover #DesignInspo",
                "en_voice": "en-US-JennyNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "indian_history": {
                "rss_feeds": [
                    "https://indianexpress.com/section/research/feed/",
                    "https://www.thehindu.com/society/history/feeder/default.rss",
                    "https://theprint.in/past-forward/feed/",
                    "https://www.livehistoryindia.com/feed/",
                    "https://www.smithsonianmag.com/rss/history/",
                ],
                "pexels_style": "historical",
                "hashtags": "#IndianHistory #AncientIndia #HistoryFacts #HistoryOfIndia #Historical #Bharat",
                "en_voice": "en-IN-PrabhatNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            # ════════════════════════════════════════════════════════
            # NEW VIRAL NICHES
            # ════════════════════════════════════════════════════════
            "science_facts": {
                "rss_feeds": [
                    "https://www.sciencedaily.com/rss/top/science.xml",
                    "https://www.zmescience.com/feed/",
                    "https://scitechdaily.com/feed/",
                    "https://www.newscientist.com/feed/home/",
                    "https://feeds.feedburner.com/sciencealert-latestnews",
                ],
                "pexels_style": "nature",
                "hashtags": "#ScienceFacts #DidYouKnow #MindBlowing #Science #Facts #Educational",
                "en_voice": "en-GB-RyanNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "health_wellness": {
                "rss_feeds": [
                    "https://www.sciencedaily.com/rss/health_medicine/",
                    "https://www.medicalnewstoday.com/rss/medicalnewstoday.xml",
                    "https://www.healthline.com/rss/",
                    "https://feeds.webmd.com/rss/rss.aspx?RSSSource=RSS_PUBLIC",
                    "https://www.who.int/rss-feeds/news-english.xml",
                ],
                "pexels_style": "medical",
                "hashtags": "#Health #Wellness #HealthFacts #MedicalFacts #BodyFacts #HealthTips",
                "en_voice": "en-US-JennyNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "animals_nature": {
                "rss_feeds": [
                    "https://www.sciencedaily.com/rss/plants_animals/",
                    "https://feeds.nationalgeographic.com/ng/News/News_Main",
                    "https://www.livescience.com/feeds/all",
                    "https://insider.si.edu/category/animals/feed/",
                    "https://www.earth.com/feed/",
                ],
                "pexels_style": "wildlife",
                "hashtags": "#Animals #Wildlife #Nature #WildAnimals #AnimalFacts #NatureFacts",
                "en_voice": "en-AU-WilliamNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "finance_economy": {
                "rss_feeds": [
                    "https://feeds.reuters.com/reuters/businessNews",
                    "https://feeds.bloomberg.com/markets/news.rss",
                    "https://www.marketwatch.com/rss/topstories",
                    "https://economictimes.indiatimes.com/rssfeedsdefault.cms",
                    "https://www.businessinsider.com/rss",
                ],
                "pexels_style": "business",
                "hashtags": "#Finance #Economy #MoneyFacts #StockMarket #Investment #FinanceFacts",
                "en_voice": "en-US-GuyNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            "bizarre_facts": {
                "rss_feeds": [
                    "https://www.zmescience.com/feed/",
                    "https://www.atlasobscura.com/feeds/latest",
                    "https://www.mentalfloss.com/rss.xml",
                    "https://www.livescience.com/feeds/all",
                    "https://www.odditycentral.com/feed",
                ],
                "pexels_style": "nature",
                "hashtags": "#BizarreFacts #WeirdFacts #DidYouKnow #MindBlowing #StrangeFacts #Shocking",
                "en_voice": "en-US-ChristopherNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            "history_world": {
                "rss_feeds": [
                    "https://www.smithsonianmag.com/rss/history/",
                    "https://www.ancient-origins.net/rss.xml",
                    "https://www.historyextra.com/feed/",
                    "https://www.historyhit.com/feed/",
                    "https://www.thehistoryblog.com/feed",
                ],
                "pexels_style": "historical",
                "hashtags": "#WorldHistory #HistoryFacts #AncientHistory #HistoricalFacts #History #Civilization",
                "en_voice": "en-GB-RyanNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
        }

    # ─────────────────────────────────────────────
    # TIME SLOT LOGIC
    # ─────────────────────────────────────────────

    def get_time_slot(self):
        h = datetime.datetime.now().hour
        if 0 <= h < 4:
            return "mid_night"
        elif 4 <= h < 8:
            return "4_am"
        elif 8 <= h < 12:
            return "8_am"
        elif 12 <= h < 16:
            return "mid_day"
        elif 16 <= h < 20:
            return "4_pm"
        else:
            return "8_pm"

    def _get_language_for_slot(self, slot, niche_data):
        """
        Centralized language + voice selection.
        English for early morning slots, Hindi for afternoon/evening.
        """
        english_slots = ["mid_night", "4_am", "8_am"]
        if slot in english_slots:
            return "English", niche_data.get("en_voice", "en-US-GuyNeural")
        else:
            return "Hindi", niche_data.get("hi_voice", "hi-IN-MadhurNeural")

    # ─────────────────────────────────────────────
    # RSS FETCHER
    # ─────────────────────────────────────────────

    def fetch_rss(self, url):
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            print(f"      🔗 Fetching: {url}")
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                entries = feedparser.parse(r.content).entries[:10]
                if entries:
                    print(f"         ✅ Found {len(entries)} articles.")
                    return entries
        except:
            pass
        return []

    # ─────────────────────────────────────────────
    # AI TOPIC PICKER
    # ─────────────────────────────────────────────

    def pick_top_3_viral_topics(self, candidates, niche):
        """
        Uses Groq to pick the 3 most viral-worthy headlines
        from a pool of RSS candidates for the given niche.
        """
        titles = [f"{i}. {c['title']}" for i, c in enumerate(candidates)]
        titles_text = "\n".join(titles)

        prompt = f"""
            TASK: Pick THREE headlines with the highest potential to go VIRAL as YouTube Shorts.
            NICHE: {niche}

            SELECTION RULES:
            1. Prefer FACTUAL, SURPRISING, or EDUCATIONAL topics — scientific discoveries,
            historical revelations, weird facts, health breakthroughs, financial insights,
            animal behavior, geography oddities, or major world events.
            2. DO NOT pick: opinion pieces, personal interviews, travel diaries,
            product reviews, motivational stories, or listicles without substance.
            3. For 'bizarre_facts' and 'science_facts': prioritize the most surprising/shocking facts.
            4. For 'finance_economy': prioritize stories with real numbers and consequences.
            5. For 'animals_nature': prioritize unusual animal behavior or new species discoveries.
            6. For 'history_world' and 'indian_history': prioritize newly discovered or little-known facts.

            HEADLINES:
            {titles_text}

            OUTPUT FORMAT: Return ONLY a JSON dict with key "indices" containing exactly 3 integers.
            Example: {{"indices": [5, 12, 2]}}
        """
        try:
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
            response_data = json.loads(
                chat_completion.choices[0].message.content.strip()
            )
            indices = response_data.get("indices", [])
            return [
                candidates[i]
                for i in indices[:3]
                if isinstance(i, int) and 0 <= i < len(candidates)
            ]
        except:
            return random.sample(candidates, min(3, len(candidates)))

    # ─────────────────────────────────────────────
    # ARTICLE EXTRACTOR
    # ─────────────────────────────────────────────

    def extract_full_article(self, url):
        """Visits the webpage and extracts paragraph text bypassing anti-bot walls."""
        print(f"      📖 Deep Reading full article from: {url}")
        try:
            import cloudscraper

            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
            res = scraper.get(url, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            paragraphs = soup.find_all("p")
            full_text = " ".join([p.get_text() for p in paragraphs])

            if len(full_text) < 200:
                return None

            return full_text[:5000]

        except Exception as e:
            print(f"      ❌ Failed to read full article: {e}")
            return None

    # ─────────────────────────────────────────────
    # MANUAL IDEA REFINER (used by main.py)
    # ─────────────────────────────────────────────

    def refine_user_idea(self, topic, content, feedback=""):
        """
        Takes a user's raw topic/content and uses Groq to refine it
        into a clean, factual article-style source text for brain.py.
        Called by main.py in manual mode.
        """
        print(f"      🧠 Refining idea: '{topic}'...")

        feedback_section = (
            f"\nPREVIOUS FEEDBACK TO ADDRESS: {feedback}" if feedback else ""
        )

        prompt = f"""
            TASK: You are a research assistant. A user wants to make a YouTube Short about the following topic.
            Rewrite and expand their idea into a clean, factual, well-structured article (300-500 words)
            that a scriptwriter can use as source material.

            TOPIC: {topic}
            USER'S IDEA: {content}{feedback_section}

            RULES:
            1. Only include facts — no opinions, no fluff, no personal stories.
            2. Structure it clearly: background → key facts → significance.
            3. Use simple language. Avoid jargon.
            4. Do NOT add a title or headline — just the body text.
            5. If the idea is too vague, make reasonable factual assumptions and expand on them.

            OUTPUT: Plain text article only. No JSON, no bullet points, no headers.
        """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a factual research writer. Output plain text only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model=self.model,
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"      ❌ Idea refinement failed: {e}")
            return content  # Fall back to original if AI fails

    # ─────────────────────────────────────────────
    # MAIN SCRAPER ORCHESTRATOR
    # ─────────────────────────────────────────────

    def scrape_targeted_niche(self, forced_slot=None):
        slot = forced_slot if forced_slot else self.get_time_slot()
        used_niches = self.db.get_used_niches_today()
        all_niches = set(self.MASTER_NICHES.keys())

        available_niches = list(all_niches - used_niches)
        if not available_niches:
            print("⚠️ All niches used today. Resetting pool.")
            available_niches = list(all_niches)

        selected_niche = random.choice(available_niches)
        niche_data = self.MASTER_NICHES[selected_niche]
        sources = niche_data["rss_feeds"]

        print(
            f"🎯 Dynamic Strategy Active: Selected '{selected_niche.upper()}' for {slot.upper()} slot."
        )

        # 🟢 Centralized language + voice selection
        target_lang, selected_voice = self._get_language_for_slot(slot, niche_data)
        print(f"🌐 Language: {target_lang} | Voice: {selected_voice}")

        candidates = []
        for url in sources:
            for e in self.fetch_rss(url):
                if hasattr(e, "title"):
                    candidates.append(
                        {
                            "title": e.title,
                            "summary": getattr(e, "summary", e.title)[:3000],
                            "link": getattr(e, "link", ""),
                            "niche": selected_niche,
                        }
                    )

        if not candidates:
            print(f"❌ No RSS candidates found for '{selected_niche}'.")
            return

        attempts, max_tries = 0, 4
        while attempts < max_tries and len(candidates) >= 3:
            top_3 = self.pick_top_3_viral_topics(candidates, selected_niche)
            unique_winners = [
                c for c in top_3 if not self.db.task_exists(c["title"], c["link"])
            ]

            # Remove tried candidates from pool regardless of outcome
            for c in top_3:
                if c in candidates:
                    candidates.remove(c)

            if unique_winners:
                final_winner = random.choice(unique_winners)
                print(f"      🎉 Unique Topic Secured: '{final_winner['title'][:60]}'")

                # Try deep article extraction first
                full_content = self.extract_full_article(final_winner["link"])
                if not full_content:
                    print("      ⚠️ Deep Read failed, falling back to RSS summary.")
                    clean_summary = re.sub(r"<[^>]+>", "", final_winner["summary"])
                    full_content = clean_summary[:5000]

                self.db.add_task(
                    title=final_winner["title"],
                    content=full_content,
                    source=f"{selected_niche.upper()}",
                    status="pending",
                    extra_data={
                        "niche": selected_niche,
                        "niche_slot": slot,
                        "source_url": final_winner["link"],
                        "hashtags": niche_data.get("hashtags", "#Shorts #Viral"),
                        "pexels_style": niche_data.get(
                            "pexels_style", "realistic"
                        ),  # 🟢 Now passed to DB
                        "voice": selected_voice,
                        "target_language": target_lang,
                    },
                )
                return

            attempts += 1

        print(
            f"❌ Could not find a unique viral topic for '{selected_niche}' after {max_tries} attempts."
        )
