"""Pydantic 데이터 스키마 (명세서 4장).

TODO(M1): 각 클래스에 명세서 4.2절 표의 필드와 제약(Field, field_validator, model_validator)을 구현한다.
지금은 필드가 없는 빈 모델이라 어떤 입력도 검증하지 않는다.
"""

from __future__ import annotations

from datetime import date  # noqa: F401  (LoanItem.due_date 구현 시 사용)
from typing import Literal

from pydantic import BaseModel

Genre = Literal["소설", "에세이", "과학", "역사", "아동", "IT", "자기계발"]
MemberType = Literal["일반", "신규"]

MEMBER_ID_PATTERN = r"^M-\d{4}$"
BOOK_ID_PATTERN = r"^B\d{3}$"
MAX_BOOKS_PER_REQUEST = 5
MAX_LOAN_DAYS = 14


class Book(BaseModel):
    """TODO: id, title, author, genre, year, copies, available (+ available <= copies)."""


class Member(BaseModel):
    """TODO: member_id, name, member_type, fee, suspended, loans, holds."""


class CheckoutRequest(BaseModel):
    """TODO: member_id, book_ids(1~5, 형식·중복 검사), loan_days(기본 14, 1~14)."""


class LoanItem(BaseModel):
    """TODO: book_id, title, due_date."""


class CheckoutResult(BaseModel):
    """TODO: member_id, loans, remaining_quota."""


class HoldRequest(BaseModel):
    """TODO: member_id, book_id."""


class HoldResult(BaseModel):
    """TODO: member_id, book_id, title, queue_position."""


class FeeWaiverRequest(BaseModel):
    """TODO: member_id, reason(5자 이상)."""


class FeeWaiverResult(BaseModel):
    """TODO: member_id, waived_amount, remaining_fee."""


class MemberStatus(BaseModel):
    """TODO: member_id, name, member_type, fee, suspended, current_loans, loan_limit, holds."""
