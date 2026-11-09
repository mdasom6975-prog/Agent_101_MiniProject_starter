"""진입점: build_agent factory와 CLI (명세서 5.6절). TODO(M3: get_interrupts, M4: 나머지)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel

from .store import LibraryStore

MODEL_NAME = "gpt-6-luna"
ROLES = ("supervisor", "catalog", "rules", "circulation")

Decider = Callable[[dict[str, Any]], dict[str, Any]]


def default_model() -> BaseChatModel:
    """init_chat_model(MODEL_NAME, model_provider="openai"). temperature를 넘기지 않는다."""
    raise NotImplementedError("M5: default_model")


def build_agent(
    model: BaseChatModel | None = None,
    *,
    models: dict[str, BaseChatModel] | None = None,
    store: LibraryStore | None = None,
    retrievers: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
    log_path: Path | str | None = None,
):
    raise NotImplementedError("M4: build_agent")


def get_interrupts(result: Any) -> list[Any]:
    raise NotImplementedError("M3: get_interrupts")


def answer_text(result: Any) -> str:
    raise NotImplementedError("M4: answer_text")


def run_turn(agent: Any, question: str, *, thread_id: str | None = None, decide: Decider | None = None,
             max_resumes: int = 3) -> dict[str, Any]:
    raise NotImplementedError("M4: run_turn")


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError("M4: main (CLI)")


if __name__ == "__main__":
    sys.exit(main())
