"""진입점: build_agent factory와 CLI (명세서 5.6절). TODO(M3: get_interrupts, M4: 나머지)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .agents import build_catalog_agent, build_circulation_agent, build_rules_agent, build_supervisor
from .rag import build_retrievers
from .store import LibraryStore, load_store

MODEL_NAME = "gpt-6-luna"
ROLES = ("supervisor", "catalog", "rules", "circulation")

Decider = Callable[[dict[str, Any]], dict[str, Any]]


def default_model() -> BaseChatModel:
    """init_chat_model(MODEL_NAME, model_provider="openai"). temperature를 넘기지 않는다."""
    # import와 모델 생성은 호출 시점에만 한다 (import 시점에 모델을 만들지 않는다).
    from langchain.chat_models import init_chat_model

    # gpt-6-luna는 reasoning model이므로 temperature를 넘기지 않는다.
    return init_chat_model(MODEL_NAME, model_provider="openai")


def build_agent(
    model: BaseChatModel | None = None,
    *,
    models: dict[str, BaseChatModel] | None = None,
    store: LibraryStore | None = None,
    retrievers: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
    log_path: Path | str | None = None,
):
    """supervisor와 subagent 3개를 조립한다. role별 모델: models[role] → model → default_model()."""
    models = models or {}
    unknown = set(models) - set(ROLES)
    if unknown:
        raise ValueError(f"알 수 없는 role입니다: {sorted(unknown)} (허용: {list(ROLES)})")

    def pick(role: str) -> BaseChatModel:
        if role in models:
            return models[role]
        if model is not None:
            return model
        return default_model()  # 모든 role이 지정되면 호출되지 않는다

    store = store if store is not None else load_store()
    retrievers = retrievers if retrievers is not None else build_retrievers()

    # subagent에는 checkpointer를 주지 않는다. 그래야 HITL interrupt가 supervisor까지 올라온다.
    subagents = {
        "catalog": build_catalog_agent(pick("catalog"), store, log_path=log_path),
        "rules": build_rules_agent(pick("rules"), retrievers, log_path=log_path),
        "circulation": build_circulation_agent(pick("circulation"), store, log_path=log_path),
    }
    return build_supervisor(
        pick("supervisor"),
        subagents,
        log_path=log_path,
        checkpointer=checkpointer if checkpointer is not None else InMemorySaver(),
    )


def get_interrupts(result: Any) -> list[Any]:
    return result.get("__interrupt__", [])


def answer_text(result: Any) -> str:
    return str(result["messages"][-1].text)


def run_turn(agent: Any, question: str, *, thread_id: str | None = None, decide: Decider | None = None,
             max_resumes: int = 3) -> dict[str, Any]:
    """질문 한 번을 처리한다. interrupt가 나면 decide로 결정을 받아 같은 thread_id로 최대 max_resumes번 resume한다."""
    config = {"configurable": {"thread_id": thread_id or uuid.uuid4().hex}}
    result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config)
    for _ in range(max_resumes):
        interrupts = get_interrupts(result)
        if not interrupts:
            break
        per_interrupt = []
        for intr in interrupts:
            decisions = [
                decide(req) if decide is not None else {"type": "reject", "message": "승인 절차 없이 자동 거절되었습니다."}
                for req in intr.value["action_requests"]
            ]
            per_interrupt.append((intr, {"decisions": decisions}))
        if len(per_interrupt) == 1:
            resume: Any = per_interrupt[0][1]
        else:  # interrupt가 여러 개면 id별로 resume 값을 매핑한다
            resume = {intr.id: value for intr, value in per_interrupt}
        result = agent.invoke(Command(resume=resume), config)
    return result


def _ask_terminal(req: dict[str, Any]) -> dict[str, Any]:
    """터미널에서 사서가 approve/edit/reject를 고른다."""
    print(f"\n[승인 요청] {req['name']} {json.dumps(req['args'], ensure_ascii=False)}")
    if req.get("description"):
        print(req["description"])
    try:
        choice = input("결정 (approve/edit/reject) [reject]: ").strip().lower() or "reject"
        if choice in ("approve", "a"):
            return {"type": "approve"}
        if choice in ("edit", "e"):
            raw = input("수정할 인자(JSON): ").strip()
            return {"type": "edit", "edited_action": {"name": req["name"], "args": json.loads(raw)}}
        reason = input("거절 사유: ").strip()
        return {"type": "reject", "message": reason or "사서가 거절했습니다."}
    except (EOFError, ValueError):
        return {"type": "reject", "message": "입력이 없어 거절되었습니다."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="library_agent.app", description="책숲 AI 사서")
    parser.add_argument("-q", "--question", help="한 번만 묻고 답을 출력한 뒤 종료한다")
    parser.add_argument("--thread", default="cli", help="대화 thread_id (기본 cli)")
    parser.add_argument("--log", default="runs/trace.jsonl", help="trace 파일 경로")
    args = parser.parse_args(argv)

    Path(args.log).parent.mkdir(parents=True, exist_ok=True)
    agent = build_agent(log_path=args.log)

    if args.question:
        result = run_turn(agent, args.question, thread_id=args.thread, decide=_ask_terminal)
        print(answer_text(result))
        return 0

    print("책숲 AI 사서입니다. 종료하려면 빈 줄이나 quit을 입력하세요.")
    while True:
        try:
            question = input("\n질문> ").strip()
        except EOFError:
            break
        if not question or question.lower() in ("quit", "exit"):
            break
        result = run_turn(agent, question, thread_id=args.thread, decide=_ask_terminal)
        print(answer_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
