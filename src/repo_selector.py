"""Repository selector using Groq LLM."""
import os
import json
from typing import List, Dict
from groq import Groq

# Popular GitHub repositories organized by category
REPO_DATABASE = {
    "react": [
        "facebook/react",
        "vercel/next.js",
        "remix-run/remix",
        "facebook/react-native",
        "preactjs/preact",
    ],
    "vue": [
        "vuejs/core",
        "nuxt/nuxt",
        "vuejs/vue",
        "quasarframework/quasar",
    ],
    "angular": [
        "angular/angular",
        "angular/angular-cli",
    ],
    "state_management": [
        "reduxjs/redux",
        "reduxjs/redux-toolkit",
        "pmndrs/zustand",
        "pmndrs/jotai",
        "dai-shi/valtio",
        "mobxjs/mobx",
    ],
    "data_fetching": [
        "tanstack/query",
        "apollographql/apollo-client",
        "swr/swr",
        "trpc/trpc",
    ],
    "typescript": [
        "microsoft/TypeScript",
        "type-challenges/type-challenges",
    ],
    "graphql": [
        "graphql/graphql-js",
        "apollographql/apollo-server",
        "dotansimha/graphql-code-generator",
    ],
    "backend": [
        "expressjs/express",
        "nestjs/nest",
        "fastify/fastify",
        "koajs/koa",
    ],
    "database": [
        "prisma/prisma",
        "typeorm/typeorm",
        "drizzle-team/drizzle-orm",
        "supabase/supabase",
    ],
    "testing": [
        "facebook/jest",
        "vitest-dev/vitest",
        "testing-library/react-testing-library",
        "playwright/playwright",
        "cypress-io/cypress",
    ],
    "build_tools": [
        "vitejs/vite",
        "webpack/webpack",
        "esbuild/esbuild",
        "swc-project/swc",
    ],
    "ui_libraries": [
        "mui/material-ui",
        "chakra-ui/chakra-ui",
        "tailwindlabs/tailwindcss",
        "ant-design/ant-design",
    ],
    "nodejs": [
        "nodejs/node",
        "denoland/deno",
        "oven-sh/bun",
    ],
    "python": [
        "python/cpython",
        "django/django",
        "fastapi/fastapi",
        "flask/flask",
    ],
    "rust": [
        "rust-lang/rust",
        "tokio-rs/tokio",
        "actix/actix-web",
    ],
    "go": [
        "golang/go",
        "gin-gonic/gin",
        "gofiber/fiber",
    ],
    "machine_learning": [
        "pytorch/pytorch",
        "tensorflow/tensorflow",
        "huggingface/transformers",
        "scikit-learn/scikit-learn",
        "openai/gym",
        "ray-project/ray",
        "microsoft/DeepSpeed",
        "facebookresearch/faiss",
        "pytorch/ignite",
        "keras-team/keras",
    ],
    "ai_research": [
        "openai/openai-python",
        "langchain-ai/langchain",
        "microsoft/semantic-kernel",
        "run-llama/llama_index",
        "huggingface/diffusers",
        "stability-ai/stable-diffusion",
        "EleutherAI/gpt-neox",
    ],
    "data_science": [
        "pandas-dev/pandas",
        "apache/spark",
        "dask/dask",
        "plotly/plotly.py",
        "matplotlib/matplotlib",
        "jupyter/notebook",
    ],
    "vector_database": [
        "qdrant/qdrant",
        "chroma-core/chroma",
        "weaviate/weaviate",
        "milvus-io/milvus",
        "pgvector/pgvector",
        "facebookresearch/faiss",
        "spotify/annoy",
        "nmslib/hnswlib",
    ],
    "linux_systems": [
        "torvalds/linux",
        "systemd/systemd",
        "util-linux/util-linux",
        "linux-pam/linux-pam",
        "SELinuxProject/selinux",
        "zfsonlinux/zfs",
        "openzfs/zfs",
    ],
    "operating_systems": [
        "torvalds/linux",
        "freebsd/freebsd-src",
        "apple-oss-distributions/xnu",
        "reactos/reactos",
        "seL4/seL4",
        "redox-os/redox",
        "minix3/minix",
    ],
    "systems_programming": [
        "rust-lang/rust",
        "llvm/llvm-project",
        "gcc-mirror/gcc",
        "bminor/glibc",
        "emscripten-core/emscripten",
        "nickel-lang/nickel",
    ],
    "embedded_systems": [
        "zephyrproject-rtos/zephyr",
        "apache/nuttx",
        "micropython/micropython",
        "espressif/esp-idf",
        "ARMmbed/mbed-os",
        "RIOT-OS/RIOT",
    ],
}


class RepoSelector:
    """Select relevant repositories using Groq LLM."""

    def __init__(self, api_key: str = None):
        """Initialize with Groq API key."""
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment")

        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.1-8b-instant"  # Smaller, faster model - uses fewer tokens, higher rate limits

    def select_repositories(self, query: str, max_repos: int = 3) -> List[str]:
        """
        Select the most relevant repositories for a query using LLM.

        Args:
            query: User's natural language query
            max_repos: Maximum number of repositories to return

        Returns:
            List of repository names (e.g., ["facebook/react", "vercel/next.js"])
        """
        # Flatten repo database for context
        all_repos = []
        for category, repos in REPO_DATABASE.items():
            all_repos.extend(repos)

        # Create prompt for LLM
        prompt = f"""You are a GitHub repository expert. Given a technical query, select the {max_repos} MOST relevant GitHub repositories from this list.

Available repositories:
{json.dumps(list(set(all_repos)), indent=2)}

User Query: "{query}"

CRITICAL RULES - Read carefully:
1. For Linux kernel/OS development: Use "torvalds/linux", "systemd/systemd", "freebsd/freebsd-src" - NOT "microsoft/semantic-kernel" (that's an AI framework, not an OS kernel!)
2. For vector databases/embeddings: Use "qdrant/qdrant", "chroma-core/chroma", "milvus-io/milvus", "facebookresearch/faiss"
3. For web development (React, Vue): Use the web framework repos
4. For ML/AI: Use "pytorch/pytorch", "tensorflow/tensorflow", "huggingface/transformers"
5. For embedded/RTOS: Use "zephyrproject-rtos/zephyr", "micropython/micropython", "espressif/esp-idf"

Match the query intent precisely:
- "kernel" in Linux context = torvalds/linux
- "kernel" in ML context = could be pytorch/tensorflow
- "semantic kernel" = microsoft/semantic-kernel (AI framework)

Return ONLY a JSON array of repository names. Example: ["torvalds/linux", "systemd/systemd"]

Selected repositories:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that selects relevant GitHub repositories. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent selection
                max_tokens=200,
            )

            result = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                selected_repos = json.loads(result)

                # Validate repositories
                valid_repos = [repo for repo in selected_repos if repo in all_repos]

                if not valid_repos:
                    # Fallback to default repos
                    print("⚠️  LLM didn't return valid repos, using defaults")
                    return self._get_default_repos(query, max_repos)

                return valid_repos[:max_repos]

            except json.JSONDecodeError:
                print(f"⚠️  Failed to parse LLM response: {result}")
                return self._get_default_repos(query, max_repos)

        except Exception as e:
            print(f"❌ Error calling Groq API: {e}")
            return self._get_default_repos(query, max_repos)

    def _get_default_repos(self, query: str, max_repos: int) -> List[str]:
        """Fallback repository selection using keyword matching."""
        query_lower = query.lower()

        # Simple keyword-based matching
        if any(word in query_lower for word in ["react", "hook", "jsx", "tsx", "component"]):
            return ["facebook/react", "vercel/next.js", "tanstack/query"][:max_repos]
        elif any(word in query_lower for word in ["vue", "nuxt"]):
            return ["vuejs/core", "nuxt/nuxt"][:max_repos]
        elif any(word in query_lower for word in ["typescript", "type", "generic"]):
            return ["microsoft/TypeScript", "facebook/react", "vercel/next.js"][:max_repos]
        elif any(word in query_lower for word in ["graphql", "apollo", "query"]):
            return ["apollographql/apollo-server", "apollographql/apollo-client", "graphql/graphql-js"][:max_repos]
        elif any(word in query_lower for word in ["state", "redux", "zustand"]):
            return ["reduxjs/redux-toolkit", "pmndrs/zustand", "pmndrs/jotai"][:max_repos]
        elif any(word in query_lower for word in ["test", "jest", "vitest"]):
            return ["facebook/jest", "vitest-dev/vitest", "testing-library/react-testing-library"][:max_repos]
        elif any(word in query_lower for word in ["next", "nextjs"]):
            return ["vercel/next.js", "facebook/react"][:max_repos]
        elif any(word in query_lower for word in ["rl", "reinforcement", "learning", "model", "neural", "deep learning", "machine learning", "ml", "ai", "pytorch", "tensorflow", "gym"]):
            return ["pytorch/pytorch", "tensorflow/tensorflow", "openai/gym", "huggingface/transformers", "ray-project/ray"][:max_repos]
        elif any(word in query_lower for word in ["data", "pandas", "numpy", "analysis"]):
            return ["pandas-dev/pandas", "apache/spark", "matplotlib/matplotlib"][:max_repos]
        elif any(word in query_lower for word in ["vector", "embedding", "similarity", "qdrant", "pinecone", "chroma", "milvus", "faiss", "ann", "nearest neighbor"]):
            return ["qdrant/qdrant", "chroma-core/chroma", "weaviate/weaviate", "milvus-io/milvus", "facebookresearch/faiss"][:max_repos]
        elif any(word in query_lower for word in ["linux", "kernel", "operating system", "os", "driver", "syscall", "systemd", "bootloader", "grub"]):
            return ["torvalds/linux", "systemd/systemd", "freebsd/freebsd-src", "zephyrproject-rtos/zephyr", "redox-os/redox"][:max_repos]
        elif any(word in query_lower for word in ["embedded", "rtos", "microcontroller", "firmware", "iot", "arduino", "esp32", "raspberry"]):
            return ["zephyrproject-rtos/zephyr", "apache/nuttx", "micropython/micropython", "espressif/esp-idf", "RIOT-OS/RIOT"][:max_repos]
        elif any(word in query_lower for word in ["compiler", "llvm", "gcc", "assembly", "low level", "systems programming"]):
            return ["llvm/llvm-project", "rust-lang/rust", "gcc-mirror/gcc", "bminor/glibc"][:max_repos]
        elif any(word in query_lower for word in ["database", "sql", "postgres", "mysql", "mongodb"]):
            return ["prisma/prisma", "typeorm/typeorm", "drizzle-team/drizzle-orm", "supabase/supabase"][:max_repos]
        else:
            # Default to popular general repos
            return ["facebook/react", "vercel/next.js", "microsoft/TypeScript"][:max_repos]

    def explain_selection(self, query: str, selected_repos: List[str]) -> str:
        """
        Generate explanation for why these repositories were selected.

        Args:
            query: User's query
            selected_repos: List of selected repositories

        Returns:
            Human-readable explanation
        """
        prompt = f"""Explain in 1-2 sentences why these GitHub repositories are the best places to find experts for this query:

Query: "{query}"
Selected Repositories: {", ".join(selected_repos)}

Provide a brief, technical explanation of why these repositories are relevant."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,
                max_tokens=150,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"Selected repositories related to: {query}"


if __name__ == "__main__":
    # Test the selector
    selector = RepoSelector()

    test_queries = [
        "useEffect cleanup functions preventing memory leaks",
        "GraphQL N+1 query optimization with DataLoader",
        "TypeScript generic constraints for React components",
        "Next.js server actions with form validation",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        repos = selector.select_repositories(query, max_repos=3)
        print(f"Selected: {repos}")
        explanation = selector.explain_selection(query, repos)
        print(f"Why: {explanation}")
