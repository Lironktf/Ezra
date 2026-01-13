"""Qdrant vector database interface for GitHub Expert Finder."""
import json
from typing import List, Dict, Optional
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    Range,
    MatchAny
)
from tqdm import tqdm

from config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_API_KEY,
    COLLECTION_NAME,
    EMBEDDING_DIMENSION
)


class QdrantDB:
    """Interface to Qdrant vector database."""

    def __init__(self, use_memory: bool = False):
        """
        Initialize Qdrant client.

        Args:
            use_memory: If True, use in-memory mode (for testing)
        """
        if use_memory:
            self.client = QdrantClient(":memory:")
            print("🧠 Using in-memory Qdrant")
        else:
            if QDRANT_API_KEY:
                # Cloud mode
                self.client = QdrantClient(
                    url=f"https://{QDRANT_HOST}",
                    api_key=QDRANT_API_KEY
                )
                print(f"☁️  Connected to Qdrant Cloud at {QDRANT_HOST}")
            else:
                # Local mode
                self.client = QdrantClient(
                    host=QDRANT_HOST,
                    port=QDRANT_PORT
                )
                print(f"🔌 Connected to local Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")

        self.collection_name = COLLECTION_NAME

    def create_collection(self, recreate: bool = False):
        """
        Create the vector collection.

        Args:
            recreate: If True, delete existing collection first
        """
        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if exists:
            if recreate:
                print(f"🗑️  Deleting existing collection: {self.collection_name}")
                self.client.delete_collection(self.collection_name)
            else:
                print(f"✅ Collection {self.collection_name} already exists")
                return

        # Create collection
        print(f"🆕 Creating collection: {self.collection_name}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE
            )
        )
        print("✅ Collection created")

    def upload_prs(self, prs: List[Dict], batch_size: int = 100):
        """
        Upload PRs to Qdrant.

        Args:
            prs: List of PR dictionaries with embeddings
            batch_size: Number of PRs to upload per batch
        """
        print(f"\n📤 Uploading {len(prs)} PRs to Qdrant...")

        points = []
        for idx, pr in enumerate(prs):
            # Skip PRs without embeddings
            if 'embedding' not in pr or not pr['embedding']:
                continue

            # Create point
            point = PointStruct(
                id=idx,
                vector=pr['embedding'],
                payload={
                    'pr_id': pr.get('pr_id', ''),
                    'pr_number': pr.get('pr_number', ''),
                    'title': pr.get('title', ''),
                    'description': pr.get('description', ''),
                    'author': pr.get('author', ''),
                    'repo': pr.get('repo', ''),
                    'tech_keywords': pr.get('tech_keywords', []),
                    'lines_changed': pr.get('lines_changed', 0),
                    'merged_date': pr.get('merged_date', ''),
                    'pr_url': pr.get('pr_url', ''),
                    'text_for_embedding': pr.get('text_for_embedding', '')
                }
            )
            points.append(point)

        # Upload in batches
        for i in tqdm(range(0, len(points), batch_size), desc="Uploading batches"):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )

        print(f"✅ Uploaded {len(points)} PRs to Qdrant")

    def search(
        self,
        query_vector: List[float],
        limit: int = 50,
        tech_filter: Optional[List[str]] = None,
        repo_filter: Optional[str] = None,
        min_lines: Optional[int] = None
    ) -> List[Dict]:
        """
        Search for similar PRs.

        Args:
            query_vector: Query embedding vector
            limit: Number of results to return
            tech_filter: Filter by technology keywords
            repo_filter: Filter by repository

        Returns:
            List of matching PR dictionaries with scores
        """
        # Build filter
        must_conditions = []

        if tech_filter:
            must_conditions.append(
                FieldCondition(
                    key="tech_keywords",
                    match=MatchAny(any=tech_filter)
                )
            )

        if repo_filter:
            must_conditions.append(
                FieldCondition(
                    key="repo",
                    match=repo_filter
                )
            )
        
        if min_lines is not None:
            must_conditions.append(
                FieldCondition(
                    key="lines_changed",
                    range=Range(gte=min_lines)
                )
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        # Search (using query_points for newer qdrant-client)
        try:
            # Try newer API (query_points)
            from qdrant_client.models import QueryRequest
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=query_filter
            ).points
        except (AttributeError, ImportError):
            # Fallback to older API (search)
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter
            )

        # Format results
        formatted_results = []
        for result in results:
            pr_data = dict(result.payload)
            pr_data['similarity_score'] = result.score
            formatted_results.append(pr_data)

        return formatted_results

    def get_collection_info(self) -> Dict:
        """Get information about the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            result = {
                'name': self.collection_name,
                'points_count': info.points_count,
                'status': info.status
            }
            # Add vectors_count if available (older API)
            if hasattr(info, 'vectors_count'):
                result['vectors_count'] = info.vectors_count
            return result
        except Exception as e:
            return {'error': str(e)}


def setup_vector_db(
    input_file: str = "data/embedded_prs.json",
    use_memory: bool = False,
    recreate: bool = False
):
    """
    Set up Qdrant database and upload PR data.

    Args:
        input_file: Path to embedded PR JSON file
        use_memory: Use in-memory mode
        recreate: Recreate collection if exists
    """
    # Load embedded PRs
    with open(input_file, 'r', encoding='utf-8') as f:
        prs = json.load(f)

    print(f"📂 Loaded {len(prs)} embedded PRs from {input_file}")

    # Initialize database
    db = QdrantDB(use_memory=use_memory)

    # Create collection
    db.create_collection(recreate=recreate)

    # Upload PRs
    db.upload_prs(prs)

    # Show info
    info = db.get_collection_info()
    print(f"\n📊 Collection Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    return db


if __name__ == "__main__":
    # Test setup
    db = setup_vector_db(use_memory=True, recreate=True)

    print("\n✅ Vector database setup complete!")
