"""Gating service for discovered vs published MCP tools.

Skeleton implementation: tracks discovered tools per server and a published set
that will later be used to filter listTools and enforce callTool.
"""

from __future__ import annotations

from typing import Dict, List, Set, Iterable, Optional
from dataclasses import dataclass, field


@dataclass
class GatingState:
    """Holds discovered and published tool identifiers."""

    # Map server -> discovered tool names (raw MCP names)
    discovered: Dict[str, List[str]] = field(default_factory=dict)
    # Global published tool IDs (format to be normalized by gateway e.g., server_tool)
    published_ids: Set[str] = field(default_factory=set)


class GatingService:
    """Maintain discovered vs published MCP tools and simple gating policy skeleton."""

    def __init__(self, default_policy: str = "deny") -> None:
        self._state = GatingState()
        self._default_policy = default_policy.lower() if default_policy else "deny"

    # Discovered tools management
    def set_discovered(self, server: str, tool_names: Iterable[str]) -> None:
        self._state.discovered[server] = list(dict.fromkeys(tool_names))

    def get_discovered(self, server: Optional[str] = None) -> Dict[str, List[str]] | List[str]:
        if server is None:
            return dict(self._state.discovered)
        return list(self._state.discovered.get(server, []))

    # Publication management
    def publish_ids(self, tool_ids: Iterable[str], replace: bool = False) -> None:
        ids = set(tool_ids)
        if replace:
            self._state.published_ids = ids
        else:
            self._state.published_ids |= ids

    def unpublish_ids(self, tool_ids: Iterable[str]) -> None:
        for tid in tool_ids:
            self._state.published_ids.discard(tid)

    def clear_publication(self) -> None:
        self._state.published_ids.clear()

    def get_published_ids(self) -> Set[str]:
        return set(self._state.published_ids)

    # Queries
    def is_published(self, tool_id: str) -> bool:
        if tool_id in self._state.published_ids:
            return True
        # Default policy can allow everything if explicitly set to allow
        return self._default_policy == "allow"

    def default_policy(self) -> str:
        return self._default_policy

