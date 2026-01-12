"""GitHub PR scraper using Browserbase."""
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from playwright.sync_api import sync_playwright, Page
from browserbase import Browserbase
from tqdm import tqdm

from config import (
    BROWSERBASE_API_KEY,
    BROWSERBASE_PROJECT_ID,
    MAX_PRS_PER_REPO,
    MIN_LINES_CHANGED,
    MAX_PR_AGE_DAYS
)
from utils import (
    extract_tech_keywords_from_paths,
    is_bot_author,
    is_merge_commit
)


class GitHubPRScraper:
    """Scraper for GitHub pull requests using Browserbase."""

    def __init__(self):
        """Initialize the scraper."""
        if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
            raise ValueError("Browserbase API credentials not configured")

        self.browserbase = Browserbase(api_key=BROWSERBASE_API_KEY)
        self.project_id = BROWSERBASE_PROJECT_ID

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

        with sync_playwright() as p:
            # Connect to Browserbase
            session = self.browserbase.sessions.create(project_id=self.project_id)
            browser = p.chromium.connect_over_cdp(session.connect_url)
            context = browser.contexts[0]
            page = context.new_page()

            prs = []
            page_num = 1

            try:
                while len(prs) < max_prs:
                    # Navigate to PRs page
                    url = f"https://github.com/{repo}/pulls?q=is%3Apr+is%3Amerged+sort%3Aupdated-desc&page={page_num}"
                    print(f"  Loading page {page_num}...")
                    page.goto(url, wait_until="networkidle")
                    time.sleep(2)  # Give it a moment to fully load

                    # Get all PR links on the page
                    pr_links = page.query_selector_all('a.Link--primary[href*="/pull/"]')

                    if not pr_links:
                        print("  No more PRs found")
                        break

                    # Extract unique PR URLs
                    pr_urls = []
                    seen_numbers = set()
                    for link in pr_links:
                        href = link.get_attribute('href')
                        if href and '/pull/' in href:
                            # Extract PR number
                            parts = href.split('/pull/')
                            if len(parts) > 1:
                                pr_num = parts[1].split('/')[0].split('#')[0]
                                if pr_num.isdigit() and pr_num not in seen_numbers:
                                    seen_numbers.add(pr_num)
                                    pr_urls.append(f"https://github.com{href.split('#')[0]}")

                    print(f"  Found {len(pr_urls)} PRs on this page")

                    # Scrape each PR
                    for pr_url in tqdm(pr_urls[:max_prs - len(prs)], desc="  Scraping PRs"):
                        pr_data = self._scrape_single_pr(page, pr_url, repo)
                        if pr_data:
                            prs.append(pr_data)

                        if len(prs) >= max_prs:
                            break

                    page_num += 1

                    # Safety: don't go beyond 10 pages
                    if page_num > 10:
                        break

            finally:
                browser.close()
                # Clean up session
                try:
                    self.browserbase.sessions.delete(session.id)
                except:
                    pass

        print(f"✅ Scraped {len(prs)} PRs from {repo}")
        return prs

    def _scrape_single_pr(self, page: Page, pr_url: str, repo: str) -> Optional[Dict]:
        """
        Scrape data from a single PR page.

        Args:
            page: Playwright page object
            pr_url: URL of the PR
            repo: Repository name

        Returns:
            Dictionary with PR data or None if PR should be filtered
        """
        try:
            page.goto(pr_url, wait_until="domcontentloaded")
            time.sleep(1)

            # Extract PR number
            pr_number = pr_url.split('/pull/')[-1].split('/')[0]

            # Extract title
            title_elem = page.query_selector('h1.gh-header-title bdi, h1 bdi')
            title = title_elem.inner_text().strip() if title_elem else ""

            # Filter merge commits
            if is_merge_commit(title):
                return None

            # Extract author
            author_elem = page.query_selector('a.author, [data-hovercard-type="user"]')
            author = author_elem.inner_text().strip() if author_elem else ""

            # Filter bot authors
            if is_bot_author(author):
                return None

            # Extract description
            description = ""
            desc_elem = page.query_selector('.comment-body')
            if desc_elem:
                description = desc_elem.inner_text().strip()

            # Extract merge date
            merged_date = ""
            merge_elem = page.query_selector('relative-time[datetime]')
            if merge_elem:
                merged_date = merge_elem.get_attribute('datetime') or ""

            # Check if PR is too old
            if merged_date:
                try:
                    merge_dt = datetime.fromisoformat(merged_date.replace('Z', '+00:00'))
                    age_days = (datetime.now(merge_dt.tzinfo) - merge_dt).days
                    if age_days > MAX_PR_AGE_DAYS:
                        return None
                except:
                    pass

            # Navigate to Files Changed tab
            files_url = f"{pr_url}/files"
            page.goto(files_url, wait_until="domcontentloaded")
            time.sleep(1)

            # Extract file paths and changes
            file_paths = []
            lines_changed = 0

            file_headers = page.query_selector_all('[data-path]')
            for header in file_headers:
                file_path = header.get_attribute('data-path')
                if file_path:
                    file_paths.append(file_path)

            # Extract total lines changed (additions + deletions)
            diff_stats = page.query_selector('.diffbar-item')
            if diff_stats:
                text = diff_stats.inner_text()
                # Extract numbers from text like "+123 −45"
                import re
                numbers = re.findall(r'\d+', text)
                lines_changed = sum(int(n) for n in numbers)

            # Filter PRs with too few changes
            if lines_changed < MIN_LINES_CHANGED:
                return None

            # Extract tech keywords from file paths
            tech_keywords = extract_tech_keywords_from_paths(file_paths)

            # Build PR data
            pr_data = {
                "pr_id": f"{repo}#{pr_number}",
                "pr_number": pr_number,
                "title": title,
                "description": description,
                "author": author,
                "repo": repo,
                "file_paths": file_paths,
                "tech_keywords": tech_keywords,
                "lines_changed": lines_changed,
                "merged_date": merged_date,
                "pr_url": pr_url
            }

            return pr_data

        except Exception as e:
            print(f"    Error scraping {pr_url}: {e}")
            return None


def scrape_repositories(repos: List[str], output_file: str = "data/raw_prs.json") -> List[Dict]:
    """
    Scrape PRs from multiple repositories.

    Args:
        repos: List of repositories in format "owner/repo"
        output_file: Path to save scraped data

    Returns:
        List of all scraped PRs
    """
    scraper = GitHubPRScraper()
    all_prs = []

    for repo in repos:
        try:
            prs = scraper.scrape_repo_prs(repo)
            all_prs.extend(prs)
        except Exception as e:
            print(f"❌ Error scraping {repo}: {e}")
            continue

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_prs, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Scraped {len(all_prs)} total PRs")
    print(f"📁 Saved to {output_file}")

    return all_prs


if __name__ == "__main__":
    # Test with a single repo
    from config import TARGET_REPOS

    prs = scrape_repositories(TARGET_REPOS[:1])  # Start with just one repo
    print(f"\nSample PR:")
    if prs:
        print(json.dumps(prs[0], indent=2))
