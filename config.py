"""Configuration settings for GitHub Expert Finder."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Scraper Configuration
# Provider: "github_api" (FREE with token!) or "browserbase" (requires account)
SCRAPER_PROVIDER = os.getenv("SCRAPER_PROVIDER", "github_api")  # "github_api" is FREE!

# GitHub API Configuration (FREE - recommended!)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Optional but increases rate limits
GITHUB_API_URL = "https://api.github.com"

# Browserbase Configuration (alternative scraper)
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

# Embedding Configuration
# Provider: "openai" or "local" (sentence-transformers)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local")  # "local" is FREE!

# OpenAI Configuration (only needed if EMBEDDING_PROVIDER="openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "text-embedding-3-small"  # or "text-embedding-3-large"

# Local Embedding Configuration (FREE - no API key needed!)
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "all-MiniLM-L6-v2")  # Fast and good quality
# Alternative models:
# - "all-MiniLM-L6-v2" (384 dim) - Fastest, good quality
# - "all-mpnet-base-v2" (768 dim) - Better quality, slower
# - "paraphrase-multilingual-MiniLM-L12-v2" (384 dim) - Multilingual support

# Auto-set dimension based on provider
if EMBEDDING_PROVIDER == "openai":
    EMBEDDING_MODEL = OPENAI_MODEL
    EMBEDDING_DIMENSION = 1536
else:  # local
    EMBEDDING_MODEL = LOCAL_MODEL
    # Set dimension based on model
    if "MiniLM" in LOCAL_MODEL:
        EMBEDDING_DIMENSION = 384
    elif "mpnet" in LOCAL_MODEL:
        EMBEDDING_DIMENSION = 768
    else:
        EMBEDDING_DIMENSION = 384  # default

# Qdrant Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")  # Optional, for cloud
COLLECTION_NAME = "github_experts"

# GitHub Configuration
TARGET_REPOS = os.getenv("TARGET_REPOS", "facebook/react,vercel/next.js,apollographql/apollo-server").split(",")
MAX_PRS_PER_REPO = 100  # Number of PRs to scrape per repo

# Data Quality Filters
MIN_LINES_CHANGED = 50  # Minimum lines changed to consider a PR
MIN_SUBSTANTIAL_PR_LINES = 100  # Minimum lines for PRs to be considered "substantial" in ranking
MAX_PR_AGE_DAYS = 730  # Only consider PRs from last 2 years
BOT_AUTHORS = ["dependabot", "renovate", "renovate-bot", "dependabot-preview"]

# Generic terms to filter from tech keywords
GENERIC_TERMS = {
    "src", "lib", "libs", "utils", "util", "helpers", "helper",
    "index", "main", "app", "test", "tests", "spec", "specs",
    "components", "component", "pages", "page", "styles", "style",
    "assets", "asset", "public", "static", "dist", "build",
    "config", "configs", "setup", "init", "common", "shared",
    "types", "type", "interfaces", "interface", "models", "model",
    "js", "ts", "tsx", "jsx", "py", "md", "json", "yml", "yaml"
}

# Query Configuration
TOP_K_RESULTS = 100  # Number of PRs to retrieve from vector search (increased to filter for substantial PRs)
TOP_N_EXPERTS = 10  # Number of experts to return to user

# Expert Quality Filters (use OR logic: either condition qualifies)
MIN_EXPERT_PRS = 2  # Minimum number of PRs an expert must have
MIN_EXPERT_TOTAL_LINES = 500  # OR minimum total lines changed across all PRs

# Cache Configuration
USE_CACHE = True  # Enable caching of scraped PR data
CACHE_MAX_AGE_DAYS = 7  # Maximum age of cache before re-scraping (default: 7 days)
CACHE_DIR = "data/cache"  # Directory to store per-repo cache files
