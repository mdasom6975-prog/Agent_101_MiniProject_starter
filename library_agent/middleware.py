"""Harness middleware (명세서 5.5절). TODO(M3: HITL, M4: 나머지)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware, HumanInTheLoopMiddleware

HITL_TOOLS = ["waive_fee"]
OUTPUT_PREVIEW_CHARS = 300


def tool_error_handler(exc: Exception, request: Any) -> str:
    raise NotImplementedError("M4: tool_error_handler")


def make_tool_error_middleware() -> AgentMiddleware:
    raise NotImplementedError("M4: make_tool_error_middleware")


class LoopGuardMiddleware(AgentMiddleware):
    def __init__(self, max_repeats: int = 2) -> None:
        raise NotImplementedError("M4: LoopGuardMiddleware")

    def count_repeats(self, messages: list[Any], name: str, args: dict[str, Any]) -> int:
        raise NotImplementedError("M4: LoopGuardMiddleware.count_repeats")

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        raise NotImplementedError("M4: LoopGuardMiddleware.wrap_tool_call")


class JsonlTraceMiddleware(AgentMiddleware):
    def __init__(self, log_path: Path | str, agent_name: str) -> None:
        raise NotImplementedError("M4: JsonlTraceMiddleware")

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        raise NotImplementedError("M4: JsonlTraceMiddleware.wrap_tool_call")


def read_trace(log_path: Path | str) -> list[dict[str, Any]]:
    raise NotImplementedError("M4: read_trace")


def make_hitl_middleware() -> HumanInTheLoopMiddleware:
    raise NotImplementedError("M3: make_hitl_middleware")


def default_middleware(
    agent_name: str,
    *,
    log_path: Path | str | None = None,
    model_call_limit: int = 8,
    max_repeats: int = 2,
) -> list[AgentMiddleware]:
    raise NotImplementedError("M4: default_middleware")
