"""테스트 공통 helper."""

from __future__ import annotations

from langchain_core.messages import ToolMessage


def user(text: str) -> dict:
    return {"messages": [{"role": "user", "content": text}]}


def tool_messages(result: dict, name: str | None = None) -> list[ToolMessage]:
    return [m for m in result["messages"] if isinstance(m, ToolMessage) and (name is None or m.name == name)]
