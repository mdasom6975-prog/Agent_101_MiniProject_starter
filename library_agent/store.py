"""In-memory 도서관 저장소 (명세서 5.1절). TODO(M1, M3)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

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


class LibraryStore:
    """도서·회원·예약 상태를 메모리에 보관하고 변경한다.

    속성: today, books(dict[str, Book]), members(dict[str, Member]), holds(dict[str, list[str]])
    """

    def __init__(self, books: list[Book], members: list[Member], today: date = DEFAULT_TODAY) -> None:
        raise NotImplementedError("M1: LibraryStore.__init__")

    @classmethod
    def from_dir(cls, data_dir: Path | str = DEFAULT_DATA_DIR, today: date = DEFAULT_TODAY) -> "LibraryStore":
        raise NotImplementedError("M1: LibraryStore.from_dir")

    def search_books(self, query: str = "", genre: str | None = None, available_only: bool = False, limit: int = 5) -> list[Book]:
        raise NotImplementedError("M1: LibraryStore.search_books")

    def get_book(self, book_id: str) -> Book:
        raise NotImplementedError("M1: LibraryStore.get_book")

    def get_member(self, member_id: str) -> Member:
        raise NotImplementedError("M1: LibraryStore.get_member")

    def loan_limit(self, member_id: str) -> int:
        raise NotImplementedError("M1: LibraryStore.loan_limit")

    def member_status(self, member_id: str) -> MemberStatus:
        raise NotImplementedError("M1: LibraryStore.member_status")

    def checkout(self, req: CheckoutRequest) -> CheckoutResult:
        raise NotImplementedError("M3: LibraryStore.checkout")

    def place_hold(self, req: HoldRequest) -> HoldResult:
        raise NotImplementedError("M3: LibraryStore.place_hold")

    def waive_fee(self, req: FeeWaiverRequest) -> FeeWaiverResult:
        raise NotImplementedError("M3: LibraryStore.waive_fee")


def load_store(data_dir: Path | str = DEFAULT_DATA_DIR, today: date = DEFAULT_TODAY) -> LibraryStore:
    """기본 데이터 폴더에서 새 LibraryStore를 만든다. 호출할 때마다 독립된 인스턴스를 반환한다."""
    raise NotImplementedError("M1: load_store")
