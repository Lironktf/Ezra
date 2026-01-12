"""Factory for choosing between different scraper implementations."""
from typing import List, Dict

from config import SCRAPER_PROVIDER


def scrape_repositories(
    repos: List[str],
    output_file: str = "data/raw_prs.json",
    provider: str = None
) -> List[Dict]:
    """
    Scrape PRs from multiple repositories using the configured scraper.

    Args:
        repos: List of repositories in format "owner/repo"
        output_file: Path to save scraped data
        provider: Override scraper provider ("github_api" or "browserbase")

    Returns:
        List of all scraped PRs
    """
    scraper_type = provider or SCRAPER_PROVIDER

    print(f"🤖 Using {scraper_type} scraper")

    if scraper_type == "github_api":
        from github_api_scraper import scrape_repositories as github_scrape
        return github_scrape(repos, output_file)
    elif scraper_type == "browserbase":
        from scraper import scrape_repositories as browserbase_scrape
        return browserbase_scrape(repos, output_file)
    else:
        raise ValueError(
            f"Unknown scraper provider: {scraper_type}. "
            f"Use 'github_api' or 'browserbase'"
        )


if __name__ == "__main__":
    # Test
    from config import TARGET_REPOS

    print("Testing scraper factory...")
    prs = scrape_repositories(TARGET_REPOS[:1])
    print(f"✅ Scraped {len(prs)} PRs")
