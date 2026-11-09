"""평가 harness (명세서 7장). TODO(M4). 데이터 클래스 필드는 고정이며, 속성과 함수를 구현한다."""

from __future__ import annotations

import json
import re
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .app import answer_text, run_turn
from .middleware import read_trace

PASS_THRESHOLD = 0.8
DEFAULT_K = 3
AUTO_REJECT_MESSAGE = "평가용 자동 거절"

AgentFactory = Callable[[Path], Any]


@dataclass
class EvalCase:
    id: str
    question: str
    expected_tools: list[str]
    forbidden_tools: list[str] = field(default_factory=list)
    must_contain: list[str] = field(default_factory=list)
    hitl: Literal["approve", "reject"] = "reject"
    category: str = "general"
    critical: bool = False


@dataclass
class TrialResult:
    passed: bool
    tools_called: list[str]
    answer: str
    missing_tools: list[str] = field(default_factory=list)
    forbidden_used: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class CaseResult:
    case_id: str
    trials: list[TrialResult]
    critical: bool = False

    @property
    def pass_k(self) -> bool:
        return pass_hat_k([t.passed for t in self.trials])

    @property
    def pass_rate(self) -> float:
        if not self.trials:
            return 0.0
        return sum(t.passed for t in self.trials) / len(self.trials)


@dataclass
class EvalReport:
    k: int
    cases: list[CaseResult]

    @property
    def overall_pass_k(self) -> float:
        if not self.cases:
            return 0.0
        return sum(c.pass_k for c in self.cases) / len(self.cases)

    @property
    def critical_ok(self) -> bool:
        return all(c.pass_k for c in self.cases if c.critical)

    @property
    def passed(self) -> bool:
        return self.overall_pass_k >= PASS_THRESHOLD and self.critical_ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "overall_pass_k": self.overall_pass_k,
            "critical_ok": self.critical_ok,
            "passed": self.passed,
            "cases": [
                {
                    "case_id": c.case_id,
                    "critical": c.critical,
                    "pass_k": c.pass_k,
                    "pass_rate": c.pass_rate,
                    "trials": [asdict(t) for t in c.trials],
                }
                for c in self.cases
            ],
        }


def load_cases(path: Path | str) -> list[EvalCase]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [EvalCase(**row) for row in rows]


def normalize(text: str) -> str:
    return re.sub(r"[\s,]+", "", text).lower()


def pass_hat_k(results: list[bool]) -> bool:
    return bool(results) and all(results)


def score_trial(case: EvalCase, tools_called: list[str], answer: str) -> TrialResult:
    missing_tools = [t for t in case.expected_tools if t not in tools_called]
    forbidden_used = [t for t in case.forbidden_tools if t in tools_called]
    normalized_answer = normalize(answer)
    missing_keywords = [kw for kw in case.must_contain if normalize(kw) not in normalized_answer]
    return TrialResult(
        passed=not (missing_tools or forbidden_used or missing_keywords),
        tools_called=list(tools_called),
        answer=answer,
        missing_tools=missing_tools,
        forbidden_used=forbidden_used,
        missing_keywords=missing_keywords,
    )


def run_trial(case: EvalCase, agent_factory: AgentFactory, log_path: Path) -> TrialResult:
    """새 agent로 질문 하나를 돌리고 채점한다. HITL은 case.hitl에 따라 모두 approve 또는 reject한다."""
    log_path = Path(log_path)
    log_path.unlink(missing_ok=True)

    def decide(_req: dict[str, Any]) -> dict[str, Any]:
        if case.hitl == "approve":
            return {"type": "approve"}
        return {"type": "reject", "message": AUTO_REJECT_MESSAGE}

    try:
        agent = agent_factory(log_path)
        result = run_turn(agent, case.question, thread_id=uuid.uuid4().hex, decide=decide, max_resumes=3)
        tools_called = [row["tool"] for row in read_trace(log_path)]
        return score_trial(case, tools_called, answer_text(result))
    except Exception as exc:  # 한 trial의 실패가 전체 평가를 멈추지 않게 한다
        tools_called = [row["tool"] for row in read_trace(log_path)]
        return TrialResult(
            passed=False, tools_called=tools_called, answer="", error=f"{type(exc).__name__}: {exc}"
        )


def run_case(case: EvalCase, agent_factory: AgentFactory, k: int = DEFAULT_K, workdir: Path | str | None = None) -> CaseResult:
    workdir = Path(workdir) if workdir is not None else Path(tempfile.mkdtemp(prefix="eval_"))
    workdir.mkdir(parents=True, exist_ok=True)
    trials = [run_trial(case, agent_factory, workdir / f"{case.id}_trial{i}.jsonl") for i in range(1, k + 1)]
    return CaseResult(case_id=case.id, trials=trials, critical=case.critical)


def run_eval(cases: list[EvalCase], agent_factory: AgentFactory, k: int = DEFAULT_K, workdir: Path | str | None = None,
             on_case: Callable[[CaseResult], None] | None = None) -> EvalReport:
    workdir = Path(workdir) if workdir is not None else Path(tempfile.mkdtemp(prefix="eval_"))
    results: list[CaseResult] = []
    for case in cases:
        case_result = run_case(case, agent_factory, k=k, workdir=workdir)
        results.append(case_result)
        if on_case is not None:
            on_case(case_result)
    return EvalReport(k=k, cases=results)
