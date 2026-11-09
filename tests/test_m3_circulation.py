"""M3: 대출·예약·연체료 면제 store 로직과 대출 처리 도구."""

import json
from datetime import date

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from fakes import call, say, scripted
from helpers import tool_messages, user
from library_agent.agents import build_circulation_agent
from library_agent.errors import (
    BookNotFoundError,
    HoldDuplicateError,
    HoldLimitError,
    HoldNotAllowedError,
    LoanLimitError,
    MemberNotFoundError,
    MemberSuspendedError,
    NoFeeError,
    NotAvailableError,
    UnpaidFeeError,
)
from library_agent.schemas import CheckoutRequest, CheckoutResult, FeeWaiverRequest, HoldRequest
from library_agent.tools import make_circulation_tools

pytestmark = pytest.mark.m3


def co(member, books, days=14):
    return CheckoutRequest(member_id=member, book_ids=books, loan_days=days)


def test_T301_checkout_success_mutates_store(store):
    res = store.checkout(co("M-0001", ["B004", "B012"], 7))
    assert isinstance(res, CheckoutResult)
    assert [(i.book_id, i.due_date) for i in res.loans] == [("B004", date(2026, 11, 10)), ("B012", date(2026, 11, 10))]
    assert res.remaining_quota == 3
    assert store.books["B004"].available == 1 and store.books["B012"].available == 2
    assert store.members["M-0001"].loans == ["B004", "B012"]


def test_T302_suspended_member(store):
    with pytest.raises(MemberSuspendedError) as e:
        store.checkout(co("M-0004", ["B001"]))
    assert str(e.value) == "이용이 정지된 회원입니다: M-0004"


def test_T303_unpaid_fee(store):
    with pytest.raises(UnpaidFeeError) as e:
        store.checkout(co("M-0003", ["B001"]))
    assert str(e.value) == "미납 연체료가 있어 대출할 수 없습니다: 1500원"


def test_T304_loan_limits(store):
    with pytest.raises(LoanLimitError) as e:
        store.checkout(co("M-0005", ["B001", "B004"]))
    assert str(e.value) == "대출 한도를 초과합니다: 현재 4권 + 요청 2권 > 한도 5권"
    with pytest.raises(LoanLimitError) as e2:
        store.checkout(co("M-0002", ["B001", "B004", "B009", "B012"]))
    assert str(e2.value) == "대출 한도를 초과합니다: 현재 0권 + 요청 4권 > 한도 3권"
    assert store.checkout(co("M-0005", ["B001"])).remaining_quota == 0


def test_T305_not_available_is_atomic(store):
    with pytest.raises(NotAvailableError) as e:
        store.checkout(co("M-0001", ["B001", "B002"]))
    assert str(e.value) == "대출 가능한 재고가 없습니다: B002"
    assert store.books["B001"].available == 2  # 부분 대출 금지
    assert store.members["M-0001"].loans == []


def test_T306_unknown_ids(store):
    with pytest.raises(BookNotFoundError):
        store.checkout(co("M-0001", ["B999"]))
    with pytest.raises(MemberNotFoundError):
        store.checkout(co("M-0999", ["B001"]))


def test_T307_place_hold_queue_and_duplicate(store):
    r = store.place_hold(HoldRequest(member_id="M-0001", book_id="B002"))
    assert (r.book_id, r.title, r.queue_position) == ("B002", "달빛 정원의 고양이", 2)
    assert store.holds["B002"] == ["M-0006", "M-0001"]
    with pytest.raises(HoldDuplicateError) as e:
        store.place_hold(HoldRequest(member_id="M-0001", book_id="B002"))
    assert str(e.value) == "이미 예약한 도서입니다: B002"


def test_T308_hold_on_available_book_not_allowed(store):
    with pytest.raises(HoldNotAllowedError) as e:
        store.place_hold(HoldRequest(member_id="M-0001", book_id="B001"))
    assert str(e.value) == "대출 가능한 도서는 예약할 수 없습니다: B001"


def test_T309_hold_limit(store):
    with pytest.raises(HoldLimitError) as e:
        store.place_hold(HoldRequest(member_id="M-0007", book_id="B010"))
    assert str(e.value) == "예약 한도를 초과합니다: 최대 3권"


def test_T310_waive_fee(store):
    r = store.waive_fee(FeeWaiverRequest(member_id="M-0003", reason="입원 증빙 제출"))
    assert (r.waived_amount, r.remaining_fee) == (1500, 0)
    assert store.members["M-0003"].fee == 0
    with pytest.raises(NoFeeError) as e:
        store.waive_fee(FeeWaiverRequest(member_id="M-0003", reason="입원 증빙 제출"))
    assert str(e.value) == "면제할 연체료가 없습니다: M-0003"


def test_T311_circulation_tools_contract(store):
    tools = {t.name: t for t in make_circulation_tools(store)}
    assert list(tools) == ["get_member_status", "checkout_books", "place_hold", "waive_fee"]
    assert tools["checkout_books"].args_schema is CheckoutRequest
    out = tools["checkout_books"].invoke({"member_id": "M-0001", "book_ids": ["B004"], "loan_days": 3})
    parsed = CheckoutResult.model_validate_json(out)
    assert parsed.loans[0].due_date == date(2026, 11, 6)
    st = json.loads(tools["get_member_status"].invoke({"member_id": "M-0001"}))
    assert st["current_loans"] == 1 and st["loan_limit"] == 5


def test_T312_tool_validation_error_on_direct_invoke(store):
    tools = {t.name: t for t in make_circulation_tools(store)}
    with pytest.raises(ValidationError):
        tools["checkout_books"].invoke({"member_id": "M-0001", "book_ids": ["B004"], "loan_days": 30})
    with pytest.raises(ValidationError):
        tools["waive_fee"].invoke({"member_id": "M-0003", "reason": "x"})


def test_T313_agent_turns_validation_error_into_tool_message(store, thread):
    model = scripted(
        call("checkout_books", {"member_id": "M-0001", "book_ids": ["B004"], "loan_days": 30}),
        say("대출 기간은 최대 14일입니다."),
    )
    agent = build_circulation_agent(model, store, checkpointer=InMemorySaver())
    result = agent.invoke(user("M-0001, B004 30일 대출"), thread)
    [tm] = tool_messages(result, "checkout_books")
    assert tm.status == "error"
    assert store.books["B004"].available == 2  # 실행되지 않음
