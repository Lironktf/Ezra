"""Generate embeddings for PR data using OpenAI or local models."""
import json
import pickle
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm

from config import (
    EMBEDDING_PROVIDER,
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION
)
from utils import format_pr_text_for_embedding


class PREmbedder:
    """Generate embeddings for GitHub PRs using OpenAI or local models."""

    def __init__(self, provider: str = None):
        """
        Initialize the embedder.

        Args:
            provider: "openai" or "local". If None, uses EMBEDDING_PROVIDER from config
        """
        self.provider = provider or EMBEDDING_PROVIDER
        self.model = EMBEDDING_MODEL
        self.dimension = EMBEDDING_DIMENSION
        self.cache = {}

        print(f"🤖 Using {self.provider} embeddings (model: {self.model}, dim: {self.dimension})")

        if self.provider == "openai":
            self._init_openai()
        else:  # local
            self._init_local()

    def _init_openai(self):
        """Initialize OpenAI client."""
        if not OPENAI_API_KEY:
            raise ValueError(
                "OpenAI API key not configured. "
                "Set OPENAI_API_KEY in .env or use EMBEDDING_PROVIDER=local for free embeddings"
            )

        from openai import OpenAI
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialized")

    def _init_local(self):
        """Initialize local sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )

        print(f"📥 Loading local model: {self.model}...")
        print("   (First time may take a few minutes to download)")
        self.model_encoder = SentenceTransformer(self.model)
        print("✅ Local model loaded")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Check cache
        if text in self.cache:
            return self.cache[text]

        try:
            if self.provider == "openai":
                embedding = self._generate_openai_embedding(text)
            else:  # local
                embedding = self._generate_local_embedding(text)

            # Cache it
            self.cache[text] = embedding

            return embedding

        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * self.dimension

    def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API."""
        response = self.client.embeddings.create(
            input=text,
            model=self.model
        )
        return response.data[0].embedding

    def _generate_local_embedding(self, text: str) -> List[float]:
        """Generate embedding using local model."""
        embedding = self.model_encoder.encode(text, show_progress_bar=False)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (for OpenAI) or batch (for local)

        Returns:
            List of embedding vectors
        """
        embeddings = []

        for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
            batch = texts[i:i + batch_size]

            # Check cache first
            batch_embeddings = []
            uncached_texts = []
            uncached_indices = []

            for idx, text in enumerate(batch):
                if text in self.cache:
                    batch_embeddings.append(self.cache[text])
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(idx)

            # Generate embeddings for uncached texts
            if uncached_texts:
                try:
                    if self.provider == "openai":
                        new_embeddings = self._generate_openai_embeddings_batch(uncached_texts)
                    else:  # local
                        new_embeddings = self._generate_local_embeddings_batch(uncached_texts)

                    # Insert into batch at correct positions and cache
                    for idx, embedding in zip(uncached_indices, new_embeddings):
                        self.cache[uncached_texts[uncached_indices.index(idx)]] = embedding
                        batch_embeddings.insert(idx, embedding)

                except Exception as e:
                    print(f"Error in batch {i}: {e}")
                    # Fill with zeros
                    for idx in uncached_indices:
                        batch_embeddings.insert(idx, [0.0] * self.dimension)

            embeddings.extend(batch_embeddings)

        return embeddings

    def _generate_openai_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API (batch)."""
        response = self.client.embeddings.create(
            input=texts,
            model=self.model
        )
        return [item.embedding for item in response.data]

    def _generate_local_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model (batch)."""
        embeddings = self.model_encoder.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    def embed_prs(self, prs: List[Dict]) -> List[Dict]:
        """
        Generate embeddings for a list of PRs.

        Args:
            prs: List of PR dictionaries

        Returns:
            List of PRs with embeddings added
        """
        print(f"\n🔄 Generating embeddings for {len(prs)} PRs...")

        # Format texts for embedding
        texts = []
        valid_indices = []

        for idx, pr in enumerate(prs):
            text = format_pr_text_for_embedding(
                pr.get('title', ''),
                pr.get('description', ''),
                pr.get('tech_keywords', [])
            )

            if text:  # Only include non-empty texts
                texts.append(text)
                valid_indices.append(idx)

        # Generate embeddings
        embeddings = self.generate_embeddings_batch(texts)

        # Add embeddings to PRs
        embedded_prs = []
        for pr_idx, embedding_idx in enumerate(valid_indices):
            pr = prs[pr_idx].copy()
            pr['text_for_embedding'] = texts[embedding_idx]
            pr['embedding'] = embeddings[embedding_idx]
            embedded_prs.append(pr)

        print(f"✅ Generated {len(embedded_prs)} embeddings")
        return embedded_prs

    def save_cache(self, cache_file: str = "data/embeddings_cache.pkl"):
        """Save embedding cache to disk."""
        cache_path = Path(cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_path, 'wb') as f:
            pickle.dump(self.cache, f)

        print(f"💾 Saved embedding cache to {cache_file}")

    def load_cache(self, cache_file: str = "data/embeddings_cache.pkl"):
        """Load embedding cache from disk."""
        cache_path = Path(cache_file)

        if cache_path.exists():
            with open(cache_path, 'rb') as f:
                self.cache = pickle.load(f)
            print(f"📂 Loaded {len(self.cache)} cached embeddings")
        else:
            print("No cache file found, starting fresh")


def embed_pr_data(
    input_file: str = "data/raw_prs.json",
    output_file: str = "data/embedded_prs.json",
    cache_file: str = "data/embeddings_cache.pkl",
    provider: str = None
) -> List[Dict]:
    """
    Generate embeddings for PR data from a JSON file.

    Args:
        input_file: Path to raw PR JSON file
        output_file: Path to save embedded PR data
        cache_file: Path to embedding cache
        provider: "openai" or "local". If None, uses config

    Returns:
        List of PRs with embeddings
    """
    # Load PR data
    with open(input_file, 'r', encoding='utf-8') as f:
        prs = json.load(f)

    print(f"📂 Loaded {len(prs)} PRs from {input_file}")

    # Initialize embedder and load cache
    embedder = PREmbedder(provider=provider)
    embedder.load_cache(cache_file)

    # Generate embeddings
    embedded_prs = embedder.embed_prs(prs)

    # Save cache
    embedder.save_cache(cache_file)

    # Save embedded data
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(embedded_prs, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved embedded PRs to {output_file}")

    return embedded_prs


if __name__ == "__main__":
    # Test embedding
    print("Testing local embeddings...")
    embedded_prs = embed_pr_data(provider="local")

    if embedded_prs:
        print(f"\nSample embedded PR:")
        sample = embedded_prs[0].copy()
        # Don't print full embedding (too long)
        sample['embedding'] = f"[{len(sample['embedding'])} dimensions]"
        print(json.dumps(sample, indent=2))
