"""테스트용 scripted fake chat model. API key 없이 agent를 결정적으로 돌린다. (starter kit에 그대로 제공)"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage

_ids = itertools.count(1)


class ScriptedChatModel(GenericFakeChatModel):
    """미리 정한 AIMessage를 순서대로 돌려준다. bind_tools는 자기 자신을 돌려준다.

    received: 매 호출마다 모델이 받은 메시지 목록(검증용).
    """

    received: list[list[BaseMessage]] = []

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[override]
        self.received.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def scripted(*messages: AIMessage | str) -> ScriptedChatModel:
    return ScriptedChatModel(messages=iter(messages), received=[])


def scripted_stream(messages: Iterable[AIMessage]) -> ScriptedChatModel:
    """무한 generator 등 임의의 iterable을 받는다(ModelCallLimit 테스트용)."""
    return ScriptedChatModel(messages=iter(messages), received=[])


def call(name: str, args: dict[str, Any] | None = None, *more: tuple[str, dict[str, Any]]) -> AIMessage:
    """도구 호출 AIMessage. 여러 도구를 한 번에 부르려면 call("a", {...}, ("b", {...}))."""
    calls = [(name, args or {}), *more]
    return AIMessage(
        content="",
        tool_calls=[{"name": n, "args": a, "id": f"call_{next(_ids)}", "type": "tool_call"} for n, a in calls],
    )


def say(text: str) -> AIMessage:
    return AIMessage(content=text)
