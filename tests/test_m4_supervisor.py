"""M4: supervisor multi-agent 라우팅과 build_agent factory."""

import pytest

from fakes import call, say, scripted
from helpers import tool_messages, user
from library_agent.app import build_agent, get_interrupts, main, run_turn
from library_agent.middleware import read_trace

pytestmark = pytest.mark.m4


def _models(supervisor=(), catalog=(), rules=(), circulation=()):
    return {
        "supervisor": scripted(*supervisor),
        "catalog": scripted(*catalog),
        "rules": scripted(*rules),
        "circulation": scripted(*circulation),
    }


def _route(log_path):
    return [(r["agent"], r["tool"]) for r in read_trace(log_path)]


def test_T411_supervisor_tools_and_factory_contract(store, log_path):
    agent = build_agent(models=_models(), store=store, log_path=log_path)
    assert agent.checkpointer is not None
    tool_node = agent.nodes["tools"].bound
    assert sorted(tool_node.tools_by_name) == ["ask_catalog_agent", "ask_circulation_agent", "ask_rules_agent"]
    with pytest.raises(ValueError):
        build_agent(models={**_models(), "billing": scripted()}, store=store)


def test_T412_routes_rules_question(store, log_path, thread):
    m = _models(
        supervisor=[call("ask_rules_agent", {"request": "신규 회원 대출 권수"}), say("신규 회원은 3권까지입니다(제2조).")],
        rules=[call("search_loan_rules", {"query": "신규 회원 대출 권수"}), say("3권까지(제2조)")],
    )
    agent = build_agent(models=m, store=store, log_path=log_path)
    result = agent.invoke(user("신규 회원은 몇 권까지 빌려요?"), thread)
    assert _route(log_path) == [("rules_agent", "search_loan_rules"), ("supervisor", "ask_rules_agent")]
    [tm] = tool_messages(result, "ask_rules_agent")
    assert tm.content == "3권까지(제2조)"  # subagent의 마지막 답이 그대로 supervisor에 전달
    assert "제2조" in result["messages"][-1].content


def test_T413_routes_catalog_then_rules(store, log_path, thread):
    m = _models(
        supervisor=[
            call("ask_catalog_agent", {"request": "기후의 시간 대출 가능?"}),
            call("ask_rules_agent", {"request": "예약 규정"}),
            say("B008은 대출 중이며 예약 가능합니다(제5조)."),
        ],
        catalog=[call("search_books", {"query": "기후의 시간"}), say("B008 available 0")],
        rules=[call("search_loan_rules", {"query": "예약"}), say("제5조")],
    )
    agent = build_agent(models=m, store=store, log_path=log_path)
    agent.invoke(user("기후의 시간 빌릴 수 있나요? 안 되면 예약 규정도"), thread)
    sup = [t for a, t in _route(log_path) if a == "supervisor"]
    assert sup == ["ask_catalog_agent", "ask_rules_agent"]
    assert ("catalog_agent", "search_books") in _route(log_path)
    assert ("rules_agent", "search_loan_rules") in _route(log_path)


def test_T414_out_of_scope_calls_no_agent(store, log_path, thread):
    agent = build_agent(models=_models(supervisor=[say("도서관 업무만 도와드릴 수 있어요.")]), store=store, log_path=log_path)
    result = agent.invoke(user("오늘 날씨 어때?"), thread)
    assert read_trace(log_path) == []
    assert result["messages"][-1].content == "도서관 업무만 도와드릴 수 있어요."


def _waive_models():
    return _models(
        supervisor=[call("ask_circulation_agent", {"request": "M-0003 연체료 면제, 입원 증빙"}), say("처리 결과를 안내드립니다.")],
        circulation=[call("waive_fee", {"member_id": "M-0003", "reason": "입원 증빙 제출"}), say("처리했습니다.")],
    )


def test_T415_hitl_bubbles_to_supervisor_and_approve(store, log_path, thread):
    from langgraph.types import Command

    agent = build_agent(models=_waive_models(), store=store, log_path=log_path)
    result = agent.invoke(user("M-0003 연체료 면제해 주세요"), thread)
    [intr] = get_interrupts(result)
    assert intr.value["action_requests"][0]["name"] == "waive_fee"
    assert store.members["M-0003"].fee == 1500
    result = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread)
    assert get_interrupts(result) == []
    assert store.members["M-0003"].fee == 0
    assert _route(log_path) == [("circulation_agent", "waive_fee"), ("supervisor", "ask_circulation_agent")]


def test_T416_hitl_reject_via_run_turn(store, log_path):
    agent = build_agent(models=_waive_models(), store=store, log_path=log_path)
    seen = []

    def decide(req):
        seen.append(req["name"])
        return {"type": "reject", "message": "증빙 미확인"}

    result = run_turn(agent, "M-0003 연체료 면제해 주세요", thread_id="t-reject", decide=decide)
    assert seen == ["waive_fee"]
    assert store.members["M-0003"].fee == 1500
    assert "waive_fee" not in [r["tool"] for r in read_trace(log_path)]  # 거절된 호출은 실행·기록되지 않는다
    assert get_interrupts(result) == []


def test_T417_cli_one_shot(monkeypatch, capsys, store, tmp_path):
    import library_agent.app as app

    m = _models(supervisor=[say("안녕하세요, 책숲 AI 사서입니다.")])
    monkeypatch.setattr(app, "build_agent", lambda **kw: build_agent(models=m, store=store, log_path=kw.get("log_path")))
    assert main(["-q", "안녕", "--log", str(tmp_path / "t.jsonl")]) == 0
    assert "책숲 AI 사서" in capsys.readouterr().out
