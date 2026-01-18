# GitHub Expert Finder

Find domain experts on GitHub by analyzing their PR history and contributions. When you have a technical question, this tool helps you discover the right people who can help based on their actual work.

## How It Works

1. **Scrape GitHub PRs** - Collects pull requests from target repositories using Browserbase
2. **Extract Tech Keywords** - Identifies technologies from file paths and PR content
3. **Generate Embeddings** - Creates semantic embeddings using **FREE local models** (or OpenAI)
4. **Vector Search** - Stores in Qdrant and enables similarity search
5. **Rank Experts** - Finds and ranks experts based on relevance and recency

## Features

- **100% FREE** - Uses local embeddings (no OpenAI API costs!)
- Natural language queries (e.g., "Help with GraphQL N+1 queries")
- Semantic search using local AI models or OpenAI embeddings
- Filters out bot PRs and merge commits
- Recency weighting for active contributors
- Deduplication by author
- Tech expertise tagging
- CLI and interactive modes

## Installation

### Prerequisites

**Required:**
- Python 3.8+
- Browserbase account ([get one here](https://browserbase.com))

**Optional (for free mode, you don't need these!):**
- OpenAI API key ([get one here](https://platform.openai.com)) - Only if you want to use OpenAI embeddings instead of free local models
- Qdrant Docker - Can use in-memory mode with `--memory` flag

### Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd github-expert-finder
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
- `BROWSERBASE_API_KEY` - Your Browserbase API key
- `BROWSERBASE_PROJECT_ID` - Your Browserbase project ID
- `EMBEDDING_PROVIDER` - Set to `local` for FREE embeddings (default) or `openai`
- `TARGET_REPOS` - Comma-separated list of repos (e.g., "facebook/react,vercel/next.js")

Optional (only if using OpenAI):
- `OPENAI_API_KEY` - Your OpenAI API key (not needed for local embeddings!)

4. Start Qdrant (local mode):
```bash
docker run -p 6333:6333 qdrant/qdrant
```

Or use `--memory` flag for in-memory mode (no Docker needed).

## Embedding Options

This tool supports **two embedding providers**:

### 🆓 Local Embeddings (FREE - Recommended)

**Default option - no API costs!**

Uses Sentence Transformers models that run on your machine:
- **all-MiniLM-L6-v2** (default) - Fast, 384 dimensions, great quality
- **all-mpnet-base-v2** - Better quality, 768 dimensions, slightly slower
- **paraphrase-multilingual-MiniLM-L12-v2** - Multilingual support

**Setup:**
```bash
# In .env file
EMBEDDING_PROVIDER=local
LOCAL_MODEL=all-MiniLM-L6-v2
```

First run will download the model (~100MB), then it's cached locally. No API keys needed!

### 💰 OpenAI Embeddings (Paid)

For potentially better quality (but costs money):

**Setup:**
```bash
# In .env file
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

Uses `text-embedding-3-small` (1536 dimensions). Cost: ~$0.02 per 100 PRs.

**Recommendation:** Start with local embeddings - they work great and are completely free!

## Quick Start

### Run the Full Pipeline

```bash
# Scrape, embed, setup DB, and search in one command
python main.py pipeline -q "How to optimize React rendering performance?"
```

### Step-by-Step

```bash
# Step 1: Scrape PRs from repositories
python main.py scrape

# Step 2: Generate embeddings
python main.py embed

# Step 3: Setup vector database
python main.py setup

# Step 4: Search for experts
python main.py search -q "GraphQL schema design best practices"
```

### Interactive Mode

```bash
python main.py interactive
```

## Usage Examples

### Search for Experts

```bash
# Basic search
python main.py search -q "React hooks performance optimization"

# Get more results
python main.py search -q "TypeScript generics" -n 10

# Filter by repository
python main.py search -q "API design" -r "facebook/react"

# Save results to file
python main.py search -q "Database migration" -o results.txt
```

### Custom Repository List

```bash
# Scrape specific repositories
python main.py scrape -r "microsoft/vscode" "facebook/react" "vercel/next.js"

# Run full pipeline with custom repos
python main.py pipeline -r "rust-lang/rust" "golang/go" -q "Concurrency patterns"
```

### Use In-Memory Database (for testing)

```bash
# No Docker required
python main.py pipeline -m -q "Your question here"
```

## Project Structure

```
github-expert-finder/
├── data/
│   ├── raw_prs.json          # Scraped PR data
│   ├── embedded_prs.json     # PRs with embeddings
│   └── embeddings_cache.pkl  # Embedding cache
├── src/
│   ├── scraper.py            # Browserbase GitHub scraper
│   ├── embedder.py           # OpenAI embedding generator
│   ├── vector_db.py          # Qdrant database interface
│   ├── query.py              # Expert search and ranking
│   └── utils.py              # Tech keyword extraction
├── config.py                 # Configuration settings
├── main.py                   # CLI interface
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Configuration

Edit `config.py` or set environment variables:

```python
# Number of PRs to scrape per repository
MAX_PRS_PER_REPO = 100

# Minimum lines changed to consider a PR
MIN_LINES_CHANGED = 20

# Only consider PRs from last N days
MAX_PR_AGE_DAYS = 730  # 2 years

# Embedding model
EMBEDDING_MODEL = "text-embedding-3-small"  # or "text-embedding-3-large"

# Search results
TOP_K_RESULTS = 50      # PRs retrieved from vector search
TOP_N_EXPERTS = 10      # Experts returned to user
```

## How It Works

### Tech Keyword Extraction

Extracts technology keywords from file paths:
- `/src/graphql/schema/user.graphql` → `["graphql", "schema"]`
- `/api/resolvers/typescript/index.ts` → `["api", "resolvers", "typescript"]`
- `/components/hooks/useQuery.tsx` → `["hooks", "react"]`

Filters out generic terms like "src", "lib", "utils", "index", "test".

### Embedding Generation

Combines PR information into searchable text:
```
"{title}. {description}. Technologies: {tech_keywords}"
```

Empty descriptions fall back to:
```
"{title}. Files: {tech_keywords}"
```

### Expert Ranking

Scores experts based on:
1. **Semantic similarity** - How well their PRs match the query
2. **Recency** - More recent contributions score higher
3. **Contribution volume** - Total lines changed and number of relevant PRs

Deduplicates by author to show each expert once with their best PR.

## API Reference

### ExpertFinder

```python
from src.query import ExpertFinder

finder = ExpertFinder(use_memory=False)

experts = finder.find_experts(
    query="Your technical question",
    top_n=10,
    tech_filter=["graphql", "typescript"],  # Optional
    repo_filter="facebook/react",           # Optional
    recency_weight=0.1                      # 0-1, higher = more recent
)

# Format for display
output = finder.format_results(experts, show_top_n=5)
print(output)
```

### Response Format

```python
{
    "author": "username",
    "github_url": "https://github.com/username",
    "score": 0.85,
    "best_pr": {
        "title": "PR title",
        "url": "https://github.com/...",
        "repo": "owner/repo",
        "tech_keywords": ["react", "graphql"],
        "similarity": 0.92
    },
    "top_prs": [...],  # Top 3 most relevant PRs
    "tech_expertise": ["react", "graphql", "typescript"],
    "total_relevant_prs": 12,
    "total_lines_changed": 3450
}
```

## Development

### Testing Individual Components

```python
# Test tech keyword extraction
from src.utils import extract_tech_keywords
keywords = extract_tech_keywords("src/api/graphql/resolvers/user.ts")
print(keywords)  # ['api', 'graphql', 'resolvers', 'user']

# Test embedding generation
from src.embedder import PREmbedder
embedder = PREmbedder()
embedding = embedder.generate_embedding("GraphQL N+1 query optimization")
print(len(embedding))  # 1536

# Test vector search
from src.vector_db import QdrantDB
db = QdrantDB(use_memory=True)
results = db.search(query_vector=embedding, limit=10)
```

### Running Tests

```bash
# Test scraper (scrapes one PR)
python -c "from src.scraper import GitHubPRScraper; s = GitHubPRScraper(); print(s.scrape_repo_prs('facebook/react', max_prs=1))"

# Test embedder
python src/embedder.py

# Test vector DB
python src/vector_db.py

# Test query
python src/query.py
```

## Troubleshooting

### Browserbase Connection Issues

- Check API key and project ID in `.env`
- Ensure you have an active Browserbase subscription
- Check Browserbase dashboard for session logs

### Qdrant Connection Issues

```bash
# Check if Qdrant is running
curl http://localhost:6333/collections

# Restart Qdrant
docker restart <qdrant-container-id>

# Use in-memory mode instead
python main.py search -m -q "your question"
```

### OpenAI Rate Limits

- Reduce `MAX_PRS_PER_REPO` in config.py
- Add delays between API calls (modify embedder.py)
- Use embedding cache (automatically enabled)

### No Results Found

- Check if database has data: `db.get_collection_info()`
- Verify embeddings were generated: check `data/embedded_prs.json`
- Try broader queries
- Check if Qdrant collection exists

## Performance Tips

1. **Cache everything** - Embeddings are cached automatically
2. **Use batch processing** - Scraper and embedder use batches
3. **Limit scope** - Start with 3-5 repos, 100 PRs each
4. **Use in-memory mode** - Faster for demos and testing
5. **Filter early** - Use tech_filter and repo_filter in queries

## Limitations

- Only works with public GitHub repositories
- Requires Browserbase for scraping (rate limits apply)
- OpenAI API costs (very cheap with text-embedding-3-small)
- PR data becomes stale (re-scrape periodically)
- Doesn't consider issue comments or code quality

## Future Improvements

- [ ] Support GitHub API instead of web scraping
- [ ] Add code snippet analysis
- [ ] Include issue contributions
- [ ] Multi-language support
- [ ] Caching layer for queries
- [ ] Web UI dashboard
- [ ] Real-time data updates
- [ ] Expert contact methods (email, Twitter)
- [ ] Collaboration network analysis

## License

MIT License - feel free to use for your hackathon or project!

## Contributing

Pull requests welcome! For major changes, please open an issue first.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review existing GitHub issues
3. Open a new issue with details

## Acknowledgments

Built for hackathons with:
- [Browserbase](https://browserbase.com) - Web scraping infrastructure
- [OpenAI](https://openai.com) - Embedding generation
- [Qdrant](https://qdrant.tech) - Vector database
- [Playwright](https://playwright.dev) - Browser automation

---

**Happy hunting for GitHub experts!** 🚀
# Ezra
