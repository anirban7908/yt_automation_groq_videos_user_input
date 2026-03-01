import requests
import feedparser
import random
import datetime
import re
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
           "space": {
                "rss_feeds": [
                    "https://www.space.com/feeds/all",
                    "https://universetoday.com/feed",
                    "https://phys.org/rss-feed/space-news/",
                    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
                    "https://spacenews.com/feed/",
                    "https://www.esa.int/rssfeed/Our_Activities/Space_News",
                ],
                "hashtags": "#Space #Astronomy #Universe #BlackHole #NASA #Cosmos #Astrophysics",
                "en_voice": "en-GB-RyanNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "mysteries": {
                "rss_feeds": [
                    "https://www.coasttocoastam.com/rss/",
                    "https://www.ancient-origins.net/rss.xml",
                    "https://www.unexplained-mysteries.com/rss/news.xml",
                    "https://mysteriousuniverse.org/feed/",
                    "https://anomalien.com/feed/",
                ],
                "hashtags": "#Mystery #Unsolved #Paranormal #Cryptid #Conspiracy #Creepy",
                "en_voice": "en-US-ChristopherNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            "tech_ai": {
                "rss_feeds": [
                    "https://www.theverge.com/rss/index.xml",
                    "https://techcrunch.com/feed/",
                    "https://venturebeat.com/category/ai/feed/",
                    "https://www.artificialintelligence-news.com/feed/",
                    "https://www.wired.com/feed/tag/ai/latest/rss",
                ],
                "hashtags": "#AI #ArtificialIntelligence #Cyberpunk #TechNews #FutureTech #Robotics",
                "en_voice": "en-US-GuyNeural",
                "hi_voice": "hi-IN-SwaraNeural",
            },
            "psychology": {
                "rss_feeds": [
                    "https://www.psychologytoday.com/us/front/feed",
                    "https://www.sciencedaily.com/rss/mind_brain/psychology.xml",
                    "https://www.psypost.org/feed/",
                    "https://neurosciencenews.com/neuroscience-topics/psychology/feed/",
                    "https://digest.bps.org.uk/feed/",
                ],
                "hashtags": "#Psychology #BodyLanguage #DarkPsychology #MindTricks #Manipulation #MentalHealth",
                "en_voice": "en-US-BrianNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            "geography": {
                "rss_feeds": [
                    "https://www.nationalgeographic.com/latest-stories/rss",
                    "https://www.atlasobscura.com/feeds/latest",
                    "https://www.earth.com/feed/",
                    "https://www.smithsonianmag.com/rss/travel/",
                    "https://geoawesomeness.com/feed/",
                ],
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
                    "https://yahoo.com/news/rss/world",
                ],
                "hashtags": "#WorldNews #GlobalNews #BreakingNews #CurrentEvents #Geopolitics #NewsUpdate",
                "en_voice": "en-US-SteffanNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
            "home_decor": {
                "rss_feeds": [
                    "https://www.apartmenttherapy.com/feed",
                    "https://design-milk.com/feed/",
                    "https://www.dezeen.com/interiors/feed/",
                    "https://ikeahackers.net/feed",
                    "https://www.housebeautiful.com/rss/all.xml",
                ],
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
                "hashtags": "#IndianHistory #AncientIndia #HistoryFacts #HistoryOfIndia #Historical #Bharat",
                "en_voice": "en-IN-PrabhatNeural",
                "hi_voice": "hi-IN-MadhurNeural",
            },
        }

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

    def pick_top_3_viral_topics(self, candidates, niche):
        titles = [f"{i}. {c['title']}" for i, c in enumerate(candidates)]
        titles_text = "\n".join(titles)

        prompt = f"""
        TASK: Pick THREE headlines that have the highest potential to go VIRAL as YouTube Shorts.
        NICHE: {niche}
        
        CRITICAL RULES: 
        1. Only select FACTUAL, INFORMATIVE, or MYSTERIOUS topics (e.g., scientific discoveries, historical events, weird geography).
        2. DO NOT pick opinion pieces, travel diaries, personal interviews, or motivational stories.
        
        HEADLINES:
        {titles_text}
        
        OUTPUT FORMAT: Return ONLY a JSON dictionary with a key "indices" containing exactly 3 integer indices. Example: {{"indices": [5, 12, 2]}}
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
            import json

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

    def extract_full_article(self, url):
        """Visits the webpage and extracts all paragraph text bypassing anti-bot walls."""
        print(f"      📖 Deep Reading full article from: {url}")
        try:
            import cloudscraper

            # Create a scraper that perfectly mimics a standard Windows Desktop Chrome user
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )

            # Use the new scraper instead of standard 'requests'
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

    def scrape_targeted_niche(self, forced_slot=None):
        slot = forced_slot if forced_slot else self.get_time_slot()
        used_niches = self.db.get_used_niches_today()
        all_niches = set(self.MASTER_NICHES.keys())

        available_niches = list(all_niches - used_niches)
        if not available_niches:
            available_niches = list(all_niches)

        selected_niche = random.choice(available_niches)
        niche_data = self.MASTER_NICHES[selected_niche]
        sources = niche_data["rss_feeds"]

        print(
            f"🎯 Dynamic Strategy Active: Selected '{selected_niche.upper()}' for {slot.upper()} slot."
        )

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
            return

        attempts, max_tries = 0, 4
        while attempts < max_tries and len(candidates) >= 3:
            top_3 = self.pick_top_3_viral_topics(candidates, selected_niche)
            unique_winners = [
                c for c in top_3 if not self.db.task_exists(c["title"], c["link"])
            ]

            for c in top_3:
                if c in candidates:
                    candidates.remove(c)

            if unique_winners:
                final_winner = random.choice(unique_winners)
                print(
                    f"      🎉 Unique Topic Secured: '{final_winner['title'][:40]}...'"
                )

                full_content = self.extract_full_article(final_winner["link"])
                if not full_content:
                    print("      ⚠️ Deep Read failed, falling back to RSS summary.")
                    raw_summary = final_winner["summary"]
                    import re

                    clean_summary = re.sub(r"<[^>]+>", "", raw_summary)
                    full_content = clean_summary[:5000]

                if slot in ["mid_night", "4_am", "8_am"]:
                    target_lang = "English"
                    selected_voice = niche_data.get("en_voice", "en-US-GuyNeural")
                else:
                    target_lang = "Hindi"
                    selected_voice = niche_data.get("hi_voice", "hi-IN-MadhurNeural")

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
                        "voice": selected_voice,  # 🟢 Dynamically selected voice
                        "target_language": target_lang,  # 🟢 Pass the language to the DB
                    },
                )
                return
            attempts += 1
        print("❌ Could not find a unique viral topic.")
