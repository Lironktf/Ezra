"""Utility functions for GitHub Expert Finder."""
import re
from pathlib import Path
from typing import List, Set
from config import GENERIC_TERMS


def extract_tech_keywords(file_path: str) -> List[str]:
    """
    Extract technology keywords from a file path.

    Examples:
        '/src/graphql/schema/user.graphql' -> ['graphql', 'schema']
        '/api/resolvers/typescript/index.ts' -> ['api', 'resolvers', 'typescript']
        '/components/hooks/useQuery.tsx' -> ['hooks', 'react']

    Args:
        file_path: Path to a file in a repository

    Returns:
        List of technology keywords extracted from the path
    """
    if not file_path:
        return []

    # Get path parts and file name
    path = Path(file_path)
    parts = path.parts
    file_name = path.stem  # filename without extension
    extension = path.suffix.lstrip('.')

    keywords: Set[str] = set()

    # Extract from directory path
    for part in parts:
        # Split on common separators
        tokens = re.split(r'[-_./\\]', part.lower())
        for token in tokens:
            # Remove numbers and clean
            token = re.sub(r'\d+', '', token).strip()
            # Keep meaningful tokens
            if len(token) > 2 and token not in GENERIC_TERMS:
                keywords.add(token)

    # Extract from filename (camelCase, snake_case, kebab-case)
    if file_name and file_name.lower() not in GENERIC_TERMS:
        # Split camelCase
        tokens = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+', file_name)
        for token in tokens:
            token = token.lower().strip()
            if len(token) > 2 and token not in GENERIC_TERMS:
                keywords.add(token)

    # Detect React hooks patterns
    hooks_patterns = [
        'usestate', 'useeffect', 'usecontext', 'usereducer', 'usecallback',
        'usememo', 'useref', 'useimperativehandle', 'uselayouteffect',
        'usedebugvalue', 'useid', 'usetransition', 'usedeferredvalue',
        'usesyncexternalstore', 'useinsertioneffect', 'useoptimistic',
        'useactionstate', 'use'  # React 19 hooks
    ]

    file_path_lower = file_path.lower()
    for hook in hooks_patterns:
        if hook in file_path_lower or hook in file_name.lower():
            keywords.add('hooks')
            keywords.add(hook)
            break

    # Add file extension as technology indicator
    if extension and extension not in GENERIC_TERMS:
        # Map common extensions to technologies
        ext_mapping = {
            'tsx': 'react',
            'jsx': 'react',
            'vue': 'vue',
            'svelte': 'svelte',
            'graphql': 'graphql',
            'gql': 'graphql',
            'sql': 'sql',
            'prisma': 'prisma',
            'proto': 'protobuf',
            'go': 'golang',
            'rs': 'rust',
            'kt': 'kotlin',
            'swift': 'swift',
            'rb': 'ruby',
            'php': 'php',
            'java': 'java',
            'scala': 'scala',
            'cpp': 'cpp',
            'dockerfile': 'docker',
            'tf': 'terraform',
        }
        tech = ext_mapping.get(extension.lower(), extension.lower())
        if tech not in GENERIC_TERMS:
            keywords.add(tech)

    # Filter out remaining generic terms and sort
    filtered = [kw for kw in keywords if kw not in GENERIC_TERMS]
    return sorted(filtered)


def extract_tech_keywords_from_paths(file_paths: List[str]) -> List[str]:
    """
    Extract unique technology keywords from multiple file paths.

    Args:
        file_paths: List of file paths

    Returns:
        Sorted list of unique technology keywords
    """
    all_keywords: Set[str] = set()
    for path in file_paths:
        keywords = extract_tech_keywords(path)
        all_keywords.update(keywords)
    return sorted(all_keywords)


def is_bot_author(username: str) -> bool:
    """Check if a username is likely a bot."""
    from config import BOT_AUTHORS

    if not username:
        return True

    username_lower = username.lower()

    # Check against known bots
    if username_lower in BOT_AUTHORS:
        return True

    # Check for bot-like patterns
    bot_patterns = ['bot', 'automated', 'dependabot', 'renovate']
    return any(pattern in username_lower for pattern in bot_patterns)


def is_merge_commit(pr_title: str) -> bool:
    """Check if a PR title indicates a merge commit."""
    if not pr_title:
        return False

    title_lower = pr_title.lower()
    merge_patterns = [
        'merge pull request',
        'merge branch',
        'merge remote',
        'auto merge',
        'automated merge'
    ]
    return any(pattern in title_lower for pattern in merge_patterns)


def clean_text(text: str) -> str:
    """Clean and normalize text for embedding."""
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove special characters that don't add meaning
    text = re.sub(r'[^\w\s\-.,!?]', '', text)

    return text.strip()


def format_pr_text_for_embedding(title: str, description: str, tech_keywords: List[str]) -> str:
    """
    Format PR information into text suitable for embedding.

    Args:
        title: PR title
        description: PR description
        tech_keywords: List of technology keywords

    Returns:
        Formatted text string
    """
    title = clean_text(title) if title else ""
    description = clean_text(description) if description else ""

    # Build text components
    components = []

    if title:
        components.append(title)

    if description:
        # Limit description length (embeddings work better with concise text)
        if len(description) > 500:
            description = description[:500] + "..."
        components.append(description)

    if tech_keywords:
        tech_text = f"Technologies: {', '.join(tech_keywords)}"
        components.append(tech_text)

    # If we have nothing, return empty string (will be filtered out)
    if not components:
        return ""

    return ". ".join(components)
