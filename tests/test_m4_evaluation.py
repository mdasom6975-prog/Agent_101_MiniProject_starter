"""M4: 평가기(evaluation.py) 로직. scripted fake로 결정적으로 검증한다."""

from pathlib import Path

import pytest

from fakes import call, say, scripted
from library_agent.app import build_agent
from library_agent.evaluation import (
    PASS_THRESHOLD,
    CaseResult,
    EvalCase,
    EvalReport,
    TrialResult,
    load_cases,
    normalize,
    pass_hat_k,
    run_case,
    run_eval,
    score_trial,
)
from library_agent.store import load_store
from library_agent.tools import CATALOG_TOOL_NAMES, CIRCULATION_TOOL_NAMES, RULE_TOOL_NAMES

pytestmark = pytest.mark.m4

CASES_PATH = Path(__file__).resolve().parents[1] / "eval" / "eval_cases.json"
KNOWN_TOOLS = set(CATALOG_TOOL_NAMES + RULE_TOOL_NAMES + CIRCULATION_TOOL_NAMES) | {
    "ask_catalog_agent",
    "ask_rules_agent",
    "ask_circulation_agent",
}


def test_T421_eval_cases_file_is_well_formed():
    cases = load_cases(CASES_PATH)
    assert len(cases) == 20
    assert len({c.id for c in cases}) == 20
    for c in cases:
        assert set(c.expected_tools) <= KNOWN_TOOLS and set(c.forbidden_tools) <= KNOWN_TOOLS
        assert not set(c.expected_tools) & set(c.forbidden_tools)
        assert c.hitl in {"approve", "reject"}
    assert any({"search_loan_rules", "search_facility_rules"} <= set(c.expected_tools) for c in cases)
    assert sum(c.critical for c in cases) >= 4
    assert any(c.hitl == "approve" and "waive_fee" in c.expected_tools for c in cases)


CASE = EvalCase(
    id="X1",
    question="신규 회원 권수?",
    expected_tools=["ask_rules_agent", "search_loan_rules"],
    forbidden_tools=["checkout_books"],
    must_contain=["3권", "제2조", "3,000원"],
)


def test_T422_score_trial():
    ok = score_trial(CASE, ["search_loan_rules", "ask_rules_agent"], "신규는 3 권 (제2조), 상한 3000 원")
    assert ok.passed and ok.missing_tools == [] and ok.missing_keywords == []
    miss = score_trial(CASE, ["ask_rules_agent"], "3권 제2조 3000원")
    assert not miss.passed and miss.missing_tools == ["search_loan_rules"]
    forb = score_trial(CASE, ["ask_rules_agent", "search_loan_rules", "checkout_books"], "3권 제2조 3000원")
    assert not forb.passed and forb.forbidden_used == ["checkout_books"]
    kw = score_trial(CASE, ["ask_rules_agent", "search_loan_rules"], "3권입니다")
    assert not kw.passed and kw.missing_keywords == ["제2조", "3,000원"]
    assert normalize("3,000 원") == normalize("3000원") == "3000원"


def test_T423_pass_hat_k():
    assert pass_hat_k([True, True, True])
    assert not pass_hat_k([True, False, True])
    assert not pass_hat_k([])


def _rules_factory(answers):
    """trial마다 새 agent(새 store, 새 scripted model)를 만든다. answers[i]가 i번째 trial의 최종 답."""
    it = iter(answers)

    def factory(log_path):
        ans = next(it)
        return build_agent(
            models={
                "supervisor": scripted(call("ask_rules_agent", {"request": "신규 회원 권수"}), say(ans)),
                "rules": scripted(call("search_loan_rules", {"query": "신규 회원 권수"}), say(ans)),
                "catalog": scripted(),
                "circulation": scripted(),
            },
            store=load_store(),
            log_path=log_path,
        )

    return factory


def test_T424_run_case_pass3(tmp_path):
    good = "신규 회원은 3권(제2조), 상한 3,000원"
    cr = run_case(CASE, _rules_factory([good] * 3), k=3, workdir=tmp_path)
    assert isinstance(cr, CaseResult) and len(cr.trials) == 3
    assert cr.pass_k and cr.pass_rate == 1.0
    assert sorted(p.name for p in tmp_path.glob("*.jsonl")) == ["X1_trial1.jsonl", "X1_trial2.jsonl", "X1_trial3.jsonl"]
    assert cr.trials[0].tools_called == ["search_loan_rules", "ask_rules_agent"]


def test_T425_one_flaky_trial_fails_pass3(tmp_path):
    good = "신규 회원은 3권(제2조), 상한 3,000원"
    cr = run_case(CASE, _rules_factory([good, "잘 모르겠어요", good]), k=3, workdir=tmp_path)
    assert not cr.pass_k
    assert cr.pass_rate == pytest.approx(2 / 3)
    assert cr.trials[1].missing_keywords == ["3권", "제2조", "3,000원"]


def test_T426_hitl_policy_in_trial(tmp_path):
    case = EvalCase(
        id="H1", question="M-0003 연체료 면제", expected_tools=["ask_circulation_agent", "waive_fee"],
        must_contain=["면제"], hitl="approve", critical=True,
    )
    stores = []

    def factory(log_path):
        s = load_store()
        stores.append(s)
        return build_agent(
            models={
                "supervisor": scripted(call("ask_circulation_agent", {"request": "M-0003 면제"}), say("면제 완료")),
                "circulation": scripted(call("waive_fee", {"member_id": "M-0003", "reason": "입원 증빙 제출"}), say("면제 완료")),
                "catalog": scripted(),
                "rules": scripted(),
            },
            store=s,
            log_path=log_path,
        )

    cr = run_case(case, factory, k=1, workdir=tmp_path)
    assert cr.pass_k and stores[0].members["M-0003"].fee == 0
    stores.clear()
    rej = EvalCase(**{**case.__dict__, "id": "H2", "hitl": "reject"})
    cr2 = run_case(rej, factory, k=1, workdir=tmp_path)
    assert stores[0].members["M-0003"].fee == 1500
    assert cr2.trials[0].missing_tools == ["waive_fee"]  # 거절된 호출은 실행되지 않으므로 trace에 없다


def test_T427_report_threshold_and_critical(tmp_path):
    def cr(cid, ok, critical=False):
        return CaseResult(case_id=cid, trials=[TrialResult(passed=ok, tools_called=[], answer="")] * 3, critical=critical)

    assert PASS_THRESHOLD == 0.8
    r = EvalReport(k=3, cases=[cr(f"C{i}", i < 8) for i in range(10)])
    assert r.overall_pass_k == 0.8 and r.passed
    r2 = EvalReport(k=3, cases=[cr(f"C{i}", i != 0, critical=(i == 0)) for i in range(10)])
    assert r2.overall_pass_k == 0.9 and not r2.critical_ok and not r2.passed
    d = r.to_dict()
    assert set(d) == {"k", "overall_pass_k", "critical_ok", "passed", "cases"}
    rep = run_eval([CASE], _rules_factory(["3권 제2조 3,000원"] * 2), k=2, workdir=tmp_path)
    assert rep.k == 2 and rep.overall_pass_k == 1.0
