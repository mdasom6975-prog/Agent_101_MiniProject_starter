"""M3: waive_fee에 대한 HumanInTheLoopMiddleware 승인/수정/거절."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from fakes import call, say, scripted
from helpers import tool_messages, user
from library_agent.agents import build_circulation_agent
from library_agent.app import get_interrupts

pytestmark = pytest.mark.m3

WAIVE = {"member_id": "M-0003", "reason": "입원 증빙 제출"}


def _agent(store, *msgs):
    return build_circulation_agent(scripted(*msgs), store, checkpointer=InMemorySaver())


def test_T321_waive_fee_interrupts_before_execution(store, thread):
    agent = _agent(store, call("waive_fee", WAIVE), say("면제 완료"))
    result = agent.invoke(user("M-0003 연체료 면제"), thread)
    [intr] = get_interrupts(result)
    req = intr.value["action_requests"][0]
    assert req["name"] == "waive_fee" and req["args"] == WAIVE
    assert intr.value["review_configs"][0]["allowed_decisions"] == ["approve", "edit", "reject"]
    assert store.members["M-0003"].fee == 1500  # 아직 실행 전


def test_T322_approve_executes(store, thread):
    agent = _agent(store, call("waive_fee", WAIVE), say("1500원 면제 완료"))
    agent.invoke(user("M-0003 연체료 면제"), thread)
    result = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), thread)
    assert get_interrupts(result) == []
    [tm] = tool_messages(result, "waive_fee")
    assert tm.status == "success" and '"waived_amount":1500' in tm.content
    assert store.members["M-0003"].fee == 0


def test_T323_reject_does_not_execute(store, thread):
    agent = _agent(store, call("waive_fee", WAIVE), say("면제가 거절되었습니다."))
    agent.invoke(user("M-0003 연체료 면제"), thread)
    result = agent.invoke(Command(resume={"decisions": [{"type": "reject", "message": "증빙 미확인"}]}), thread)
    [tm] = tool_messages(result, "waive_fee")
    assert tm.status == "error" and "증빙 미확인" in tm.content
    assert store.members["M-0003"].fee == 1500
    assert result["messages"][-1].content == "면제가 거절되었습니다."


def test_T324_edit_executes_edited_args(store, thread):
    agent = _agent(store, call("waive_fee", WAIVE), say("수정된 회원으로 처리"))
    agent.invoke(user("M-0003 연체료 면제"), thread)
    edited = {"type": "edit", "edited_action": {"name": "waive_fee", "args": {"member_id": "M-0008", "reason": "시스템 오류 확인"}}}
    agent.invoke(Command(resume={"decisions": [edited]}), thread)
    assert store.members["M-0008"].fee == 0
    assert store.members["M-0003"].fee == 1500


def test_T325_other_tools_do_not_interrupt(store, thread):
    agent = _agent(
        store,
        call("get_member_status", {"member_id": "M-0001"}),
        call("checkout_books", {"member_id": "M-0001", "book_ids": ["B004"]}),
        say("대출 완료"),
    )
    result = agent.invoke(user("M-0001 B004 대출"), thread)
    assert get_interrupts(result) == []
    assert store.books["B004"].available == 1
