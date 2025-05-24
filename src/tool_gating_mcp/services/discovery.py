# Tool discovery service
# Implements semantic search and tag-based tool discovery

from typing import Any

import numpy as np
from numpy.typing import NDArray

from ..models.tool import ToolMatch


class DiscoveryService:
    """Service for discovering relevant tools based on queries and context."""

    def __init__(self, tool_repo: Any) -> None:
        """Initialize discovery service with tool repository."""
        self.tool_repo = tool_repo
        # In production, this would be a real sentence transformer
        # For now, we'll use a mock that can be replaced
        self.encoder: Any = None
        self._tool_embeddings_cache: dict[str, NDArray[np.float64]] = {}

    async def find_relevant_tools(
        self,
        query: str,
        context: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[ToolMatch]:
        """Find tools relevant to the query using semantic search and tag matching."""
        # Get all tools from registry
        all_tools = await self.tool_repo.get_all()

        # Filter by tags if provided
        if tags:
            all_tools = [t for t in all_tools if any(tag in t.tags for tag in tags)]

        # If no tools match filters, return empty list
        if not all_tools:
            return []

        # Compute query embedding
        query_text = f"{query} {context or ''}"
        query_embedding = self._get_embedding(query_text)

        # Score tools by semantic similarity
        tool_scores = []
        for tool in all_tools:
            # Get or compute tool embedding
            tool_text = f"{tool.name} {tool.description} {' '.join(tool.tags)}"
            tool_embedding = self._get_embedding(tool_text, cache_key=tool.id)

            # Compute cosine similarity
            similarity = self._cosine_similarity(query_embedding, tool_embedding)

            # Boost score for exact tag matches
            matched_tags = list(set(tags or []) & set(tool.tags)) if tags else []
            tag_boost = 0.2 * len(matched_tags)

            tool_scores.append(
                ToolMatch(
                    tool=tool,
                    score=float(min(1.0, similarity + tag_boost)),  # Cap at 1.0
                    matched_tags=matched_tags,
                )
            )

        # Sort by score and return top results
        tool_scores.sort(key=lambda x: x.score, reverse=True)
        return tool_scores[:limit]

    def _get_embedding(self, text: str, cache_key: str | None = None) -> NDArray[np.float64]:
        """Get embedding for text, using cache if available."""
        if cache_key and cache_key in self._tool_embeddings_cache:
            return self._tool_embeddings_cache[cache_key]

        # Use encoder if available, otherwise return mock embedding
        embedding: NDArray[np.float64]
        if self.encoder:
            embedding = self.encoder.encode(text)
        else:
            # Mock embedding based on text length and content
            embedding = np.array([0.5, 0.5], dtype=np.float64)  # Simplified for testing

        if cache_key:
            self._tool_embeddings_cache[cache_key] = embedding

        return embedding

    def _cosine_similarity(self, vec1: Any, vec2: Any) -> float:
        """Compute cosine similarity between two vectors."""
        # Handle numpy arrays and lists
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))
