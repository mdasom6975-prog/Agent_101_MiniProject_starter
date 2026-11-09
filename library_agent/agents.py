"""Subagent와 Supervisor 조립 (명세서 5.4절). TODO(M2: rules, M3: circulation, M4: catalog·supervisor)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool

from .store import LibraryStore

SUPERVISOR_MODEL_CALL_LIMIT = 8
SUBAGENT_MODEL_CALL_LIMIT = 6

# TODO: 각 agent의 system prompt를 직접 설계한다 (명세서 5.4절 요구사항 참고).
CATALOG_PROMPT = "TODO"
RULES_PROMPT = "TODO"
CIRCULATION_PROMPT = "TODO"
SUPERVISOR_PROMPT = "TODO"

SUBAGENT_TOOL_SPECS: dict[str, tuple[str, str]] = {
    "catalog": ("ask_catalog_agent", "TODO: 도구 description"),
    "rules": ("ask_rules_agent", "TODO: 도구 description"),
    "circulation": ("ask_circulation_agent", "TODO: 도구 description"),
}


def build_catalog_agent(model: BaseChatModel, store: LibraryStore, *, log_path: Path | str | None = None,
                        model_call_limit: int = SUBAGENT_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    raise NotImplementedError("M4: build_catalog_agent")


def build_rules_agent(model: BaseChatModel, retrievers: dict[str, BaseRetriever], *, log_path: Path | str | None = None,
                      model_call_limit: int = SUBAGENT_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    raise NotImplementedError("M2: build_rules_agent")


def build_circulation_agent(model: BaseChatModel, store: LibraryStore, *, log_path: Path | str | None = None,
                            model_call_limit: int = SUBAGENT_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    raise NotImplementedError("M3: build_circulation_agent")


def make_subagent_tool(agent: Any, name: str, description: str) -> BaseTool:
    raise NotImplementedError("M4: make_subagent_tool")


def build_supervisor(model: BaseChatModel, subagents: dict[str, Any], *, log_path: Path | str | None = None,
                     model_call_limit: int = SUPERVISOR_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    raise NotImplementedError("M4: build_supervisor")
