#!/usr/bin/env python3
"""
GitHub Expert Finder - Main CLI Interface

Find domain experts on GitHub by analyzing their PR history.
"""
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scraper_factory import scrape_repositories
from embedder import embed_pr_data
from vector_db import setup_vector_db
from query import ExpertFinder
from config import TARGET_REPOS


def scrape_command(args):
    """Scrape GitHub repositories for PRs."""
    repos = args.repos if args.repos else TARGET_REPOS
    output_file = args.output or "data/raw_prs.json"

    print(f"🚀 Starting scrape of {len(repos)} repositories...")
    print(f"Repos: {', '.join(repos)}")

    prs = scrape_repositories(repos, output_file)

    print(f"\n✅ Scraping complete! Saved {len(prs)} PRs to {output_file}")


def embed_command(args):
    """Generate embeddings for scraped PRs."""
    input_file = args.input or "data/raw_prs.json"
    output_file = args.output or "data/embedded_prs.json"

    if not Path(input_file).exists():
        print(f"❌ Input file not found: {input_file}")
        print("Run 'python main.py scrape' first to collect PR data")
        return

    print(f"🚀 Generating embeddings for PRs in {input_file}...")

    embedded_prs = embed_pr_data(input_file, output_file)

    print(f"\n✅ Embedding complete! Saved {len(embedded_prs)} embedded PRs to {output_file}")


def setup_command(args):
    """Set up vector database and upload PR data."""
    input_file = args.input or "data/embedded_prs.json"

    if not Path(input_file).exists():
        print(f"❌ Input file not found: {input_file}")
        print("Run 'python main.py embed' first to generate embeddings")
        return

    print(f"🚀 Setting up vector database...")

    db = setup_vector_db(
        input_file=input_file,
        use_memory=args.memory,
        recreate=args.recreate
    )

    print(f"\n✅ Database setup complete!")


def search_command(args):
    """Search for experts."""
    query = args.query

    if not query:
        print("❌ Please provide a query with -q/--query")
        return

    print(f"🚀 Searching for experts...")

    finder = ExpertFinder(use_memory=args.memory)

    try:
        experts = finder.find_experts(
            query=query,
            top_n=args.top_n,
            repo_filter=args.repo
        )

        # Display results
        output = finder.format_results(experts, show_top_n=args.top_n)
        print(output)

        # Optionally save to file
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"\n💾 Saved results to {args.output}")

    except Exception as e:
        print(f"❌ Error during search: {e}")
        import traceback
        traceback.print_exc()


def pipeline_command(args):
    """Run the full pipeline: scrape -> embed -> setup -> search."""
    repos = args.repos if args.repos else TARGET_REPOS

    print("=" * 80)
    print("RUNNING FULL PIPELINE")
    print("=" * 80)

    # Step 1: Scrape
    print("\n📍 STEP 1/4: Scraping PRs...")
    scrape_args = argparse.Namespace(
        repos=repos,
        output="data/raw_prs.json"
    )
    scrape_command(scrape_args)

    # Step 2: Embed
    print("\n📍 STEP 2/4: Generating embeddings...")
    embed_args = argparse.Namespace(
        input="data/raw_prs.json",
        output="data/embedded_prs.json"
    )
    embed_command(embed_args)

    # Step 3: Setup DB
    print("\n📍 STEP 3/4: Setting up vector database...")
    db = setup_vector_db(
        input_file="data/embedded_prs.json",
        use_memory=args.memory,
        recreate=True
    )

    # Step 4: Search (if query provided)
    if args.query:
        print("\n📍 STEP 4/4: Searching for experts...")
        # For in-memory mode, use the same DB instance
        if args.memory:
            finder = ExpertFinder(use_memory=False)  # Don't create new DB
            finder.db = db  # Use the DB we just created
        else:
            finder = ExpertFinder(use_memory=args.memory)

        try:
            experts = finder.find_experts(
                query=args.query,
                top_n=args.top_n or 5,
                repo_filter=None
            )

            # Display results
            output = finder.format_results(experts, show_top_n=args.top_n or 5)
            print(output)

            # Optionally save to file
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output)
                print(f"\n💾 Saved results to {args.output}")

        except Exception as e:
            print(f"❌ Error during search: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n✅ Pipeline complete! Use 'python main.py search -q \"your question\"' to find experts")


def interactive_command(args):
    """Interactive mode for searching experts."""
    print("=" * 80)
    print("GITHUB EXPERT FINDER - Interactive Mode")
    print("=" * 80)
    print("Ask technical questions to find GitHub experts who can help!")
    print("Type 'quit' or 'exit' to stop.\n")

    finder = ExpertFinder(use_memory=args.memory)

    while True:
        try:
            query = input("\n🔍 Your question: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break

            if not query:
                continue

            experts = finder.find_experts(query, top_n=args.top_n or 5)
            output = finder.format_results(experts, show_top_n=args.top_n or 5)
            print(output)

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="GitHub Expert Finder - Find domain experts by analyzing PR history",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Scrape GitHub PRs')
    scrape_parser.add_argument('-r', '--repos', nargs='+', help='Repositories to scrape (owner/repo)')
    scrape_parser.add_argument('-o', '--output', help='Output JSON file')

    # Embed command
    embed_parser = subparsers.add_parser('embed', help='Generate embeddings')
    embed_parser.add_argument('-i', '--input', help='Input JSON file with scraped PRs')
    embed_parser.add_argument('-o', '--output', help='Output JSON file for embedded PRs')

    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup vector database')
    setup_parser.add_argument('-i', '--input', help='Input JSON file with embedded PRs')
    setup_parser.add_argument('-m', '--memory', action='store_true', help='Use in-memory database')
    setup_parser.add_argument('--recreate', action='store_true', help='Recreate collection if exists')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for experts')
    search_parser.add_argument('-q', '--query', required=True, help='Search query')
    search_parser.add_argument('-n', '--top-n', type=int, default=5, help='Number of experts to return')
    search_parser.add_argument('-m', '--memory', action='store_true', help='Use in-memory database')
    search_parser.add_argument('-r', '--repo', help='Filter by repository')
    search_parser.add_argument('-o', '--output', help='Save results to file')

    # Pipeline command (run everything)
    pipeline_parser = subparsers.add_parser('pipeline', help='Run full pipeline')
    pipeline_parser.add_argument('-r', '--repos', nargs='+', help='Repositories to scrape')
    pipeline_parser.add_argument('-q', '--query', help='Search query (optional)')
    pipeline_parser.add_argument('-n', '--top-n', type=int, help='Number of experts to return')
    pipeline_parser.add_argument('-m', '--memory', action='store_true', help='Use in-memory database')
    pipeline_parser.add_argument('-o', '--output', help='Save results to file')

    # Interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Interactive search mode')
    interactive_parser.add_argument('-n', '--top-n', type=int, default=5, help='Number of experts to return')
    interactive_parser.add_argument('-m', '--memory', action='store_true', help='Use in-memory database')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to appropriate command
    if args.command == 'scrape':
        scrape_command(args)
    elif args.command == 'embed':
        embed_command(args)
    elif args.command == 'setup':
        setup_command(args)
    elif args.command == 'search':
        search_command(args)
    elif args.command == 'pipeline':
        pipeline_command(args)
    elif args.command == 'interactive':
        interactive_command(args)


if __name__ == "__main__":
    main()
