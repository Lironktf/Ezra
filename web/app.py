"""Flask web application for GitHub Expert Finder."""
import sys
import os
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json

from scraper_factory import scrape_repositories
from embedder import embed_pr_data, PREmbedder
from vector_db import QdrantDB
from query import ExpertFinder
from repo_selector import RepoSelector

app = Flask(__name__)
CORS(app)

# Global state (for in-memory DB)
_db_instance = None
_embedder_instance = None


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/api/find-experts', methods=['POST'])
def find_experts():
    """
    API endpoint to find GitHub experts.

    Request body:
    {
        "query": "useEffect cleanup functions preventing memory leaks",
        "max_repos": 3,
        "max_prs_per_repo": 50,
        "top_n": 5
    }

    Returns:
    {
        "query": "...",
        "selected_repos": ["facebook/react", ...],
        "repo_explanation": "...",
        "experts": [...],
        "status": "success"
    }
    """
    global _db_instance, _embedder_instance

    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_repos = data.get('max_repos', 3)
        max_prs_per_repo = data.get('max_prs_per_repo', 50)
        top_n = data.get('top_n', 5)

        if not query:
            return jsonify({
                'status': 'error',
                'message': 'Query is required'
            }), 400

        print(f"\n{'='*80}")
        print(f"🔍 Processing query: {query}")
        print(f"{'='*80}")


        print("\n📍 STEP 1: Selecting repositories with Groq...")
        selector = RepoSelector()
        selected_repos = selector.select_repositories(query, max_repos=max_repos)
        repo_explanation = selector.explain_selection(query, selected_repos)

        print(f"✅ Selected repos: {selected_repos}")
        print(f"💡 Why: {repo_explanation}")


        print(f"\n📍 STEP 2: Scraping {max_prs_per_repo} PRs from each repo...")


        import config
        original_max = config.MAX_PRS_PER_REPO
        config.MAX_PRS_PER_REPO = max_prs_per_repo

        prs = scrape_repositories(
            selected_repos,
            output_file="data/web_prs.json"
        )


        config.MAX_PRS_PER_REPO = original_max

        print(f"✅ Scraped {len(prs)} PRs")

        if len(prs) == 0:
            return jsonify({
                'status': 'error',
                'message': 'No PRs found in selected repositories'
            })


        print("\n📍 STEP 3: Generating embeddings...")

        if _embedder_instance is None:
            _embedder_instance = PREmbedder()

        embedded_prs = _embedder_instance.embed_prs(prs)
        print(f"✅ Generated {len(embedded_prs)} embeddings")


        print("\n📍 STEP 4: Setting up vector database...")


        _db_instance = QdrantDB(use_memory=True)
        _db_instance.create_collection(recreate=True)
        _db_instance.upload_prs(embedded_prs)

        print("✅ Database ready")


        print("\n📍 STEP 5: Finding experts...")

        finder = ExpertFinder(use_memory=False)
        finder.db = _db_instance
        finder.embedder = _embedder_instance

        experts = finder.find_experts(
            query=query,
            top_n=top_n
        )

        print(f"✅ Found {len(experts)} experts")

        # Format response
        response = {
            'status': 'success',
            'query': query,
            'selected_repos': selected_repos,
            'repo_explanation': repo_explanation,
            'total_prs_analyzed': len(prs),
            'experts': experts
        }

        return jsonify(response)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 GitHub Expert Finder - Web UI")
    print("="*80)
    print("\n📍 Starting server at http://localhost:5000")
    print("💡 Open your browser and navigate to http://localhost:5000\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
