"""평가 harness (명세서 7장). TODO(M4). 데이터 클래스 필드는 고정이며, 속성과 함수를 구현한다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

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
        raise NotImplementedError("M4: CaseResult.pass_k")

    @property
    def pass_rate(self) -> float:
        raise NotImplementedError("M4: CaseResult.pass_rate")


@dataclass
class EvalReport:
    k: int
    cases: list[CaseResult]

    @property
    def overall_pass_k(self) -> float:
        raise NotImplementedError("M4: EvalReport.overall_pass_k")

    @property
    def critical_ok(self) -> bool:
        raise NotImplementedError("M4: EvalReport.critical_ok")

    @property
    def passed(self) -> bool:
        raise NotImplementedError("M4: EvalReport.passed")

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError("M4: EvalReport.to_dict")


def load_cases(path: Path | str) -> list[EvalCase]:
    raise NotImplementedError("M4: load_cases")


def normalize(text: str) -> str:
    raise NotImplementedError("M4: normalize")


def pass_hat_k(results: list[bool]) -> bool:
    raise NotImplementedError("M4: pass_hat_k")


def score_trial(case: EvalCase, tools_called: list[str], answer: str) -> TrialResult:
    raise NotImplementedError("M4: score_trial")


def run_trial(case: EvalCase, agent_factory: AgentFactory, log_path: Path) -> TrialResult:
    raise NotImplementedError("M4: run_trial")


def run_case(case: EvalCase, agent_factory: AgentFactory, k: int = DEFAULT_K, workdir: Path | str | None = None) -> CaseResult:
    raise NotImplementedError("M4: run_case")


def run_eval(cases: list[EvalCase], agent_factory: AgentFactory, k: int = DEFAULT_K, workdir: Path | str | None = None,
             on_case: Callable[[CaseResult], None] | None = None) -> EvalReport:
    raise NotImplementedError("M4: run_eval")
