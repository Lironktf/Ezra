"""GitHub PR scraper using GitHub REST API (FREE!)."""
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

import requests
from tqdm import tqdm

from config import (
    GITHUB_TOKEN,
    GITHUB_API_URL,
    MAX_PRS_PER_REPO,
    MIN_LINES_CHANGED,
    MAX_PR_AGE_DAYS
)
from utils import (
    extract_tech_keywords_from_paths,
    is_bot_author,
    is_merge_commit
)
from cache_manager import PRCacheManager


class GitHubAPIScraper:
    """Scraper for GitHub pull requests using GitHub REST API."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize the scraper.

        Args:
            token: GitHub personal access token (optional but recommended)
        """
        self.token = token or GITHUB_TOKEN
        self.api_url = GITHUB_API_URL
        self.session = requests.Session()

        # Set up headers
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Expert-Finder'
        })

        if self.token:
            self.session.headers.update({
                'Authorization': f'token {self.token}'
            })
            print("✅ Using authenticated GitHub API (Core: 5000 req/hr, Search: 30 req/min)")
        else:
            print("⚠️  Using unauthenticated GitHub API (Core: 60 req/hr, Search: 10 req/min)")
            print("   Get a token at https://github.com/settings/tokens for higher limits")

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a request to GitHub API with rate limit handling.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            JSON response or None on error
        """
        try:
            response = self.session.get(url, params=params)

            # Check rate limit
            remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            if remaining < 10:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                wait_time = max(0, reset_time - time.time())
                if wait_time > 0:
                    print(f"⏳ Rate limit low, waiting {int(wait_time)}s...")
                    time.sleep(wait_time + 1)

            response.raise_for_status()
            # Extract links for pagination
            self.session.links = response.links
            return response.json()

        except requests.exceptions.HTTPError as e:
            if hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
                if status_code == 404:
                    print(f"❌ Repository not found or not accessible")
                elif status_code == 403:
                    print(f"❌ Rate limit exceeded or forbidden")
                elif status_code == 422:
                    # 422 usually means invalid query syntax - try to get error details
                    try:
                        error_data = e.response.json()
                        error_msg = error_data.get('message', 'Invalid query syntax')
                        print(f"❌ HTTP Error 422: {error_msg}")
                    except:
                        print(f"❌ HTTP Error 422: Invalid query syntax (possibly date format issue)")
                else:
                    print(f"❌ HTTP Error {status_code}: {e}")
            else:
                print(f"❌ HTTP Error: {e}")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def scrape_repo_prs(self, repo: str, max_prs: int = MAX_PRS_PER_REPO) -> List[Dict]:
        """
        Scrape pull requests from a GitHub repository.

        Args:
            repo: Repository in format "owner/repo"
            max_prs: Maximum number of PRs to scrape

        Returns:
            List of PR dictionaries
        """
        print(f"\n🔍 Scraping PRs from {repo}...")

        # Calculate date range for search
        # GitHub API requires dates in YYYY-MM-DD format
        since_date = (datetime.now() - timedelta(days=MAX_PR_AGE_DAYS)).strftime('%Y-%m-%d')
        # Use merged:>= format which is more reliable, or fallback to no date filter if that fails
        query = f"repo:{repo} is:pr is:merged merged:>={since_date}"

        prs = []
        page = 1
        per_page = 100

        while len(prs) < max_prs:
            # Search for PRs
            url = f"{self.api_url}/search/issues"
            params = {
                'q': query,
                'sort': 'updated',
                'order': 'desc',
                'per_page': per_page,
                'page': page
            }
            
            print(f"  Searching page {page} for '{query}'...")
            data = self._make_request(url, params)

            if not data:
                # If we get an error on first page with date filter, try without date filter
                if page == 1:
                    print(f"  ⚠️  Date-filtered search failed, trying without date filter...")
                    query_fallback = f"repo:{repo} is:pr is:merged"
                    params['q'] = query_fallback
                    data = self._make_request(url, params)
                    if data:
                        query = query_fallback  # Use fallback query for remaining pages
                    else:
                        print("  No PRs found in search results.")
                        break
                else:
                    print("  No more PRs found in search results.")
                    break

            if not data.get('items'):
                print("  No more PRs found in search results.")
                break

            # Process each PR from search results
            for pr_data in tqdm(data['items'], desc="  Processing PRs"):
                pr_number = pr_data['number']
                
                # Filter bot authors
                author = pr_data['user']['login'] if pr_data.get('user') else ''
                if is_bot_author(author):
                    continue

                # Fetch detailed PR info (includes files, lines changed, etc.)
                pr_details = self._fetch_pr_details(repo, pr_number)

                if not pr_details:
                    continue
                    
                # Additional filtering that requires full PR data
                if is_merge_commit(pr_details['title']):
                    continue

                # Add to list
                prs.append(pr_details)
                if len(prs) >= max_prs:
                    break
            
            # Check if there are more pages
            if 'next' not in self.session.links:
                 break

            page += 1
            if page > 10: # Safety break
                print("  Reached max pages for search.")
                break

        print(f"✅ Scraped {len(prs)} PRs from {repo}")
        return prs

    def _fetch_pr_details(self, repo: str, pr_number: int) -> Optional[Dict]:
        """
        Fetch detailed information for a single PR.

        Args:
            repo: Repository name
            pr_number: PR number

        Returns:
            PR dictionary or None if filtered out
        """
        try:
            # Get PR details
            pr_url = f"{self.api_url}/repos/{repo}/pulls/{pr_number}"
            pr_data = self._make_request(pr_url)

            if not pr_data:
                return None

            # Extract basic info
            title = pr_data.get('title', '')
            description = pr_data.get('body', '') or ''
            author = pr_data['user']['login'] if pr_data.get('user') else ''
            merged_date = pr_data.get('merged_at', '')
            
            # NEW: Extract additional quality metrics
            commits_count = pr_data.get('commits', 0)
            comments_count = pr_data.get('comments', 0)
            review_comments_count = pr_data.get('review_comments', 0)
            changed_files = pr_data.get('changed_files', 0)

            # Get files changed
            files_url = f"{self.api_url}/repos/{repo}/pulls/{pr_number}/files"
            files_data = self._make_request(files_url)

            if not files_data:
                return None

            # Extract file paths and count lines changed
            file_paths = []
            lines_changed = 0
            has_tests = False
            has_docs = False

            for file_info in files_data:
                filename = file_info.get('filename', '')
                if filename:
                    file_paths.append(filename)
                    lines_changed += file_info.get('additions', 0)
                    lines_changed += file_info.get('deletions', 0)
                    
                    # Detect test files
                    filename_lower = filename.lower()
                    if any(pattern in filename_lower for pattern in ['test_', 'spec_', '__test__', '.test.', '.spec.', '/tests/', '/test/']):
                        has_tests = True
                    
                    # Detect documentation
                    if any(pattern in filename_lower for pattern in ['.md', 'readme', 'docs/', '/doc/', 'documentation']):
                        has_docs = True

            # Filter PRs with too few changes
            if lines_changed < MIN_LINES_CHANGED:
                return None

            # Extract tech keywords from file paths
            tech_keywords = extract_tech_keywords_from_paths(file_paths)
            
            # Calculate complexity score
            files_changed_count = len(file_paths)
            complexity_score = self._calculate_complexity_score(
                files_changed=files_changed_count,
                lines_changed=lines_changed,
                commits=commits_count,
                has_tests=has_tests,
                has_docs=has_docs
            )
            
            # Determine PR impact category
            impact_category, impact_score = self._categorize_pr_impact(title)

            # Build PR data with enhanced metrics
            pr_info = {
                "pr_id": f"{repo}#{pr_number}",
                "pr_number": str(pr_number),
                "title": title,
                "description": description,
                "author": author,
                "repo": repo,
                "file_paths": file_paths,
                "tech_keywords": tech_keywords,
                "lines_changed": lines_changed,
                "merged_date": merged_date,
                "pr_url": f"https://github.com/{repo}/pull/{pr_number}",
                # NEW: Enhanced quality metrics
                "files_changed": files_changed_count,
                "commits_count": commits_count,
                "comments_count": comments_count,
                "review_comments_count": review_comments_count,
                "has_tests": has_tests,
                "has_docs": has_docs,
                "complexity_score": complexity_score,
                "impact_category": impact_category,
                "impact_score": impact_score
            }

            return pr_info

        except Exception as e:
            print(f"    Error fetching PR #{pr_number}: {e}")
            return None

    def _calculate_complexity_score(
        self,
        files_changed: int,
        lines_changed: int,
        commits: int,
        has_tests: bool,
        has_docs: bool
    ) -> float:
        """
        Calculate PR complexity score based on multiple factors.
        
        Higher score = more complex/substantial PR
        
        Args:
            files_changed: Number of files modified
            lines_changed: Total lines added + deleted
            commits: Number of commits in PR
            has_tests: Whether PR includes test files
            has_docs: Whether PR includes documentation
            
        Returns:
            Complexity score (0-1 scale)
        """
        score = 0.0
        
        # Files changed (0-0.3): More files = more complex
        # Normalize: 1 file=0.05, 10 files=0.3
        files_score = min(files_changed / 30.0, 1.0) * 0.3
        score += files_score
        
        # Lines changed (0-0.3): More lines = more work
        # Normalize: 100 lines=0.1, 1000 lines=0.3
        lines_score = min(lines_changed / 3000.0, 1.0) * 0.3
        score += lines_score
        
        # Commits (0-0.2): Multiple commits = iterative work
        # Normalize: 1 commit=0.05, 5+ commits=0.2
        commits_score = min(commits / 25.0, 1.0) * 0.2
        score += commits_score
        
        # Quality indicators (0-0.2 total)
        if has_tests:
            score += 0.1
        if has_docs:
            score += 0.1
        
        return min(score, 1.0)
    
    def _categorize_pr_impact(self, title: str) -> tuple[str, float]:
        """
        Categorize PR by impact level based on title.
        
        Args:
            title: PR title
            
        Returns:
            Tuple of (category, impact_score)
        """
        if not title:
            return ('unknown', 0.5)
        
        title_lower = title.lower()
        
        # Define patterns and their scores
        categories = {
            'feature': {
                'patterns': ['feat:', 'feature:', 'add', 'implement', 'introduce', 'new'],
                'score': 1.0
            },
            'performance': {
                'patterns': ['perf:', 'performance:', 'optimize', 'speed up', 'improve performance'],
                'score': 0.9
            },
            'fix': {
                'patterns': ['fix:', 'bug:', 'resolve', 'patch', 'correct'],
                'score': 0.7
            },
            'refactor': {
                'patterns': ['refactor:', 'restructure', 'cleanup', 'reorganize'],
                'score': 0.5
            },
            'docs': {
                'patterns': ['docs:', 'documentation:', 'readme', 'comment'],
                'score': 0.3
            },
            'chore': {
                'patterns': ['chore:', 'deps:', 'ci:', 'build:', 'dependencies', 'upgrade'],
                'score': 0.2
            }
        }
        
        # Check each category
        for category, config in categories.items():
            if any(pattern in title_lower for pattern in config['patterns']):
                return (category, config['score'])
        
        # Default to unknown
        return ('unknown', 0.5)
    
    def check_rate_limit(self) -> Dict:
        """
        Check current rate limit status for both Core and Search APIs.

        Returns:
            Dictionary with rate limit info
        """
        url = f"{self.api_url}/rate_limit"
        data = self._make_request(url)

        if data:
            resources = data.get('resources', {})
            core = resources.get('core', {})
            search = resources.get('search', {})
            
            return {
                'core': {
                    'limit': core.get('limit', 0),
                    'remaining': core.get('remaining', 0),
                    'reset': datetime.fromtimestamp(core.get('reset', 0))
                },
                'search': {
                    'limit': search.get('limit', 0),
                    'remaining': search.get('remaining', 0),
                    'reset': datetime.fromtimestamp(search.get('reset', 0))
                }
            }
        return {}


def scrape_repositories(
    repos: List[str], 
    output_file: str = "data/raw_prs.json",
    use_cache: bool = True,
    force_refresh: bool = False,
    max_cache_age_days: int = 7
) -> List[Dict]:
    """
    Scrape PRs from multiple repositories using GitHub API with caching.

    Args:
        repos: List of repositories in format "owner/repo"
        output_file: Path to save scraped data
        use_cache: Use cached data if available
        force_refresh: Force re-scraping even if cached
        max_cache_age_days: Maximum age of cache to consider fresh (default: 7 days)

    Returns:
        List of all scraped PRs
    """
    scraper = GitHubAPIScraper()
    cache = PRCacheManager() if use_cache else None
    all_prs = []

    # Show rate limit info
    rate_limit = scraper.check_rate_limit()
    if rate_limit:
        print(f"\n📊 GitHub API Rate Limit:")
        print(f"   Core API: {rate_limit['core']['remaining']}/{rate_limit['core']['limit']} requests remaining (resets at {rate_limit['core']['reset']})")
        print(f"   Search API: {rate_limit['search']['remaining']}/{rate_limit['search']['limit']} requests remaining (resets at {rate_limit['search']['reset']})")

    # Show cache status if using cache
    if cache:
        print(f"\n💾 Cache enabled (max age: {max_cache_age_days} days)")
        if force_refresh:
            print("🔄 Force refresh enabled - ignoring cache")

    for repo in repos:
        try:
            # Try cache first
            if cache and not force_refresh and cache.is_cached(repo, max_cache_age_days):
                cached_prs = cache.get_cached_prs(repo)
                if cached_prs:
                    all_prs.extend(cached_prs)
                    continue
            
            # Scrape if not cached
            print(f"\n🔄 Scraping {repo}...")
            prs = scraper.scrape_repo_prs(repo)
            
            # Cache the results
            if cache:
                cache.cache_prs(repo, prs, {
                    'scraped_at': datetime.now().isoformat(),
                    'scraper': 'github_api'
                })
            
            all_prs.extend(prs)
        
        except Exception as e:
            print(f"❌ Error scraping {repo}: {e}")
            # Try to use stale cache as fallback
            if cache:
                cached_prs = cache.get_cached_prs(repo)
                if cached_prs:
                    print(f"⚠️  Using cached data for {repo} as fallback")
                    all_prs.extend(cached_prs)
            continue

    # Save combined results to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_prs, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Total: {len(all_prs)} PRs from {len(repos)} repositories")
    print(f"📁 Saved to {output_file}")
    
    if cache:
        cache.print_cache_status()

    return all_prs


if __name__ == "__main__":
    # Test with a single repo
    from config import TARGET_REPOS

    prs = scrape_repositories(TARGET_REPOS[:1])  # Start with just one repo
    print(f"\nSample PR:")
    if prs:
        print(json.dumps(prs[0], indent=2))
