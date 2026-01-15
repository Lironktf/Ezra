"""Cache manager for GitHub PR data to avoid re-scraping."""
import json
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict


class PRCacheManager:
    """Manage cached PR data per repository."""
    
    def __init__(self, cache_dir: str = "data/cache"):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Index file tracks what's cached and when
        self.index_file = self.cache_dir / "cache_index.json"
        self.index = self._load_index()
    
    def _load_index(self) -> Dict:
        """Load cache index from disk."""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_index(self):
        """Save cache index to disk."""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def _get_repo_cache_path(self, repo: str) -> Path:
        """Get cache file path for a repository."""
        # Convert "owner/repo" to "owner_repo.json"
        safe_name = repo.replace('/', '_')
        return self.cache_dir / f"{safe_name}.json"
    
    def is_cached(self, repo: str, max_age_days: int = 7) -> bool:
        """
        Check if repo data is cached and fresh.
        
        Args:
            repo: Repository name (e.g., "facebook/react")
            max_age_days: Maximum age of cache in days
            
        Returns:
            True if cache exists and is fresh
        """
        if repo not in self.index:
            return False
        
        cache_info = self.index[repo]
        cached_time = datetime.fromisoformat(cache_info['cached_at'])
        age = datetime.now() - cached_time
        
        return age.days < max_age_days
    
    def get_cached_prs(self, repo: str) -> Optional[List[Dict]]:
        """
        Retrieve cached PR data for a repository.
        
        Args:
            repo: Repository name
            
        Returns:
            List of PR dictionaries or None if not cached
        """
        if repo not in self.index:
            return None
        
        cache_path = self._get_repo_cache_path(repo)
        if not cache_path.exists():
            # Index says it's cached but file missing - remove from index
            del self.index[repo]
            self._save_index()
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"✅ Loaded {len(data['prs'])} cached PRs from {repo}")
            return data['prs']
        
        except Exception as e:
            print(f"⚠️  Error loading cache for {repo}: {e}")
            return None
    
    def cache_prs(self, repo: str, prs: List[Dict], metadata: Optional[Dict] = None):
        """
        Cache PR data for a repository.
        
        Args:
            repo: Repository name
            prs: List of PR dictionaries
            metadata: Optional metadata about the scrape
        """
        cache_path = self._get_repo_cache_path(repo)
        
        cache_data = {
            'repo': repo,
            'cached_at': datetime.now().isoformat(),
            'pr_count': len(prs),
            'metadata': metadata or {},
            'prs': prs
        }
        
        # Save cache file
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        # Update index
        self.index[repo] = {
            'cached_at': cache_data['cached_at'],
            'pr_count': len(prs),
            'cache_file': str(cache_path)
        }
        self._save_index()
        
        print(f"💾 Cached {len(prs)} PRs for {repo}")
    
    def get_cache_info(self, repo: str) -> Optional[Dict]:
        """Get cache metadata for a repository."""
        return self.index.get(repo)
    
    def invalidate_cache(self, repo: str):
        """Remove cache for a specific repository."""
        if repo in self.index:
            cache_path = self._get_repo_cache_path(repo)
            if cache_path.exists():
                cache_path.unlink()
            del self.index[repo]
            self._save_index()
            print(f"🗑️  Invalidated cache for {repo}")
    
    def clear_all_cache(self):
        """Clear all cached data."""
        for repo in list(self.index.keys()):
            self.invalidate_cache(repo)
        print("🗑️  Cleared all cache")
    
    def get_all_cached_repos(self) -> List[str]:
        """Get list of all cached repositories."""
        return list(self.index.keys())
    
    def print_cache_status(self):
        """Print status of all cached repositories."""
        if not self.index:
            print("📭 No cached repositories")
            return
        
        print(f"\n📦 Cached Repositories ({len(self.index)}):")
        print("=" * 80)
        
        for repo, info in sorted(self.index.items()):
            cached_time = datetime.fromisoformat(info['cached_at'])
            age = datetime.now() - cached_time
            age_str = f"{age.days}d {age.seconds // 3600}h ago"
            
            status = "✅ Fresh" if age.days < 7 else "⚠️  Stale"
            print(f"{status} {repo:40} {info['pr_count']:4} PRs  (cached {age_str})")
        
        print("=" * 80)


def get_or_scrape_repos(
    repos: List[str],
    scraper_func,
    cache_manager: PRCacheManager,
    force_refresh: bool = False,
    max_cache_age_days: int = 7
) -> List[Dict]:
    """
    Get PR data from cache or scrape if needed.
    
    Args:
        repos: List of repository names
        scraper_func: Function to scrape a repo (takes repo name, returns PRs)
        cache_manager: Cache manager instance
        force_refresh: Force re-scraping even if cached
        max_cache_age_days: Maximum age of cache to use
        
    Returns:
        Combined list of PRs from all repos
    """
    all_prs = []
    
    for repo in repos:
        # Check cache first
        if not force_refresh and cache_manager.is_cached(repo, max_cache_age_days):
            cached_prs = cache_manager.get_cached_prs(repo)
            if cached_prs:
                all_prs.extend(cached_prs)
                continue
        
        # Scrape if not cached or cache is stale
        print(f"\n🔄 Scraping fresh data for {repo}...")
        try:
            prs = scraper_func(repo)
            
            # Cache the results
            cache_manager.cache_prs(repo, prs, {
                'scraped_at': datetime.now().isoformat(),
                'pr_count': len(prs)
            })
            
            all_prs.extend(prs)
        
        except Exception as e:
            print(f"❌ Error scraping {repo}: {e}")
            # Try to use stale cache as fallback
            cached_prs = cache_manager.get_cached_prs(repo)
            if cached_prs:
                print(f"⚠️  Using stale cache for {repo}")
                all_prs.extend(cached_prs)
    
    return all_prs


if __name__ == "__main__":
    # Test the cache manager
    cache = PRCacheManager()
    
    # Show current cache status
    cache.print_cache_status()
    
    # Example: Cache some test data
    test_prs = [
        {
            'pr_id': 'test/repo#1',
            'title': 'Test PR',
            'author': 'testuser',
            'lines_changed': 100
        }
    ]
    
    cache.cache_prs('test/repo', test_prs)
    
    # Retrieve from cache
    cached = cache.get_cached_prs('test/repo')
    print(f"\nRetrieved {len(cached)} PRs from cache")
    
    # Check if cached
    print(f"Is cached (fresh): {cache.is_cached('test/repo', max_age_days=7)}")
    print(f"Is cached (stale check): {cache.is_cached('test/repo', max_age_days=0)}")
