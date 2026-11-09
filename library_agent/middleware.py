"""Harness middleware (명세서 5.5절). TODO(M3: HITL, M4: 나머지)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolErrorMiddleware,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .errors import LibraryError

HITL_TOOLS = ["waive_fee"]
OUTPUT_PREVIEW_CHARS = 300


def tool_error_handler(exc: Exception, request: Any) -> str:
    """도메인 오류는 `[CODE] 메시지`, 그 밖의 예외는 `[INTERNAL] ...`로 바꾼다."""
    if isinstance(exc, LibraryError):
        return f"[{exc.code}] {exc}"
    tool_name = request.tool_call["name"]
    return f"[INTERNAL] {tool_name} 실행 중 예기치 못한 오류가 발생했습니다 ({type(exc).__name__})"


def make_tool_error_middleware() -> AgentMiddleware:
    return ToolErrorMiddleware(on_error=tool_error_handler)


class LoopGuardMiddleware(AgentMiddleware):
    def __init__(self, max_repeats: int = 2) -> None:
        super().__init__()
        if max_repeats < 1:
            raise ValueError("max_repeats는 1 이상이어야 합니다")
        self.max_repeats = max_repeats

    def count_repeats(self, messages: list[Any], name: str, args: dict[str, Any]) -> int:
        """마지막 HumanMessage 이후 AIMessage의 tool_calls 중 (name, args)가 같은 개수 (현재 호출 포함)."""
        start = 0
        for i, m in enumerate(messages):
            if isinstance(m, HumanMessage):
                start = i + 1
        count = 0
        for m in messages[start:]:
            if isinstance(m, AIMessage):
                count += sum(1 for tc in m.tool_calls if tc["name"] == name and tc["args"] == args)
        return count

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        name, args = request.tool_call["name"], request.tool_call["args"]
        n = self.count_repeats(request.state["messages"], name, args)
        if n > self.max_repeats:
            return ToolMessage(
                content=f"[LOOP_GUARD] 같은 인자로 {name}을(를) {n}번째 호출하여 차단했습니다. 이미 받은 결과로 답하세요.",
                tool_call_id=request.tool_call["id"],
                name=name,
                status="error",
            )
        return handler(request)


class JsonlTraceMiddleware(AgentMiddleware):
    def __init__(self, log_path: Path | str, agent_name: str) -> None:
        raise NotImplementedError("M4: JsonlTraceMiddleware")

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        raise NotImplementedError("M4: JsonlTraceMiddleware.wrap_tool_call")


def read_trace(log_path: Path | str) -> list[dict[str, Any]]:
    raise NotImplementedError("M4: read_trace")


def make_hitl_middleware() -> HumanInTheLoopMiddleware:
    """waive_fee 실행 전에 사서의 승인(approve/edit/reject)을 받는다. interrupt mode는 기본값."""
    return HumanInTheLoopMiddleware(
        interrupt_on={
            tool_name: {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "연체료 면제는 사서의 승인이 필요합니다. 승인, 수정, 거절 중 하나를 선택하세요.",
            }
            for tool_name in HITL_TOOLS
        }
    )


def default_middleware(
    agent_name: str,
    *,
    log_path: Path | str | None = None,
    model_call_limit: int = 8,
    max_repeats: int = 2,
) -> list[AgentMiddleware]:
    middleware: list[AgentMiddleware] = []
    if log_path is not None:
        middleware.append(JsonlTraceMiddleware(log_path, agent_name))
    middleware.append(ModelCallLimitMiddleware(run_limit=model_call_limit, exit_behavior="end"))
    middleware.append(LoopGuardMiddleware(max_repeats))
    middleware.append(make_tool_error_middleware())
    return middleware
