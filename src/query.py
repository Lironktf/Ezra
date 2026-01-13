"""Query pipeline for finding GitHub experts."""
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

from embedder import PREmbedder
from vector_db import QdrantDB
from config import TOP_K_RESULTS, TOP_N_EXPERTS, MAX_PR_AGE_DAYS


class ExpertFinder:
    """Find domain experts based on PR history."""

    def __init__(self, use_memory: bool = False):
        """
        Initialize expert finder.

        Args:
            use_memory: Use in-memory Qdrant (for testing)
        """
        self.embedder = PREmbedder()
        self.db = QdrantDB(use_memory=use_memory)

    def find_experts(
        self,
        query: str,
        top_n: int = TOP_N_EXPERTS,
        tech_filter: Optional[List[str]] = None,
        repo_filter: Optional[str] = None,
        recency_weight: float = 0.1
    ) -> List[Dict]:
        """
        Find experts who can help with a technical question.

        Args:
            query: Natural language question
            top_n: Number of experts to return
            tech_filter: Filter by specific technologies
            repo_filter: Filter by specific repository
            recency_weight: Weight for recency scoring (0-1)

        Returns:
            List of expert dictionaries with their best PRs
        """
        print(f"\n🔍 Searching for experts: '{query}'")

        # Generate query embedding
        query_embedding = self.embedder.generate_embedding(query)

        # Search vector database - get more results to filter for substantial PRs
        results = self.db.search(
            query_vector=query_embedding,
            limit=TOP_K_RESULTS,  # Get enough results to filter from
            tech_filter=tech_filter,
            repo_filter=repo_filter
        )
        
        # Sort by similarity first, then filter by size
        results.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        # Log size distribution
        if results:
            sizes = [pr.get('lines_changed', 0) for pr in results]
            avg_size = sum(sizes) / len(sizes)
            max_size = max(sizes)
            print(f"📏 PR size stats: avg={avg_size:.0f} lines, max={max_size} lines")

        print(f"📊 Found {len(results)} relevant PRs")

        # Filter PRs by size - prioritize substantial PRs
        from config import MIN_SUBSTANTIAL_PR_LINES
        substantial_prs = [pr for pr in results if pr.get('lines_changed', 0) >= MIN_SUBSTANTIAL_PR_LINES]
        
        if substantial_prs:
            print(f"📈 Filtered to {len(substantial_prs)} substantial PRs (≥{MIN_SUBSTANTIAL_PR_LINES} lines)")
            # Use substantial PRs, but also include smaller ones if we don't have enough
            if len(substantial_prs) >= 20:
                results = substantial_prs
            else:
                # Mix: prioritize substantial, but include some smaller ones
                smaller_prs = [pr for pr in results if pr.get('lines_changed', 0) < MIN_SUBSTANTIAL_PR_LINES]
                # Sort smaller PRs by size (largest first) and take top ones
                smaller_prs.sort(key=lambda x: x.get('lines_changed', 0), reverse=True)
                results = substantial_prs + smaller_prs[:max(10, 20 - len(substantial_prs))]
                print(f"📊 Including {len(smaller_prs[:max(10, 20 - len(substantial_prs))])} additional smaller PRs")
        else:
            print(f"⚠️  No substantial PRs found (≥{MIN_SUBSTANTIAL_PR_LINES} lines), using all results")

        # Post-process and rank
        experts = self._rank_experts(results, recency_weight)

        # Return top N experts (already filtered by quality criteria in _rank_experts)
        top_experts = experts[:top_n]

        print(f"✅ Returning top {len(top_experts)} experts\n")

        return top_experts

    def _rank_experts(self, prs: List[Dict], recency_weight: float = 0.1) -> List[Dict]:
        """
        Rank experts by aggregating their PR contributions.

        Args:
            prs: List of PR results with similarity scores
            recency_weight: Weight for recency in final score

        Returns:
            Ranked list of experts
        """
        # Group PRs by author
        author_prs = defaultdict(list)
        for pr in prs:
            author = pr.get('author', '')
            if author:
                author_prs[author].append(pr)

        # Score each author
        experts = []
        for author, prs_list in author_prs.items():
            # Sort PRs by a combined score: similarity + size boost
            # Bigger PRs get a boost to their similarity score
            from config import MIN_SUBSTANTIAL_PR_LINES
            
            def combined_score(pr):
                similarity = pr.get('similarity_score', 0)
                lines = pr.get('lines_changed', 0)
                
                # Size boost: PRs with more lines get a boost
                # Normalize lines (0-1 scale, assuming max ~5000 lines is very large)
                lines_normalized = min(lines / 5000.0, 1.0)
                
                # Substantial PRs (≥200 lines) get extra boost
                if lines >= MIN_SUBSTANTIAL_PR_LINES:
                    size_boost = 0.15 * lines_normalized  # Up to 15% boost for size
                else:
                    size_boost = 0.05 * lines_normalized  # Smaller boost for smaller PRs
                
                # NEW: Complexity boost (based on files, commits, tests, docs)
                complexity = pr.get('complexity_score', 0.5)  # 0-1 scale
                complexity_boost = complexity * 0.10  # Up to 10% boost for complexity
                
                # NEW: Impact boost (feature > fix > refactor > docs)
                impact = pr.get('impact_score', 0.5)  # 0-1 scale  
                impact_boost = impact * 0.08  # Up to 8% boost for impact
                
                # NEW: Quality indicators
                quality_boost = 0.0
                if pr.get('has_tests', False):
                    quality_boost += 0.03  # 3% for tests
                if pr.get('has_docs', False):
                    quality_boost += 0.02  # 2% for docs
                if pr.get('review_comments_count', 0) > 5:
                    quality_boost += 0.03  # 3% for discussion
                
                return similarity * (1.0 + size_boost + complexity_boost + impact_boost + quality_boost)
            
            # Sort by combined score
            prs_list.sort(key=combined_score, reverse=True)

            # Get best PR for this author
            best_pr = prs_list[0]

            # Calculate aggregate score (consider volume of work, not just best match)
            # Average of top 5 PRs, weighted by their position AND size
            top_5_prs = prs_list[:5]
            top_5_scores = [combined_score(pr) for pr in top_5_prs]
            weights = [1.0, 0.8, 0.6, 0.4, 0.2][:len(top_5_scores)]
            weighted_avg = sum(s * w for s, w in zip(top_5_scores, weights)) / sum(weights)

            # Aggregate tech keywords and calculate technology depth FIRST
            all_tech = set()
            total_lines = 0
            tech_frequency = defaultdict(int)  # Track how often each tech appears
            
            for pr in prs_list:
                all_tech.update(pr.get('tech_keywords', []))
                total_lines += pr.get('lines_changed', 0)
                
                # Count tech frequency for depth analysis
                for tech in pr.get('tech_keywords', []):
                    tech_frequency[tech] += 1
            
            # Calculate technology depth score
            # Authors with multiple PRs in same tech have deeper expertise
            tech_depth_score = 0.0
            if tech_frequency:
                # Get top 3 technologies by frequency
                top_techs = sorted(tech_frequency.items(), key=lambda x: x[1], reverse=True)[:3]
                # Average frequency of top techs (normalized)
                avg_top_frequency = sum(count for _, count in top_techs) / len(top_techs)
                tech_depth_score = min(avg_top_frequency / 5.0, 1.0)  # Normalize (5+ PRs = max)
            
            # Boost score based on number of relevant PRs (volume matters!)
            volume_boost = min(len(prs_list) / 10.0, 1.0)  # Max 10 PRs gives full boost
            
            # Additional boost for authors with substantial PRs
            substantial_count = sum(1 for pr in prs_list if pr.get('lines_changed', 0) >= MIN_SUBSTANTIAL_PR_LINES)
            substantial_boost = min(substantial_count / 5.0, 0.2)  # Up to 20% boost for having multiple substantial PRs
            
            # Technology depth boost - reward specialization
            tech_specialization_boost = tech_depth_score * 0.15  # Up to 15% boost for tech depth
            
            similarity_score = weighted_avg * (0.7 + 0.3 * volume_boost) * (1.0 + substantial_boost + tech_specialization_boost)

            # Apply recency weighting
            recency_score = self._calculate_recency_score(best_pr.get('merged_date', ''))
            final_score = similarity_score * (1 - recency_weight) + recency_score * recency_weight

            # Get top 3 PRs as evidence
            top_prs = prs_list[:3]

            # Build expert profile with enhanced metrics
            expert = {
                'author': author,
                'github_url': f"https://github.com/{author}",
                'score': final_score,
                'similarity_score': similarity_score,
                'recency_score': recency_score,
                'tech_depth_score': tech_depth_score,
                'best_pr': {
                    'title': best_pr.get('title', ''),
                    'url': best_pr.get('pr_url', ''),
                    'repo': best_pr.get('repo', ''),
                    'tech_keywords': best_pr.get('tech_keywords', []),
                    'merged_date': best_pr.get('merged_date', ''),
                    'similarity': best_pr.get('similarity_score', 0),
                    # NEW: Enhanced metrics
                    'complexity_score': best_pr.get('complexity_score', 0),
                    'impact_category': best_pr.get('impact_category', 'unknown'),
                    'files_changed': best_pr.get('files_changed', 0),
                    'commits_count': best_pr.get('commits_count', 0)
                },
                'top_prs': [
                    {
                        'title': pr.get('title', ''),
                        'url': pr.get('pr_url', ''),
                        'repo': pr.get('repo', ''),
                        'similarity': pr.get('similarity_score', 0),
                        'impact_category': pr.get('impact_category', 'unknown'),
                        'lines_changed': pr.get('lines_changed', 0)
                    }
                    for pr in top_prs
                ],
                'tech_expertise': sorted(list(all_tech)),
                'tech_specialization': dict(sorted(tech_frequency.items(), key=lambda x: x[1], reverse=True)[:5]),  # Top 5 techs
                'total_relevant_prs': len(prs_list),
                'total_lines_changed': total_lines,
                'substantial_prs_count': substantial_count
            }

            experts.append(expert)

        # Sort by final score
        experts.sort(key=lambda x: x['score'], reverse=True)
        
        # Filter experts by minimum requirements (OR logic: either condition qualifies)
        from config import MIN_EXPERT_PRS, MIN_EXPERT_TOTAL_LINES
        filtered_experts = []
        for expert in experts:
            pr_count = expert.get('total_relevant_prs', 0)
            total_lines = expert.get('total_lines_changed', 0)
            
            # Use OR logic: either multiple PRs OR substantial total lines
            if pr_count >= MIN_EXPERT_PRS or total_lines >= MIN_EXPERT_TOTAL_LINES:
                filtered_experts.append(expert)
        
        if filtered_experts:
            print(f"✅ {len(filtered_experts)} experts meet criteria ({MIN_EXPERT_PRS}+ PRs OR {MIN_EXPERT_TOTAL_LINES}+ lines)")
        else:
            print(f"⚠️  No experts meet quality criteria, returning all ranked experts")
            filtered_experts = experts

        return filtered_experts

    def _calculate_recency_score(self, merged_date: str) -> float:
        """
        Calculate recency score (0-1, higher = more recent).

        Args:
            merged_date: ISO format date string

        Returns:
            Recency score between 0 and 1
        """
        if not merged_date:
            return 0.0

        try:
            merge_dt = datetime.fromisoformat(merged_date.replace('Z', '+00:00'))
            now = datetime.now(merge_dt.tzinfo)
            age_days = (now - merge_dt).days

            # Normalize by max age (older = lower score)
            # Use exponential decay
            import math
            decay_rate = 0.001  # Adjust this to control decay speed
            score = math.exp(-decay_rate * age_days)

            return max(0.0, min(1.0, score))

        except Exception:
            return 0.0

    def format_results(self, experts: List[Dict], show_top_n: int = 5) -> str:
        """
        Format expert results for display.

        Args:
            experts: List of expert dictionaries
            show_top_n: Number of experts to display

        Returns:
            Formatted string
        """
        output = []
        output.append("=" * 80)
        output.append(f"TOP {min(show_top_n, len(experts))} GITHUB EXPERTS")
        output.append("=" * 80)

        for i, expert in enumerate(experts[:show_top_n], 1):
            output.append(f"\n#{i} {expert['author']}")
            output.append("-" * 80)
            output.append(f"GitHub: {expert['github_url']}")
            output.append(f"Match Score: {expert['similarity_score']:.3f} | Recency: {expert['recency_score']:.3f}")
            output.append(f"Relevant PRs: {expert['total_relevant_prs']} | Lines Changed: {expert['total_lines_changed']:,}")

            # Tech expertise
            tech_tags = expert['tech_expertise'][:10]  # Show top 10
            if tech_tags:
                output.append(f"Tech Expertise: {', '.join(tech_tags)}")

            # Best PR
            best = expert['best_pr']
            output.append(f"\n  Most Relevant PR:")
            output.append(f"  Title: {best['title']}")
            output.append(f"  Repo: {best['repo']}")
            output.append(f"  URL: {best['url']}")
            if best['tech_keywords']:
                output.append(f"  Technologies: {', '.join(best['tech_keywords'][:5])}")

            # Additional PRs
            if len(expert['top_prs']) > 1:
                output.append(f"\n  Other Relevant PRs:")
                for pr in expert['top_prs'][1:]:
                    output.append(f"  - {pr['title']} ({pr['repo']})")
                    output.append(f"    {pr['url']}")

        output.append("\n" + "=" * 80)

        return "\n".join(output)


def search_experts(
    query: str,
    top_n: int = 10,
    use_memory: bool = False
) -> List[Dict]:
    """
    Search for experts (convenience function).

    Args:
        query: Natural language question
        top_n: Number of experts to return
        use_memory: Use in-memory Qdrant

    Returns:
        List of expert dictionaries
    """
    finder = ExpertFinder(use_memory=use_memory)
    experts = finder.find_experts(query, top_n=top_n)
    return experts


if __name__ == "__main__":
    # Test query
    query = "I need help optimizing GraphQL N+1 queries in my Node.js API"

    finder = ExpertFinder(use_memory=True)
    experts = finder.find_experts(query, top_n=5)

    # Display results
    print(finder.format_results(experts))
