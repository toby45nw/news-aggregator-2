"""Central configuration for the aggregator.

All hand-tunable constants live here. No logic, no dependencies on other
project modules — this is imported by everything else.
"""
from pathlib import Path


# --- Paths ---
DB_PATH = Path("newsagg.sqlite")
LOG_PATH       = Path("logs/newsagg.log")


# --- Embedding ---
EMBED_MODEL    = "all-MiniLM-L6-v2"
EMBED_DIM      = 384
EMBED_BATCH    = 64


# --- LLM tagger ---
LLM_MODEL      = "gemma3:4b"
LLM_KEEP_ALIVE = "30m"
LLM_MAX_TAGS   = 3         # cap per article
LLM_RETRIES    = 2         # invalid response retries before flagging needs_retag


# --- Seed tags ---
# The stable, hand-authored tag list. `other` is the LLM's escape hatch when
# nothing on the list fits. All ship with weight 1.0 and is_seed=1.
SEED_TAGS = [
    "politics",
    "world affairs",
    "business",
    "technology",
    "science",
    "health",
    "environment",
    "culture",
    "sports",
    "society",
    "history",
    "lifestyle",
    "other",
]


# --- Story clustering ---
CLUSTER_DISTANCE_THRESHOLD = 0.65   # cosine distance ceiling for cluster members
CLUSTER_LINKAGE            = "average"


# --- Scoring ---
# Per-cluster score = log(1 + distinct_source_count)
#                   + max(tag.weight * fit_score)
#                   + max(source.weight)


# --- Reaction weight adjustments ---
REACTION_TAG_DELTA    = 0.10   # 👍 / 👎 nudge to tags.weight
TAG_WEIGHT_MIN        = 0.0
TAG_WEIGHT_MAX        = 3.0


# --- Ingest cadence ---
INGEST_INTERVAL_HOURS = 2
DAILY_DIGEST_HOUR     = 6
WEEKLY_DIGEST_DAY     = "sun"
WEEKLY_DIGEST_HOUR    = 6


# --- Source weights ---
# Manual per-source multipliers. Anything not in this dict defaults to 1.0.
# Adjust here when a source consistently drifts up or down in quality.
SOURCE_WEIGHTS = {
    # "the_economist_international": 1.2,
    # "hn_frontpage": 0.9,
}


def source_weight(name: str) -> float:
    """Look up a source weight; unknown sources default to 1.0."""
    return SOURCE_WEIGHTS.get(name, 1.0)


# --- Discord ---
# Loaded from environment at runtime; never hardcode.
import os
DISCORD_TOKEN     = os.getenv("SEED_DISCORD_TOKEN")
DISCORD_CHANNEL   = int(os.getenv("SEED_DISCORD_CHANNEL", "0"))
DISCORD_ERROR_DM  = int(os.getenv("SEED_DISCORD_ERROR_DM", "0"))




### ---------- Feeds ----------

# List of feeds to ingest.
# 'source' is a short label you control (used for tagging later).
# 'url' must be a working RSS/Atom feed URL.
#
# Find feeds by trying: <site>/feed, <site>/rss, <site>/atom.xml
# Or use RSSHub (self-hosted) to generate one for sites that don't publish RSS:
#   https://docs.rsshub.app/

FEEDS = [
    {"source": "bbc_tech", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"source": "hn_frontpage", "url": "https://hnrss.org/frontpage"},
    {"source": "guardian_science", "url": "https://www.theguardian.com/science/rss"},
    {"source": "nature", "url": "https://www.nature.com/nature.rss"},  # Nature
    {"source": "ars_technica", "url": "https://arstechnica.com/feed"},  # Ars Technica
    {"source": "science_daily", "url": "https://www.sciencedaily.com/rss/all.xml"},  # Science Daily
    {"source": "wired", "url": "https://www.wired.com/feed/rss"},  # Wired
    {"source": "quanta_magazine", "url": "https://www.quantamagazine.org/quanta/feed/"},  # Quanta Magazine
    {"source": "mit_technology_review", "url": "https://www.technologyreview.com/feed"},  # MIT Technology Review
    {"source": "scientific_american", "url": "https://www.scientificamerican.com/platform/syndication/rss/"},  # Scientific American
    {"source": "nature_reviews", "url": "https://www.nature.com/nrd.rss"},  # Nature Reviews
    {"source": "popular_science", "url": "https://www.popsci.com/feed/"},  # Popular Science
    {"source": "techcrunch", "url": "https://techcrunch.com/feed/"},  # TechCrunch
    {"source": "gizmodo", "url": "https://gizmodo.com/feed"},  # Gizmodo
    {"source": "cnet", "url": "https://www.cnet.com/rss/news/"},  # CNET
    {"source": "engadget", "url": "https://www.engadget.com/category/news/feed/"},  # Engadget
    {"source": "futurism", "url": "https://futurism.com/feed"},  # Futurism
    {"source": "foreign_affairs", "url": "https://www.foreignaffairs.com/rss.xml"},  # Foreign Affairs
    {"source": "council_on_foreign_relations_cfr", "url": "https://www.cfr.org/feed"},  # Council on Foreign Relations (CFR)
    {"source": "the_diplomat", "url": "https://thediplomat.com/feed"},  # The Diplomat
    {"source": "geopolitical_futures", "url": "https://geopoliticalfutures.com/feed/"},  # Geopolitical Futures
    {"source": "uk_defence_journal", "url": "https://ukdefencejournal.org.uk/feed/"},  # UK Defence Journal
    {"source": "the_atlantic", "url": "https://www.theatlantic.com/feed/all/"},  # The Atlantic
    {"source": "the_guardian_-_world_news", "url": "https://www.theguardian.com/world/rss"},  # The Guardian - World News
    {"source": "war_on_the_rocks", "url": "https://warontherocks.com/feed"},  # War on the Rocks
    {"source": "foreign_policy", "url": "https://foreignpolicy.com/feed"},  # Foreign Policy
    {"source": "responsible_statecraft", "url": "https://responsiblestatecraft.org/feeds/feed.rss"},  # Responsible Statecraft
    {"source": "history_extra_bbc", "url": "https://www.historyextra.com/feed"},  # History Extra (BBC)
    {"source": "the_conversation", "url": "https://theconversation.com/articles.atom"},  # The Conversation
    {"source": "national_archives", "url": "https://www.archives.gov/rss.xml"},  # National Archives
    {"source": "atmos", "url": "https://atmos.earth/feed"},  # Atmos
    {"source": "al_jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},  # Al Jazeera
    {"source": "aeon", "url": "https://aeon.co/feed.rss"},  # Aeon
    {"source": "npr", "url": "https://feeds.npr.org/1002/rss.xml"},  # NPR
    {"source": "the_new_yorker", "url": "https://www.newyorker.com/feed/rss"},  # The New Yorker
    {"source": "vox", "url": "https://www.vox.com/rss/index.xml"},  # Vox
    {"source": "pew_research_center", "url": "https://www.pewresearch.org/feed/"},  # Pew Research Center
    {"source": "inequality.org", "url": "https://inequality.org/feed"},  # Inequality.org
    {"source": "the_baffler", "url": "https://thebaffler.com/homepage/feed"},  # The Baffler
    {"source": "environmental_news_network", "url": "https://www.enn.com/?layout=ja_teline_v:taggedblog&types[0]=1&format=feed&type=rss"},  # Environmental News Network
    {"source": "grist", "url": "https://grist.org/feed"},  # Grist
    {"source": "artnet_news", "url": "https://news.artnet.com/feed"},  # ArtNet News
    {"source": "hyperallergic", "url": "https://hyperallergic.com/rss/"},  # Hyperallergic
    {"source": "brain_pickings", "url": "https://feeds.feedburner.com/brainpickings/rss"},  # Brain Pickings
    {"source": "atlas_obscura", "url": "https://www.atlasobscura.com/feeds/latest"},  # Atlas Obscura
    {"source": "wait_but_why", "url": "https://waitbutwhy.com/feed"},  # Wait But Why
    {"source": "nautilus", "url": "https://nautil.us/feed"},  # Nautilus
    {"source": "longreads", "url": "https://longreads.com/feed/"},  # Longreads
    {"source": "phys_org", "url": "https://phys.org/rss-feed/"},
    {"source": "new_scientist", "url": "https://www.newscientist.com/feed/home/"},
    {"source": "defense_one", "url": "https://www.defenseone.com/rss/all/"},
    {"source": "national_interest", "url": "https://nationalinterest.org/feed"},
    {"source": "the_hill", "url": "https://thehill.com/feed/"},
    {"source": "politico", "url": "https://www.politico.com/rss/politicopicks.xml"},
    {"source": "smithsonian_magazine", "url": "https://www.smithsonianmag.com/rss/latest_articles/"},
    {"source": "the_tyee", "url": "https://thetyee.ca/rss2.xml"},
    {"source": "paris_review", "url": "https://www.theparisreview.org/blog/feed/"},
    {"source": "economist_international", "url": "https://www.economist.com/international/rss.xml"},
]

# Skipped entirely — not single-feed publications, so a feed URL isn't
# really the right shape for these:
#   Medium (no site-wide feed, per-author/publication only)
#   Astrophysics Data System (a search tool, not a publication)
#   RAND Corporation (no consistent public feed found)
#   American Historical Association (no public feed found)
#   Earth Island Journal (no public feed found)
#   The Nature Conservancy (no public feed found)
#   The Poetry Foundation (feed appears discontinued)
#   The History Channel (no reliable public feed found)
#   Global Policy Journal (no public feed found)
#   Reuters (public RSS discontinued some years ago)

# Failed to find a feed
# discover_magazine, hbr, the_rumpus, brookings, history_today, carnegie_endowment

#### ---------------



#### ------Source weights------
SOURCE_WEIGHTS = {
    # Depth / careful reporting — bump up
    "the_economist_international": 1.2,
    "foreign_affairs": 1.2,
    "nature": 1.2,
    "quanta_magazine": 1.2,
    "the_atlantic": 1.15,
    "the_new_yorker": 1.15,
    "aeon": 1.15,
    "pew_research_center": 1.15,
    "mit_technology_review": 1.1,
    "scientific_american": 1.1,
    "war_on_the_rocks": 1.1,
    "the_diplomat": 1.1,
    "council_on_foreign_relations_cfr": 1.1,
    "longreads": 1.1,
    "nautilus": 1.1,
    "the_conversation": 1.1,

    # Fast/breezy tech + news — dip
    "gizmodo": 0.8,
    "engadget": 0.8,
    "cnet": 0.8,
    "futurism": 0.7,
    "techcrunch": 0.85,
    "hn_frontpage": 0.85,   # aggregator-of-an-aggregator
    "science_daily": 0.85,  # rewrites press releases

    # Everything else defaults to 1.0
}
#### ----------------