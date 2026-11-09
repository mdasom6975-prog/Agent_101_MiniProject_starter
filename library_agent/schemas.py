"""Pydantic 데이터 스키마 (명세서 4장)."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Genre = Literal["소설", "에세이", "과학", "역사", "아동", "IT", "자기계발"]
MemberType = Literal["일반", "신규"]

MEMBER_ID_PATTERN = r"^M-\d{4}$"
BOOK_ID_PATTERN = r"^B\d{3}$"
MAX_BOOKS_PER_REQUEST = 5
MAX_LOAN_DAYS = 14

_BOOK_ID_RE = re.compile(BOOK_ID_PATTERN)


class Book(BaseModel):
    """도서 한 권. 재고(available)는 소장 수(copies)를 넘을 수 없다."""

    id: str = Field(pattern=BOOK_ID_PATTERN)
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    genre: Genre
    year: int = Field(ge=1900, le=2026)
    copies: int = Field(ge=1)
    available: int = Field(ge=0)

    @model_validator(mode="after")
    def _available_le_copies(self) -> "Book":
        if self.available > self.copies:
            raise ValueError("available은 copies보다 클 수 없습니다")
        return self


class Member(BaseModel):
    """도서관 회원."""

    member_id: str = Field(pattern=MEMBER_ID_PATTERN)
    name: str
    member_type: MemberType
    fee: int = Field(default=0, ge=0)
    suspended: bool = False
    loans: list[str] = Field(default_factory=list)
    holds: list[str] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    """대출 요청. 도서는 한 번에 1~5권, 대출 기간은 1~14일."""

    member_id: str = Field(pattern=MEMBER_ID_PATTERN, description="회원 ID (예: M-0001)")
    book_ids: list[str] = Field(
        min_length=1,
        max_length=MAX_BOOKS_PER_REQUEST,
        description="대출할 도서 ID 목록 (1~5권, 예: ['B001', 'B004'])",
    )
    loan_days: int = Field(default=MAX_LOAN_DAYS, ge=1, le=MAX_LOAN_DAYS, description="대출 기간(일, 1~14)")

    @field_validator("book_ids")
    @classmethod
    def _validate_book_ids(cls, v: list[str]) -> list[str]:
        for bid in v:
            if not _BOOK_ID_RE.match(bid):
                raise ValueError(f"도서 ID 형식이 올바르지 않습니다: {bid}")
        if len(set(v)) != len(v):
            raise ValueError("중복된 도서 ID가 있습니다")
        return v


class LoanItem(BaseModel):
    """대출된 도서 한 건과 반납 예정일."""

    book_id: str
    title: str
    due_date: date


class CheckoutResult(BaseModel):
    """대출 처리 결과."""

    member_id: str
    loans: list[LoanItem]
    remaining_quota: int = Field(ge=0)


class HoldRequest(BaseModel):
    """예약 요청."""

    member_id: str = Field(pattern=MEMBER_ID_PATTERN, description="회원 ID (예: M-0001)")
    book_id: str = Field(pattern=BOOK_ID_PATTERN, description="예약할 도서 ID (예: B002)")


class HoldResult(BaseModel):
    """예약 처리 결과."""

    member_id: str
    book_id: str
    title: str
    queue_position: int = Field(ge=1)


class FeeWaiverRequest(BaseModel):
    """연체료 면제 요청. 사유는 5자 이상."""

    member_id: str = Field(pattern=MEMBER_ID_PATTERN, description="회원 ID (예: M-0003)")
    reason: str = Field(min_length=5, description="면제 사유 (5자 이상)")


class FeeWaiverResult(BaseModel):
    """연체료 면제 결과."""

    member_id: str
    waived_amount: int = Field(ge=1)
    remaining_fee: int = 0


class MemberStatus(BaseModel):
    """회원의 현재 이용 현황."""

    member_id: str
    name: str
    member_type: MemberType
    fee: int
    suspended: bool
    current_loans: int
    loan_limit: int
    holds: list[str]
