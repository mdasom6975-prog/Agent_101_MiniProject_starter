"""M1: Pydantic 스키마 검증."""

import pytest
from pydantic import ValidationError

from library_agent.schemas import Book, CheckoutRequest, FeeWaiverRequest, HoldRequest

pytestmark = pytest.mark.m1


def test_T111_checkout_request_defaults():
    r = CheckoutRequest(member_id="M-0001", book_ids=["B001"])
    assert r.loan_days == 14


@pytest.mark.parametrize("member_id", ["M001", "m-0001", "M-00001", "0001", ""])
def test_T112_member_id_format(member_id):
    with pytest.raises(ValidationError):
        CheckoutRequest(member_id=member_id, book_ids=["B001"])
    with pytest.raises(ValidationError):
        HoldRequest(member_id=member_id, book_id="B001")


@pytest.mark.parametrize("days,ok", [(0, False), (1, True), (7, True), (14, True), (15, False), (30, False)])
def test_T113_loan_days_range(days, ok):
    if ok:
        assert CheckoutRequest(member_id="M-0001", book_ids=["B001"], loan_days=days).loan_days == days
    else:
        with pytest.raises(ValidationError):
            CheckoutRequest(member_id="M-0001", book_ids=["B001"], loan_days=days)


def test_T114_book_count_1_to_5():
    CheckoutRequest(member_id="M-0001", book_ids=[f"B00{i}" for i in range(1, 6)])
    with pytest.raises(ValidationError):
        CheckoutRequest(member_id="M-0001", book_ids=[f"B00{i}" for i in range(1, 7)])
    with pytest.raises(ValidationError):
        CheckoutRequest(member_id="M-0001", book_ids=[])


def test_T115_duplicate_book_ids():
    with pytest.raises(ValidationError) as e:
        CheckoutRequest(member_id="M-0001", book_ids=["B001", "B001"])
    assert "중복된 도서 ID가 있습니다" in str(e.value)


def test_T116_book_id_format_in_list():
    with pytest.raises(ValidationError) as e:
        CheckoutRequest(member_id="M-0001", book_ids=["B001", "b1"])
    assert "도서 ID 형식이 올바르지 않습니다: b1" in str(e.value)
    with pytest.raises(ValidationError):
        HoldRequest(member_id="M-0001", book_id="B1")


def test_T117_fee_waiver_reason_min_length():
    FeeWaiverRequest(member_id="M-0003", reason="입원 증빙 제출")
    with pytest.raises(ValidationError):
        FeeWaiverRequest(member_id="M-0003", reason="그냥")


def test_T118_book_available_le_copies():
    Book(id="B100", title="t", author="a", genre="소설", year=2020, copies=2, available=2)
    with pytest.raises(ValidationError):
        Book(id="B100", title="t", author="a", genre="소설", year=2020, copies=2, available=3)
    with pytest.raises(ValidationError):
        Book(id="B100", title="t", author="a", genre="만화", year=2020, copies=2, available=1)
