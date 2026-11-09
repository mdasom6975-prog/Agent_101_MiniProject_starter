"""M5: 실제 LLM(gpt-6-luna) 연동과 프로젝트 문서. live 테스트는 OPENAI_API_KEY가 없으면 skip된다."""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.m5
ROOT = Path(__file__).resolve().parents[1]
needs_key = pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY 없음")


def test_T501_agents_md_is_filled():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "TODO" not in text, "AGENTS.md의 TODO를 모두 채우세요"
    for section in ["## 프로젝트 개요", "## 명령어", "## 코드 규칙", "## 금지 사항", "## 완료 조건"]:
        assert section in text
    assert "pytest" in text


@pytest.mark.live
@needs_key
def test_T502_live_smoke_rules_question(tmp_path):
    from library_agent.app import answer_text, build_agent, run_turn
    from library_agent.middleware import read_trace

    log = tmp_path / "live.jsonl"
    agent = build_agent(log_path=log)
    result = run_turn(agent, "신규 회원은 몇 권까지 빌릴 수 있나요?")
    tools = [r["tool"] for r in read_trace(log)]
    assert "ask_rules_agent" in tools and "search_loan_rules" in tools
    assert "3권" in answer_text(result).replace(" ", "")


@pytest.mark.live
@needs_key
@pytest.mark.skipif(not os.getenv("RUN_FULL_EVAL"), reason="전체 eval은 RUN_FULL_EVAL=1일 때만 (API 비용)")
def test_T503_live_full_eval_pass3(tmp_path):
    from library_agent.app import build_agent
    from library_agent.evaluation import load_cases, run_eval

    report = run_eval(load_cases(ROOT / "eval" / "eval_cases.json"), lambda p: build_agent(log_path=p), k=3, workdir=tmp_path)
    assert report.critical_ok, [c.case_id for c in report.cases if c.critical and not c.pass_k]
    assert report.overall_pass_k >= 0.8
