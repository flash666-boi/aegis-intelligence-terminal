from __future__ import annotations
import hashlib
import html
import io
import json
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "news.db"
CASES_PATH = DATA_DIR / "cyber_cases.json"
DATA_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------- #
# Streamlit page config (must run before any other st.* call)
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Aegis | Global Intelligence Terminal",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-refresh every 60 seconds. The rerun re-evaluates the live clock,
# status pulses, and triggers a background feed re-check when due.
st_autorefresh(interval=60_000, key="auto_refresh")

# --------------------------------------------------------------------------- #
# Theme — modern glassmorphism with animated accents
# --------------------------------------------------------------------------- #
st.markdown(
    """
<style>
:root {
  --bg-0:#060912; --bg-1:#0a1018; --bg-2:#0e1626;
  --panel:rgba(20,28,44,.72);
  --panel-solid:#121a2c;
  --line:rgba(86,110,145,.25);
  --line-strong:rgba(120,150,195,.40);
  --muted:#8ea0bc;
  --fg:#e8eef7;
  --cyan:#4dd0e1; --cyan-glow:rgba(77,208,225,.40);
  --amber:#ffb74d; --green:#66ddaa;
  --red:#ff6b6b; --violet:#b39ddb;
}

/* Animated base gradient */
.stApp {
  background:linear-gradient(125deg,#060912 0%,#0a1018 35%,#0e1626 70%,#060912 100%);
  background-size:400% 400%;
  animation:gradientShift 22s ease-in-out infinite;
  color:var(--fg);
}
@keyframes gradientShift {
  0%{background-position:0% 50%}
  50%{background-position:100% 50%}
  100%{background-position:0% 50%}
}
/* Soft radial accents that breathe */
.stApp::before {
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
  background:
    radial-gradient(800px circle at 10% 10%,rgba(77,208,225,.08),transparent 60%),
    radial-gradient(900px circle at 90% 90%,rgba(255,183,77,.06),transparent 60%);
  animation:pulseGlow 12s ease-in-out infinite alternate;
}
@keyframes pulseGlow { 0%{opacity:.55} 100%{opacity:1} }

/* Layout shell */
.block-container { padding-top:1.4rem; max-width:1680px; z-index:1; position:relative; }

/* Glass cards */
.glass-card {
  background:linear-gradient(180deg,rgba(20,28,44,.78),rgba(14,22,38,.72));
  border:1px solid var(--line);
  border-radius:14px; padding:16px 18px; margin:10px 0;
  backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
  box-shadow:0 4px 24px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.04);
  transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease;
  position:relative; overflow:hidden;
  animation:fadeInUp .45s ease both;
}
.glass-card:hover {
  transform:translateY(-2px);
  border-color:var(--line-strong);
  box-shadow:0 10px 36px rgba(0,0,0,.5),0 0 0 1px rgba(77,208,225,.15);
}
.glass-card::after {
  content:""; position:absolute; inset:0;
  background:linear-gradient(120deg,transparent 35%,rgba(77,208,225,.06) 50%,transparent 65%);
  opacity:0; transition:opacity .4s ease; pointer-events:none;
}
.glass-card:hover::after { opacity:1; }
@keyframes fadeInUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }

/* Pills / chips */
.pill {
  display:inline-block; padding:3px 9px; border-radius:99px;
  background:linear-gradient(180deg,rgba(77,208,225,.18),rgba(77,208,225,.08));
  border:1px solid rgba(77,208,225,.35); color:#a7e9f2;
  font-size:.72rem; font-weight:600; letter-spacing:.02em; margin-right:6px;
}
.pill-cat-Technology   { background:rgba(77,208,225,.15);  border-color:rgba(77,208,225,.40); color:#a7e9f2; }
.pill-cat-Politics     { background:rgba(255,183,77,.15);  border-color:rgba(255,183,77,.40); color:#ffd9a0; }
.pill-cat-Intelligence { background:rgba(179,157,219,.18); border-color:rgba(179,157,219,.40); color:#d4c1ec; }
.pill-cat-Business     { background:rgba(102,221,170,.15); border-color:rgba(102,221,170,.40); color:#a8eec9; }
.pill-cat-Finance      { background:rgba(255,207,90,.15);  border-color:rgba(255,207,90,.40); color:#ffe39e; }
.pill-cat-Cyber        { background:rgba(255,107,107,.15); border-color:rgba(255,107,107,.40); color:#ffb3b3; }
.pill-cat-World        { background:rgba(160,180,215,.15);border-color:rgba(160,180,215,.40); color:#c9d6ea; }

/* Live clock & status dots */
.live-clock {
  font-family:'JetBrains Mono','Fira Code','Consolas',monospace;
  font-size:.92rem; color:var(--cyan); letter-spacing:.04em;
  display:flex; align-items:center; gap:8px;
}
.live-dot {
  width:8px; height:8px; border-radius:50%; background:var(--green);
  box-shadow:0 0 0 0 rgba(102,221,170,.7);
  animation:pulse-dot 1.4s infinite;
}
@keyframes pulse-dot {
  0%  { box-shadow:0 0 0 0 rgba(102,221,170,.7); }
  70% { box-shadow:0 0 0 9px rgba(102,221,170,0); }
  100%{ box-shadow:0 0 0 0 rgba(102,221,170,0); }
}
.refresh-ring {
  display:inline-block; width:14px; height:14px;
  border:2px solid rgba(77,208,225,.25); border-top-color:var(--cyan);
  border-radius:50%; animation:spin .9s linear infinite; vertical-align:middle;
}
@keyframes spin { to { transform:rotate(360deg); } }

/* Metric tiles */
[data-testid="stMetric"] {
  background:linear-gradient(180deg,rgba(20,28,44,.75),rgba(14,22,38,.6));
  border:1px solid var(--line); padding:14px 16px !important; border-radius:14px;
  backdrop-filter:blur(8px);
  transition:border-color .2s ease,transform .2s ease;
}
[data-testid="stMetric"]:hover { border-color:var(--line-strong); transform:translateY(-2px); }
[data-testid="stMetric"] label {
  color:var(--muted) !important; font-size:.78rem !important;
  text-transform:uppercase; letter-spacing:.06em;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color:var(--fg) !important; font-weight:700 !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#080d18 0%,#0b121f 100%);
  border-right:1px solid var(--line);
}
section[data-testid="stSidebar"] .stRadio > label,
section[data-testid="stSidebar"] .stSelectbox > label,
section[data-testid="stSidebar"] .stTextInput > label {
  color:var(--fg) !important;
}

/* Buttons */
.stButton > button {
  background:linear-gradient(180deg,rgba(77,208,225,.18),rgba(77,208,225,.08));
  border:1px solid rgba(77,208,225,.4); color:#a7e9f2;
  border-radius:10px; font-weight:600; transition:all .2s ease;
}
.stButton > button:hover {
  background:linear-gradient(180deg,rgba(77,208,225,.3),rgba(77,208,225,.15));
  border-color:var(--cyan); color:#d4f5fa;
  box-shadow:0 0 20px rgba(77,208,225,.25); transform:translateY(-1px);
}
.stButton > button:active { transform:translateY(0); }
/* Danger / amber button variant */
.danger-btn > button {
  background:linear-gradient(180deg,rgba(255,107,107,.18),rgba(255,107,107,.08)) !important;
  border-color:rgba(255,107,107,.4) !important; color:#ffb3b3 !important;
}
.danger-btn > button:hover {
  background:linear-gradient(180deg,rgba(255,107,107,.3),rgba(255,107,107,.15)) !important;
  box-shadow:0 0 20px rgba(255,107,107,.25) !important;
}

/* Headings */
h1,h2,h3 { letter-spacing:-.025em; color:var(--fg); }
h1 {
  background:linear-gradient(120deg,#e8eef7 0%,#4dd0e1 50%,#ffb74d 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text;
}

/* Misc text */
.small-muted { color:var(--muted); font-size:.85rem; }
.summary-text { color:#c2cee0; line-height:1.55; }
hr { border-color:var(--line); }

/* Custom scrollbar */
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-track { background:#060912; }
::-webkit-scrollbar-thumb { background:linear-gradient(180deg,#1c2b3f,#111827); border-radius:6px; border:2px solid #060912; }
::-webkit-scrollbar-thumb:hover { background:var(--cyan); }

/* Notes cards */
.note-card {
  background:linear-gradient(180deg,rgba(20,28,44,.78),rgba(14,22,38,.72));
  border:1px solid var(--line); border-left:3px solid var(--cyan);
  border-radius:12px; padding:14px 16px; margin:8px 0;
  backdrop-filter:blur(10px); transition:all .2s ease;
}
.note-card.pinned {
  border-left-color:var(--amber);
  background:linear-gradient(180deg,rgba(40,32,18,.62),rgba(28,22,14,.6));
}
.note-card:hover { border-color:var(--line-strong); transform:translateX(2px); }
.note-title { font-weight:700; font-size:1.02rem; color:var(--fg); margin-bottom:4px; }
.note-content { color:#c2cee0; line-height:1.55; font-size:.92rem; white-space:pre-wrap; }
.note-meta { color:var(--muted); font-size:.78rem; margin-top:8px; }
.note-tag {
  display:inline-block; padding:2px 8px; border-radius:99px;
  background:rgba(120,150,195,.15); color:#a8b6cf;
  font-size:.72rem; margin-right:4px;
}

/* Sidebar hero block */
.sidebar-hero {
  background:linear-gradient(135deg,rgba(77,208,225,.12),rgba(255,183,77,.06));
  border:1px solid rgba(77,208,225,.25);
  border-radius:14px; padding:14px 16px; margin-bottom:14px;
}
.sidebar-hero h2 {
  background:linear-gradient(120deg,#e8eef7,#4dd0e1);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}

/* Status pills in sidebar */
.status-pill {
  display:inline-flex; align-items:center; gap:6px;
  padding:4px 10px; border-radius:99px; font-size:.78rem;
  background:rgba(102,221,170,.12); border:1px solid rgba(102,221,170,.35);
  color:#a8eec9;
}
.status-pill.warn { background:rgba(255,183,77,.12); border-color:rgba(255,183,77,.35); color:#ffd9a0; }
.status-pill.bad  { background:rgba(255,107,107,.12); border-color:rgba(255,107,107,.35); color:#ffb3b3; }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap:6px; }
.stTabs [data-baseweb="tab"] {
  background:rgba(20,28,44,.55); border:1px solid var(--line);
  border-radius:10px 10px 0 0; padding:8px 14px; color:var(--muted);
}
.stTabs [aria-selected="true"] {
  background:linear-gradient(180deg,rgba(77,208,225,.18),rgba(77,208,225,.06)) !important;
  color:#a7e9f2 !important; border-color:rgba(77,208,225,.4) !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Public RSS/Atom feeds. Availability, feed URLs, and publisher terms can
# change. Each entry: (publisher, url, default category fallback).
# --------------------------------------------------------------------------- #
FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "World"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "Business"),
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "Technology"),
    ("BBC Politics", "https://feeds.bbci.co.uk/news/politics/rss.xml", "Politics"),
    ("The Guardian World", "https://www.theguardian.com/world/rss", "World"),
    ("The Guardian Politics", "https://www.theguardian.com/politics/rss", "Politics"),
    ("The Guardian Business", "https://www.theguardian.com/business/rss", "Business"),
    ("The Guardian Technology", "https://www.theguardian.com/technology/rss", "Technology"),
    ("The Guardian Environment", "https://www.theguardian.com/environment/rss", "World"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml", "World"),
    ("NPR Politics", "https://feeds.npr.org/1014/rss.xml", "Politics"),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml", "Business"),
    ("NPR Technology", "https://feeds.npr.org/1019/rss.xml", "Technology"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "World"),
    ("France 24", "https://www.france24.com/en/rss", "World"),
    ("DW Top Stories", "https://rss.dw.com/rdf/rss-en-all", "World"),
    ("DW Business", "https://rss.dw.com/xml/rss-en-bus", "Business"),
    ("DW Science", "https://rss.dw.com/xml/rss-en-science", "Technology"),
    ("ABC News International", "https://abcnews.go.com/abcnews/internationalheadlines", "World"),
    ("CBS News World", "https://www.cbsnews.com/latest/rss/world", "World"),
    ("CBS News Politics", "https://www.cbsnews.com/latest/rss/politics", "Politics"),
    ("CBS News Technology", "https://www.cbsnews.com/latest/rss/tech", "Technology"),
    ("NBC World", "https://feeds.nbcnews.com/nbcnews/public/world", "World"),
    ("NBC Tech", "https://feeds.nbcnews.com/nbcnews/public/tech", "Technology"),
    ("PBS World", "https://www.pbs.org/newshour/feeds/rss/world", "World"),
    ("PBS Politics", "https://www.pbs.org/newshour/feeds/rss/politics", "Politics"),
    ("PBS Business", "https://www.pbs.org/newshour/feeds/rss/business", "Business"),
    ("Sky News World", "https://feeds.skynews.com/feeds/rss/world.xml", "World"),
    ("Sky News Business", "https://feeds.skynews.com/feeds/rss/business.xml", "Business"),
    ("Sky News Technology", "https://feeds.skynews.com/feeds/rss/technology.xml", "Technology"),
    ("The Conversation Politics", "https://theconversation.com/us/politics/articles.atom", "Politics"),
    ("The Conversation Technology", "https://theconversation.com/us/technology/articles.atom", "Technology"),
    ("The Conversation Business", "https://theconversation.com/us/business/articles.atom", "Business"),
    ("Politico", "https://rss.politico.com/politics-news.xml", "Politics"),
    ("Politico Europe", "https://www.politico.eu/feed/", "Politics"),
    ("The Hill", "https://thehill.com/feed/", "Politics"),
    ("Axios", "https://api.axios.com/feed/", "World"),
    ("Financial Times World", "https://www.ft.com/world?format=rss", "World"),
    ("Financial Times Markets", "https://www.ft.com/markets?format=rss", "Finance/Trading"),
    ("MarketWatch Top Stories", "https://feeds.marketwatch.com/marketwatch/topstories/", "Finance/Trading"),
    ("MarketWatch Markets", "https://feeds.marketwatch.com/marketwatch/marketpulse/", "Finance/Trading"),
    ("CNBC World", "https://www.cnbc.com/id/100727362/device/rss/rss.html", "Business"),
    ("CNBC Finance", "https://www.cnbc.com/id/10000664/device/rss/rss.html", "Finance/Trading"),
    ("CNBC Technology", "https://www.cnbc.com/id/19854910/device/rss/rss.html", "Technology"),
    ("Investing.com News", "https://www.investing.com/rss/news.rss", "Finance/Trading"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "Finance/Trading"),
    ("TechCrunch", "https://techcrunch.com/feed/", "Technology"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "Technology"),
    ("The Register", "https://www.theregister.com/headlines.atom", "Technology"),
    ("Wired", "https://www.wired.com/feed/rss", "Technology"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", "Technology"),
    ("Hacker News front page", "https://hnrss.org/frontpage", "Technology"),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "Cyber"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", "Cyber"),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "Cyber"),
    ("CISA Alerts", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "Cyber"),
    ("Google Security Blog", "https://security.googleblog.com/feeds/posts/default", "Cyber"),
    ("Microsoft Security Blog", "https://www.microsoft.com/en-us/security/blog/feed/", "Cyber"),
    ("Cisco Talos", "https://blog.talosintelligence.com/feeds/posts/default", "Cyber"),
    ("SANS Internet Storm Center", "https://isc.sans.edu/rssfeed.xml", "Cyber"),
    ("Recorded Future News", "https://therecord.media/feed", "Cyber"),
    ("US Treasury Press Releases", "https://home.treasury.gov/news/press-releases/rss", "Finance/Trading"),
    ("Federal Reserve Press Releases", "https://www.federalreserve.gov/feeds/press_all.xml", "Finance/Trading"),
    ("IMF News", "https://www.imf.org/en/News/RSS", "Business"),
    ("World Bank News", "https://www.worldbank.org/en/news/all?format=rss", "Business"),
    ("OECD News", "https://www.oecd.org/newsroom/rss.xml", "Business"),
    ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "World"),
    ("UN Security Council", "https://www.un.org/securitycouncil/content/rss", "Intelligence"),
    ("NATO News", "https://www.nato.int/cps/en/natohq/news.rss", "Intelligence"),
    ("EU Council Press", "https://www.consilium.europa.eu/en/press/press-releases/rss/", "Politics"),
    ("NASA Breaking News", "https://www.nasa.gov/news-release/feed/", "Technology"),
    ("Nature News", "https://www.nature.com/subjects/scientific-community-and-society.rss", "Technology"),
    ("ScienceDaily Technology", "https://www.sciencedaily.com/rss/computers_math/computer_science.xml", "Technology"),
    ("The Diplomat", "https://thediplomat.com/feed/", "Intelligence"),
    ("War on the Rocks", "https://warontherocks.com/feed/", "Intelligence"),
    ("Foreign Policy", "https://foreignpolicy.com/feed/", "Intelligence"),
    ("Responsible Statecraft", "https://responsiblestatecraft.org/feed/", "Intelligence"),
    ("Defense News", "https://www.defensenews.com/arc/outboundfeeds/rss/", "Intelligence"),
    ("Breaking Defense", "https://breakingdefense.com/feed/", "Intelligence"),
    ("India MEA", "https://www.mea.gov.in/rss.htm", "Politics"),
    ("RBI Press Releases", "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=0", "Finance/Trading"),
    ("The Hindu International", "https://www.thehindu.com/news/international/feeder/default.rss", "World"),
    ("The Hindu Business", "https://www.thehindu.com/business/feeder/default.rss", "Business"),
    ("Indian Express World", "https://indianexpress.com/section/world/feed/", "World"),
    ("Indian Express Business", "https://indianexpress.com/section/business/feed/", "Business"),
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "Finance/Trading"),
    ("Economic Times Tech", "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", "Technology"),
    ("Reuters World", "https://feeds.reuters.com/Reuters/worldNews", "World"),
    ("AP Top News", "https://apnews.com/hub/ap-top-news?output=rss", "World"),
    ("AP Business", "https://apnews.com/hub/business?output=rss", "Business"),
    ("AP Technology", "https://apnews.com/hub/technology?output=rss", "Technology"),
]

CATEGORIES = ["All", "Technology", "Politics", "Intelligence", "Business",
              "Finance/Trading", "Cyber", "World"]
NOTE_CATEGORIES = ["General", "Technology", "Politics", "Intelligence",
                   "Business", "Finance/Trading", "Cyber", "World", "Personal"]

KEYWORDS = {
    "Technology": ["technology", "tech", "ai ", "artificial intelligence", "software",
                   "chip", "semiconductor", "robot", "data center", "startup", "cybersecurity"],
    "Politics": ["election", "parliament", "president", "prime minister", "government",
                 "minister", "campaign", "congress", "policy", "political party", "vote"],
    "Intelligence": ["intelligence", "espionage", "spy", "national security", "defense",
                     "defence", "military", "missile", "nato", "sanction", "geopolit", "diplomat", "war "],
    "Business": ["business", "company", "companies", "ceo", "merger", "acquisition",
                 "earnings", "revenue", "trade deal", "supply chain", "retail"],
    "Finance/Trading": ["market", "stock", "shares", "trading", "investor", "bond",
                        "yield", "inflation", "interest rate", "central bank", "currency",
                        "crypto", "bitcoin", "forex", "rbi", "fed"],
    "Cyber": ["cyber", "hack", "ransomware", "malware", "breach", "phishing",
              "vulnerability", "zero-day", "ddos", "data leak", "botnet"],
    "World": ["world", "international", "conflict", "diplomacy", "border", "sanctions",
              "united nations", "humanitarian", "ceasefire"],
}
GEO_TERMS = ["war", "conflict", "sanction", "border", "diplomacy", "military", "missile",
             "election", "treaty", "nato", "china", "taiwan", "ukraine", "russia", "iran",
             "israel", "gaza", "trade war", "coup", "protest", "summit", "tariff",
             "security council"]

# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS articles(
                id TEXT PRIMARY KEY, title TEXT, link TEXT, source TEXT,
                category TEXT, published TEXT, summary TEXT, fetched_at TEXT,
                tags TEXT)"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_published ON articles(published)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_category ON articles(category)")
        con.execute(
            """CREATE TABLE IF NOT EXISTS notes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'General',
                tags TEXT,
                pinned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                article_link TEXT)"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(pinned DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC)")

init_db()

# --------------------------------------------------------------------------- #
# Helpers — feed parsing & classification
# --------------------------------------------------------------------------- #
def classify(title, summary, fallback="World"):
    text = f"{title} {summary}".lower()
    scores = {cat: sum(1 for kw in words if kw in text) for cat, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else fallback

def iso_date(entry):
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def clean_html(value):
    value = re.sub(r"<script.*?</script>|<style.*?</style>", " ", value or "",
                  flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def stable_id(link, title):
    raw = (link or title or "").strip().lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def safe_link(url):
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def pill_class(category):
    """Stable CSS class for a category pill."""
    return "pill-cat-" + re.sub(r"[^A-Za-z0-9]+", "", str(category).split("/")[0])

# --------------------------------------------------------------------------- #
# Notes CRUD
# --------------------------------------------------------------------------- #
def add_note(title, content, category="General", tags=None, pinned=False, article_link=""):
    tags_json = json.dumps([t.strip() for t in (tags or "").split(",") if t.strip()])
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """INSERT INTO notes(title,content,category,tags,pinned,created_at,updated_at,article_link)
               VALUES(?,?,?,?,?,?,?,?)""",
            (title.strip(), content.strip(), category, tags_json,
             1 if pinned else 0, now, now, article_link.strip() or None),
        )

def update_note(note_id, title, content, category="General", tags=None, pinned=False, article_link=""):
    tags_json = json.dumps([t.strip() for t in (tags or "").split(",") if t.strip()])
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """UPDATE notes SET title=?, content=?, category=?, tags=?, pinned=?,
               updated_at=?, article_link=? WHERE id=?""",
            (title.strip(), content.strip(), category, tags_json,
             1 if pinned else 0, now, article_link.strip() or None, note_id),
        )

def delete_note(note_id):
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM notes WHERE id=?", (note_id,))

def toggle_pin(note_id, current_pinned):
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("UPDATE notes SET pinned=?, updated_at=? WHERE id=?",
                    (0 if current_pinned else 1, now, note_id))

def list_notes(search="", category="All", only_pinned=False):
    with sqlite3.connect(DB_PATH) as con:
        q = "SELECT id,title,content,category,tags,pinned,created_at,updated_at,article_link FROM notes"
        conditions, params = [], []
        if search:
            q += " WHERE (LOWER(title) LIKE ? OR LOWER(content) LIKE ?)"
            params.extend([f"%{search.lower()}%"] * 2)
        if category != "All":
            joiner = " AND " if conditions else " WHERE "
            q += f"{joiner}category=?"
            params.append(category)
        if only_pinned:
            joiner = " AND " if "WHERE" in q else " WHERE "
            q += f"{joiner}pinned=1"
        q += " ORDER BY pinned DESC, updated_at DESC"
        rows = con.execute(q, params).fetchall()
    out = []
    for r in rows:
        try:
            tags = json.loads(r[4]) if r[4] else []
        except Exception:
            tags = []
        out.append({
            "id": r[0], "title": r[1], "content": r[2], "category": r[3],
            "tags": tags, "pinned": bool(r[5]), "created_at": r[6],
            "updated_at": r[7], "article_link": r[8],
        })
    return out

def count_notes():
    with sqlite3.connect(DB_PATH) as con:
        total, pinned = con.execute(
            "SELECT COUNT(*), SUM(CASE WHEN pinned=1 THEN 1 ELSE 0 END) FROM notes"
        ).fetchone()
    return total or 0, pinned or 0

def export_notes_markdown():
    notes = list_notes()
    if not notes:
        return "*No notes saved yet.*"
    buf = io.StringIO()
    buf.write(f"# Aegis Notes Export\n\n")
    buf.write(f"_Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}_\n")
    buf.write(f"_Total notes: {len(notes)}_\n\n---\n\n")
    for n in notes:
        pin = "[PINNED] " if n["pinned"] else ""
        buf.write(f"## {pin}{n['title']}\n\n")
        buf.write(f"- **Category:** {n['category']}\n")
        if n["tags"]:
            buf.write(f"- **Tags:** {', '.join(n['tags'])}\n")
        buf.write(f"- **Updated:** {n['updated_at']}\n")
        if n["article_link"]:
            buf.write(f"- **Linked article:** {n['article_link']}\n")
        buf.write(f"\n{n['content']}\n\n---\n\n")
    return buf.getvalue()

# --------------------------------------------------------------------------- #
# Feed fetching
# --------------------------------------------------------------------------- #
def fetch_feed(name, url, fallback, timeout=9):
    try:
        response = requests.get(
            url, timeout=timeout,
            headers={"User-Agent": "AegisResearchTerminal/1.0 (public RSS reader)"})
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if not parsed.entries:
            return [], f"No entries ({parsed.bozo_exception if parsed.bozo else 'empty feed'})"
        records = []
        for entry in parsed.entries[:30]:
            title = clean_html(entry.get("title", ""))
            link = entry.get("link", "")
            if not title or not link:
                continue
            summary = clean_html(entry.get("summary", entry.get("description", "")))[:1800]
            category = classify(title, summary, fallback)
            published = iso_date(entry)
            tags = ["geopolitics"] if any(
                k in f"{title} {summary}".lower() for k in GEO_TERMS) else []
            if category == "Cyber":
                tags.append("cyber")
            records.append({
                "id": stable_id(link, title), "title": title, "link": link,
                "source": name, "category": category, "published": published,
                "summary": summary,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "tags": json.dumps(tags),
            })
        return records, None
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:180]}"

def refresh_feeds(force=False):
    now = time.time()
    last = st.session_state.get("last_refresh_epoch", 0)
    if not force and now - last < 50:
        return {"skipped": True, "added": 0, "errors": [], "checked": 0}
    all_records, errors, checked = [], [], 0
    progress = st.progress(0, text="Checking public feeds…")
    # Parallel requests keep a large feed list practical while each request
    # has its own timeout.
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(fetch_feed, n, u, c): (n, u, c)
                   for n, u, c in FEEDS}
        for future in as_completed(futures):
            name, _, _ = futures[future]
            try:
                records, err = future.result()
            except Exception as e:
                records, err = [], f"{type(e).__name__}: {str(e)[:180]}"
            checked += 1
            if err:
                errors.append((name, err))
            all_records.extend(records)
            progress.progress(checked / len(FEEDS),
                              text=f"Checking feeds: {checked}/{len(FEEDS)}")
    progress.empty()
    added = 0
    with sqlite3.connect(DB_PATH) as con:
        for r in all_records:
            cur = con.execute(
                """INSERT OR IGNORE INTO articles
                   (id,title,link,source,category,published,summary,fetched_at,tags)
                   VALUES (:id,:title,:link,:source,:category,:published,:summary,
                           :fetched_at,:tags)""", r)
            added += max(cur.rowcount, 0)
    st.session_state["last_refresh_epoch"] = now
    st.session_state["last_refresh_at"] = datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z")
    st.session_state["last_errors"] = errors
    st.session_state["last_checked"] = checked
    return {"skipped": False, "added": added, "errors": errors, "checked": checked}

def get_articles(limit=1500):
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql_query(
            "SELECT * FROM articles ORDER BY published DESC LIMIT ?", con, params=(limit,))
    if not df.empty:
        df["published_dt"] = pd.to_datetime(df["published"], utc=True, errors="coerce")
        df["date_local"] = df["published_dt"].dt.tz_convert(None)
    return df

def brief_for(df, category):
    if df.empty:
        return []
    subset = df if category == "All" else df[df.category == category]
    subset = subset.head(80)
    if subset.empty:
        return []
    out = []
    for _, r in subset.head(8).iterrows():
        summary = r["summary"] or "Open the original report for details."
        if len(summary) > 280:
            summary = summary[:277].rsplit(" ", 1)[0] + "…"
        out.append({"title": r["title"], "source": r["source"],
                    "published": r["published"], "summary": summary, "link": r["link"]})
    return out

# --------------------------------------------------------------------------- #
# Render helpers
# --------------------------------------------------------------------------- #
def render_articles(df, empty_text="No articles in this view yet. Refresh feeds or check source status."):
    if df.empty:
        st.info(empty_text)
        return
    for _, r in df.iterrows():
        published = r.get("published", "")
        try:
            published = pd.to_datetime(published, utc=True).strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            pass
        summary = r.get("summary", "") or "No publisher summary supplied."
        cat = str(r.get("category", "News"))
        st.markdown(
            f"""<div class="glass-card">
            <span class="pill {pill_class(cat)}">{html.escape(cat)}</span>
            <span class="small-muted">{html.escape(str(r.get('source','Unknown source')))} · {html.escape(str(published))}</span>
            <h4 style="margin:8px 0 5px">{html.escape(str(r.get('title','Untitled')))}</h4>
            <div class="summary-text">{html.escape(str(summary))[:700]}</div>
            </div>""",
            unsafe_allow_html=True)
        if safe_link(str(r.get("link", ""))):
            st.markdown(f"[Read original article ↗]({r['link']})")
        st.caption("Publisher content is linked, not republished in full. Verify important "
                   "claims against the original and independent sources.")

def render_live_clock():
    """Render a live UTC clock + status dot. Updates every rerun (60s)."""
    now = datetime.now(timezone.utc)
    st.markdown(
        f"""<div class="live-clock">
            <span class="live-dot"></span>
            <span>{now.strftime('%H:%M:%S')} UTC</span>
            <span class="small-muted" style="margin-left:6px">· {now.strftime('%a, %d %b %Y')}</span>
        </div>""",
        unsafe_allow_html=True)

def fmt_relative(iso_str):
    """Human-readable 'x min ago' from an ISO timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return "—"

# --------------------------------------------------------------------------- #
# Sidebar — branding, live clock, refresh, status, notes quick stats
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown(
        """<div class="sidebar-hero">
            <h2>🌐 AEGIS</h2>
            <div class="small-muted">Global Intelligence Terminal</div>
        </div>""",
        unsafe_allow_html=True)
    render_live_clock()
    st.markdown("")

    page = st.radio(
        "Navigate",
        ["Overview", "Geopolitics", "Cyber Lab", "Global News",
         "Daily Briefings", "Notes", "Sources & Status"],
        index=0)

    st.divider()
    st.markdown("**Collection**")
    st.caption(f"{len(FEEDS)} configured public feeds")

    if st.button("↻ Refresh all feeds now", use_container_width=True):
        with st.spinner("Fetching public feeds; slow feeds may time out…"):
            result = refresh_feeds(force=True)
        if result.get("added", 0) > 0:
            st.success(f"✓ {result['checked']} feeds checked · {result['added']} new articles")
        else:
            st.info(f"{result['checked']} feeds checked · no new articles since last refresh")
        st.rerun()

    # Auto-refresh on first load / stale cache
    if "last_refresh_epoch" not in st.session_state or \
            time.time() - st.session_state.get("last_refresh_epoch", 0) > 60:
        with st.spinner("Refreshing public feeds…"):
            refresh_feeds(force=True)

    df = get_articles()
    last_at = st.session_state.get("last_refresh_at", "Not refreshed in this session")
    errors = st.session_state.get("last_errors", [])

    if errors:
        st.markdown(
            f"""<span class="status-pill warn">
                <span class="live-dot" style="background:#ffb74d;
                       box-shadow:0 0 0 0 rgba(255,183,77,.7);"></span>
                {len(errors)} feed issues
            </span>""",
            unsafe_allow_html=True)
    else:
        st.markdown(
            """<span class="status-pill"><span class="live-dot"></span>All feeds nominal</span>""",
            unsafe_allow_html=True)

    st.caption(f"Last checked: {last_at}")
    st.caption("Auto-check cadence: 60 seconds")
    st.caption("Publishers control how often they publish — Aegis only polls.")

    st.divider()
    st.markdown("**Notes**")
    n_total, n_pinned = count_notes()
    st.caption(f"📝 {n_total} saved · 📌 {n_pinned} pinned")

# --------------------------------------------------------------------------- #
# Page: Overview
# --------------------------------------------------------------------------- #
if page == "Overview":
    st.title("🌐 Aegis Intelligence Terminal")
    st.markdown("**Geopolitics · Cybersecurity research · Global news**")
    st.caption("Public-source monitoring dashboard. Facts, interpretation, and "
               "forecasts are deliberately separated.")
    a, b, c, d = st.columns(4)
    a.metric("Articles stored", f"{len(df):,}")
    b.metric("Configured feeds", len(FEEDS))
    c.metric("Feed issues", len(errors))
    d.metric("Refresh cadence", "60 sec")

    st.divider()
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.subheader("📡 Latest global developments")
        render_articles(df.head(8))
    with col2:
        st.subheader("📊 Coverage by category")
        if not df.empty:
            counts = df["category"].value_counts().rename_axis("Category").reset_index(name="Articles")
            st.bar_chart(counts.set_index("Category"), use_container_width=True)
        else:
            st.info("No articles yet — refresh feeds to populate.")
        st.subheader("🧭 Research guardrails")
        st.markdown("""
        - **Reported fact** — what a named source says.
        - **Analysis** — an interpretation to test, not a confirmed fact.
        - **Forecast** — a conditional scenario, not a certainty.
        - **Cross-check** — seek independent sources, especially for breaking events.
        """)
        st.info("Briefings are extractive summaries of publisher-provided descriptions. "
                "They do not invent facts or claim to be AI-verified.")

# --------------------------------------------------------------------------- #
# Page: Geopolitics
# --------------------------------------------------------------------------- #
elif page == "Geopolitics":
    st.title("🗺️ Geopolitics & Strategic Risk")
    st.caption("Discover relevant reporting, compare viewpoints, and develop scenarios "
               "without confusing forecasts with facts.")
    geo = df[df["tags"].str.contains("geopolitics", na=False)] if not df.empty else df
    if not df.empty and len(geo) < 5:
        geo = df[df["category"].isin(["Intelligence", "Politics", "World"])]
    q = st.text_input("Search geopolitical topics",
                      placeholder="e.g., sanctions, Taiwan, energy, elections, shipping")
    if q and not geo.empty:
        geo = geo[geo.apply(
            lambda r: q.lower() in (str(r["title"]) + " " + str(r["summary"])).lower(),
            axis=1)]
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("Recent reporting")
        st.caption(f"{len(geo)} stories matched")
        render_articles(geo.head(25), "No geopolitics-related articles found. Try a broader search.")
    with right:
        st.subheader("Analytical worksheet")
        st.markdown("Use this structured checklist for each event:")
        st.markdown("""
        **1 · Reported facts** — date, actors, stated decision, independently confirmed outcomes.

        **2 · Stakeholders** — governments, civilians, firms, allies, rivals, international bodies.

        **3 · Transmission channels** — energy, shipping, trade, currencies, migration, technology, security.

        **4 · Competing interpretations** — official rationale; critics' strongest argument;
        independent expert view; what evidence could falsify each.

        **5 · Scenarios (not predictions)** — baseline, escalation, de-escalation;
        indicators to monitor; confidence and time horizon.
        """)
        st.text_area("Event / decision", key="geo_event",
                     placeholder="Summarize the event and link sources…")
        st.text_area("Evidence and counterarguments", key="geo_evidence",
                     placeholder="Separate confirmed facts from claims and interpretation…")
        st.text_area("Scenarios and indicators", key="geo_scenarios",
                     placeholder="What would change your assessment?")
        st.caption("This worksheet is not an automated forecast. Do not treat keyword-matched "
                   "articles as proof of causality.")

# --------------------------------------------------------------------------- #
# Page: Cyber Lab
# --------------------------------------------------------------------------- #
elif page == "Cyber Lab":
    st.title("🛡️ Cybersecurity Research Lab")
    st.markdown("A defensive, educational library of major incidents. Case studies focus on "
                "impact, root causes, detection, response, and lessons — not reusable intrusion instructions.")
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8")) if CASES_PATH.exists() else []
    c1, c2 = st.columns([1, 2])
    with c1:
        search = st.text_input("Find an incident", placeholder="e.g., SolarWinds, WannaCry")
    with c2:
        year_opts = ["All"] + sorted({str(c.get("year", "Unknown")) for c in cases}, reverse=True)
        selected_year = st.selectbox("Year", year_opts)
    filtered = cases
    if search:
        filtered = [c for c in filtered if search.lower() in (
            c.get("name", "") + " " + c.get("summary", "") + " " + c.get("sector", "")).lower()]
    if selected_year != "All":
        filtered = [c for c in filtered if str(c.get("year")) == selected_year]
    st.caption(f"{len(filtered)} case studies shown · {len(cases)} total in local library")
    for case in filtered:
        with st.expander(f"{case['year']} · {case['name']} — {case['sector']}"):
            st.markdown(f"**What happened:** {case['summary']}")
            st.markdown(f"**What made it notable:** {case['notable']}")
            st.markdown(f"**Defensive lessons:** {case['lessons']}")
            st.markdown(f"**Research starting point:** [{case['source_label']}]({case['source']})")
            st.caption("Details and attribution may evolve as investigations are updated. Confirm "
                       "technical claims with primary incident reports.")
    st.divider()
    st.subheader("Study path")
    st.markdown("""
    1. **Networking fundamentals** — TCP/IP, DNS, HTTP(S), routing, TLS.
    2. **Operating systems and identity** — Linux, Windows logs, permissions, authentication.
    3. **Secure coding and vulnerability classes** — OWASP Top 10, patch management, threat modeling.
    4. **Defensive operations** — SIEM queries, endpoint telemetry, backups, incident response, threat hunting.
    5. **Safe practice** — CTFs and intentionally vulnerable labs you own or are authorized to test.
    6. **Research** — compare vendor write-ups, advisories, CVE records, post-incident reviews, and peer-reviewed work.
    """)
    st.warning("Only test systems you own or have explicit permission to assess. This library "
               "intentionally avoids exploit payloads, persistence steps, credential theft "
               "instructions, and target-selection guidance.")

# --------------------------------------------------------------------------- #
# Page: Global News
# --------------------------------------------------------------------------- #
elif page == "Global News":
    st.title("📰 Global News Wire")
    st.caption("Cross-source feed reader. Articles are deduplicated by URL/title hash and "
               "stored in SQLite.")
    c1, c2, c3 = st.columns([1, 1, 2])
    cat = c1.selectbox("Category", CATEGORIES)
    source_opts = ["All"] + sorted(df["source"].dropna().unique().tolist()) if not df.empty else ["All"]
    src = c2.selectbox("Publisher", source_opts)
    query = c3.text_input("Search headlines and summaries")
    view = df.copy()
    if cat != "All":
        view = view[view["category"] == cat]
    if src != "All":
        view = view[view["source"] == src]
    if query:
        view = view[view.apply(
            lambda r: query.lower() in (str(r["title"]) + " " + str(r["summary"])).lower(),
            axis=1)]
    st.caption(f"{len(view)} matching stories")
    render_articles(view.head(100))

# --------------------------------------------------------------------------- #
# Page: Daily Briefings
# --------------------------------------------------------------------------- #
elif page == "Daily Briefings":
    st.title("☀️ Daily Briefings")
    st.caption("Briefings are generated from the most recent available feed entries. This "
               "lightweight build uses source-provided descriptions; no generative AI or "
               "unsupported claims are added.")
    cats = ["Technology", "Politics", "Intelligence", "Business", "Finance/Trading"]
    tabs = st.tabs(cats)
    for tab, cat in zip(tabs, cats):
        with tab:
            items = brief_for(df, cat)
            if not items:
                st.info(f"No {cat.lower()} stories available in the current cache.")
            else:
                st.markdown(f"### {cat}: latest available developments")
                st.caption(f"{len(items)} items · newest cached entries · generated at "
                           f"{datetime.now().astimezone().strftime('%d %b %Y %H:%M %Z')}")
                for i, item in enumerate(items, 1):
                    st.markdown(f"**{i}. {item['title']}**")
                    st.caption(f"{item['source']} · {item['published']}")
                    st.write(item["summary"])
                    if safe_link(item["link"]):
                        st.markdown(f"[Original report]({item['link']})")
                    st.divider()
    st.info("For a true editorial daily briefing, add a licensed summarization model/API "
            "and require citations for every factual sentence. This version is key-free and transparent.")

# --------------------------------------------------------------------------- #
# Page: Notes (NEW)
# --------------------------------------------------------------------------- #
elif page == "Notes":
    st.title("📝 Notes & Workspace")
    st.caption("Capture observations, hypotheses, source links, and analytical reminders. "
               "Notes are stored locally in SQLite and persist across sessions.")

    n_total, n_pinned = count_notes()
    m1, m2, m3 = st.columns(3)
    m1.metric("Total notes", n_total)
    m2.metric("Pinned", n_pinned)
    m3.metric("Categories tracked", len(NOTE_CATEGORIES))

    # ----- Composer -----
    with st.expander("➕ New note", expanded=False):
        with st.form("note_form", clear_on_submit=True):
            ncol1, ncol2 = st.columns([3, 1])
            with ncol1:
                n_title = st.text_input("Title", placeholder="Concise summary of the note")
            with ncol2:
                n_cat = st.selectbox("Category", NOTE_CATEGORIES, index=0)
            n_content = st.text_area(
                "Content", height=160,
                placeholder="Write your observation, hypothesis, source excerpt, or analysis…")
            n_tags = st.text_input(
                "Tags (comma-separated)",
                placeholder="e.g., sanctions, energy, Q4-2026")
            n_link = st.text_input(
                "Linked article URL (optional)",
                placeholder="https://…")
            n_pin = st.checkbox("📌 Pin this note")
            submitted = st.form_submit_button("Save note", use_container_width=True)
            if submitted:
                if not n_title.strip() or not n_content.strip():
                    st.error("Title and content are required.")
                else:
                    add_note(n_title, n_content, n_cat, n_tags, n_pin, n_link)
                    st.success("✓ Note saved.")
                    st.rerun()

    # ----- Filters -----
    st.divider()
    st.subheader("🔎 Browse & search")
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 1.2, 1, 1])
    search_q = fcol1.text_input("Search titles & content", placeholder="…",
                                key="note_search", label_visibility="collapsed")
    cat_filter = fcol2.selectbox("Category", ["All"] + NOTE_CATEGORIES, key="note_cat")
    only_pinned = fcol3.checkbox("📌 Pinned only")
    sort_latest = fcol4.selectbox("Sort", ["Updated (newest)", "Created (newest)"])

    notes = list_notes(search=search_q, category=cat_filter, only_pinned=only_pinned)
    if sort_latest == "Created (newest)":
        notes.sort(key=lambda n: n["created_at"], reverse=True)

    # ----- Export -----
    ecol1, ecol2 = st.columns([4, 1])
    with ecol2:
        if st.button("⬇ Export Markdown", use_container_width=True):
            md = export_notes_markdown()
            st.download_button(
                "💾 Download .md",
                data=md.encode("utf-8"),
                file_name=f"aegis_notes_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                mime="text/markdown",
                use_container_width=True)

    st.caption(f"{len(notes)} notes match the current filter")

    # ----- List -----
    if not notes:
        st.info("No notes match. Create one above, or adjust filters.")
    for n in notes:
        cls = "note-card pinned" if n["pinned"] else "note-card"
        tags_html = "".join(f'<span class="note-tag">#{html.escape(t)}</span>' for t in n["tags"])
        link_html = (f'<div class="small-muted" style="margin-top:4px">🔗 <a href="{html.escape(n["article_link"])}" '
                     f'target="_blank">{html.escape(n["article_link"])}</a></div>'
                     if n["article_link"] else "")
        st.markdown(
            f"""<div class="{cls}">
                <div class="note-title">{"📌 " if n["pinned"] else ""}{html.escape(n["title"])}</div>
                <span class="pill {pill_class(n["category"])}">{html.escape(n["category"])}</span>
                {tags_html}
                <div class="note-content">{html.escape(n["content"])}</div>
                {link_html}
                <div class="note-meta">Updated {fmt_relative(n["updated_at"])} ·
                    Created {fmt_relative(n["created_at"])}</div>
            </div>""",
            unsafe_allow_html=True)
        bcol1, bcol2, bcol3 = st.columns([1, 1, 4])
        with bcol1:
            if st.button("📌 Pin" if not n["pinned"] else "↓ Unpin",
                        key=f"pin_{n['id']}", use_container_width=True):
                toggle_pin(n["id"], n["pinned"])
                st.rerun()
        with bcol2:
            if st.button("✎ Edit", key=f"edit_{n['id']}", use_container_width=True):
                st.session_state[f"editing_{n['id']}"] = True
                st.rerun()
        if st.session_state.get(f"editing_{n['id']}"):
            with st.form(f"edit_form_{n['id']}", clear_on_submit=False):
                e_title = st.text_input("Title", value=n["title"], key=f"e_title_{n['id']}")
                e_cat = st.selectbox("Category", NOTE_CATEGORIES,
                                     index=NOTE_CATEGORIES.index(n["category"]) if n["category"] in NOTE_CATEGORIES else 0,
                                     key=f"e_cat_{n['id']}")
                e_content = st.text_area("Content", value=n["content"], height=160,
                                         key=f"e_content_{n['id']}")
                e_tags = st.text_input("Tags (comma-separated)",
                                       value=", ".join(n["tags"]),
                                       key=f"e_tags_{n['id']}")
                e_link = st.text_input("Linked article URL",
                                       value=n["article_link"] or "",
                                       key=f"e_link_{n['id']}")
                e_pin = st.checkbox("📌 Pin", value=n["pinned"], key=f"e_pin_{n['id']}")
                esave, ecancel = st.columns([1, 1])
                with esave:
                    save_clicked = st.form_submit_button("💾 Save changes", use_container_width=True)
                with ecancel:
                    cancel_clicked = st.form_submit_button("✕ Cancel", use_container_width=True)
                if save_clicked:
                    if not e_title.strip() or not e_content.strip():
                        st.error("Title and content are required.")
                    else:
                        update_note(n["id"], e_title, e_content, e_cat,
                                    e_tags, e_pin, e_link)
                        st.session_state.pop(f"editing_{n['id']}", None)
                        st.success("✓ Note updated.")
                        st.rerun()
                if cancel_clicked:
                    st.session_state.pop(f"editing_{n['id']}", None)
                    st.rerun()
        bcol3_internal = bcol3
        with bcol3_internal.container():
            if st.button("🗑 Delete", key=f"del_{n['id']}",
                         use_container_width=False):
                st.session_state[f"confirm_del_{n['id']}"] = True
                st.rerun()
            if st.session_state.get(f"confirm_del_{n['id']}"):
                st.warning("Are you sure? This cannot be undone.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Yes, delete", key=f"yes_{n['id']}",
                                 use_container_width=True):
                        delete_note(n["id"])
                        st.session_state.pop(f"confirm_del_{n['id']}", None)
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"no_{n['id']}",
                                 use_container_width=True):
                        st.session_state.pop(f"confirm_del_{n['id']}", None)
                        st.rerun()
        st.divider()

# --------------------------------------------------------------------------- #
# Page: Sources & Status
# --------------------------------------------------------------------------- #
elif page == "Sources & Status":
    st.title("🔌 Sources, Status & Limitations")
    st.write(f"Configured public feeds: **{len(FEEDS)}**. Some endpoints may be "
             "unavailable, move, rate-limit requests, or change format.")
    if errors:
        st.subheader(f"Recent feed errors ({len(errors)})")
        for name, err in errors:
            st.warning(f"**{name}**: {err}")
    else:
        st.success("No feed errors were recorded in the most recent refresh.")
    st.subheader("Configured sources")
    feed_df = pd.DataFrame([
        {"Publisher / feed": n, "Default topic": c, "Feed URL": u}
        for n, u, c in FEEDS
    ])
    st.dataframe(feed_df, use_container_width=True, hide_index=True,
                 column_config={"Feed URL": st.column_config.LinkColumn("Feed URL")})
    st.subheader("Data handling")
    st.markdown("""
    - Fetches publicly accessible RSS/Atom endpoints only; no login or paywall bypass.
    - Source names, original links, publication timestamps, and feed-check errors are retained.
    - SQLite database is local to this project folder.
    - Duplicate items are ignored by a stable SHA-256 hash of URL or title.
    - Publisher timestamps are normalized to UTC where available; missing timestamps fall back to fetch time.
    - Topic labels use transparent keyword rules and can be wrong. Always check the original source.
    - This app does not provide classified intelligence, verify claims independently, or guarantee real-time delivery.
    """)
    st.subheader("Operations")
    st.code("python -m venv .venv\n"
             "# Windows: .venv\\Scripts\\activate\n"
             "# macOS/Linux: source .venv/bin/activate\n"
             "pip install -r requirements.txt\n"
             "streamlit run app.py", language="bash")
