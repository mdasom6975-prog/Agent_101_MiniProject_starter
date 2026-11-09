"""Harness middleware (명세서 5.5절). TODO(M3: HITL, M4: 나머지)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolErrorMiddleware,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphBubbleUp

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
        super().__init__()
        self.log_path = Path(log_path)
        self.agent_name = agent_name

    @property
    def name(self) -> str:
        # 같은 이름의 middleware가 중복되면 create_agent가 오류를 내므로 agent별로 다르게 한다.
        return f"JsonlTraceMiddleware[{self.agent_name}]"

    def _append(self, request: Any, status: str, output: Any, started: float) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_name,
            "tool": request.tool_call["name"],
            "args": request.tool_call["args"],
            "tool_call_id": request.tool_call["id"],
            "status": status,
            "output": str(output)[:OUTPUT_PREVIEW_CHARS],
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        started = time.perf_counter()
        try:
            result = handler(request)
        except GraphBubbleUp:
            raise  # interrupt는 기록하지 않고 그대로 위로 올린다
        except Exception as exc:
            self._append(request, "exception", f"{type(exc).__name__}: {exc}", started)
            raise
        if isinstance(result, ToolMessage):
            self._append(request, result.status or "success", result.content, started)
        else:  # Command 등
            self._append(request, "command", result, started)
        return result


def read_trace(log_path: Path | str) -> list[dict[str, Any]]:
    path = Path(log_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
