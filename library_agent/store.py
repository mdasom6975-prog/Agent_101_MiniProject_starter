"""In-memory 도서관 저장소 (명세서 5.1절). TODO(M1, M3)."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from .errors import MESSAGES, BookNotFoundError, MemberNotFoundError
from .schemas import (
    Book,
    CheckoutRequest,
    CheckoutResult,
    FeeWaiverRequest,
    FeeWaiverResult,
    HoldRequest,
    HoldResult,
    Member,
    MemberStatus,
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_TODAY = date(2026, 11, 3)
LOAN_LIMITS: dict[str, int] = {"일반": 5, "신규": 3}
MAX_HOLDS = 3


def _norm(text: str) -> str:
    """검색 비교용: 소문자화하고 공백을 지운다."""
    return text.lower().replace(" ", "")


class LibraryStore:
    """도서·회원·예약 상태를 메모리에 보관하고 변경한다.

    속성: today, books(dict[str, Book]), members(dict[str, Member]), holds(dict[str, list[str]])
    """

    def __init__(self, books: list[Book], members: list[Member], today: date = DEFAULT_TODAY) -> None:
        self.today = today
        self.books: dict[str, Book] = {b.id: deepcopy(b) for b in books}
        self.members: dict[str, Member] = {m.member_id: deepcopy(m) for m in members}
        # book_id별 예약 대기열. members.json의 holds를 파일(회원) 순서대로 쌓는다.
        self.holds: dict[str, list[str]] = {}
        for member in self.members.values():
            for book_id in member.holds:
                self.holds.setdefault(book_id, []).append(member.member_id)

    @classmethod
    def from_dir(cls, data_dir: Path | str = DEFAULT_DATA_DIR, today: date = DEFAULT_TODAY) -> "LibraryStore":
        data_dir = Path(data_dir)
        raw_books = json.loads((data_dir / "books.json").read_text(encoding="utf-8"))
        raw_members = json.loads((data_dir / "members.json").read_text(encoding="utf-8"))
        return cls([Book(**b) for b in raw_books], [Member(**m) for m in raw_members], today)

    def search_books(self, query: str = "", genre: str | None = None, available_only: bool = False, limit: int = 5) -> list[Book]:
        books = sorted(self.books.values(), key=lambda b: b.id)
        if genre is not None:
            books = [b for b in books if b.genre == genre]
        if available_only:
            books = [b for b in books if b.available > 0]
        q = _norm(query)
        if q:
            books = [b for b in books if q in _norm(b.title) or q in _norm(b.author)]
        return books[:limit]

    def get_book(self, book_id: str) -> Book:
        if book_id not in self.books:
            raise BookNotFoundError(MESSAGES["BOOK_NOT_FOUND"].format(book_id=book_id))
        return self.books[book_id]

    def get_member(self, member_id: str) -> Member:
        if member_id not in self.members:
            raise MemberNotFoundError(MESSAGES["MEMBER_NOT_FOUND"].format(member_id=member_id))
        return self.members[member_id]

    def loan_limit(self, member_id: str) -> int:
        return LOAN_LIMITS[self.get_member(member_id).member_type]

    def member_status(self, member_id: str) -> MemberStatus:
        member = self.get_member(member_id)
        return MemberStatus(
            member_id=member.member_id,
            name=member.name,
            member_type=member.member_type,
            fee=member.fee,
            suspended=member.suspended,
            current_loans=len(member.loans),
            loan_limit=self.loan_limit(member_id),
            holds=sorted(book_id for book_id, queue in self.holds.items() if member_id in queue),
        )

    def checkout(self, req: CheckoutRequest) -> CheckoutResult:
        raise NotImplementedError("M3: LibraryStore.checkout")

    def place_hold(self, req: HoldRequest) -> HoldResult:
        raise NotImplementedError("M3: LibraryStore.place_hold")

    def waive_fee(self, req: FeeWaiverRequest) -> FeeWaiverResult:
        raise NotImplementedError("M3: LibraryStore.waive_fee")


def load_store(data_dir: Path | str = DEFAULT_DATA_DIR, today: date = DEFAULT_TODAY) -> LibraryStore:
    """기본 데이터 폴더에서 새 LibraryStore를 만든다. 호출할 때마다 독립된 인스턴스를 반환한다."""
    return LibraryStore.from_dir(data_dir, today)
