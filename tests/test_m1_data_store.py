"""M1: 데이터 파일과 LibraryStore 조회 기능."""

import json

import pytest

from library_agent.errors import BookNotFoundError, MemberNotFoundError
from library_agent.schemas import Book, Member
from library_agent.store import DEFAULT_DATA_DIR, DEFAULT_TODAY, LOAN_LIMITS, LibraryStore, load_store

pytestmark = pytest.mark.m1


def test_T101_books_json_valid():
    raw = json.loads((DEFAULT_DATA_DIR / "books.json").read_text(encoding="utf-8"))
    assert len(raw) == 30
    books = [Book(**b) for b in raw]
    assert len({b.id for b in books}) == 30
    assert {b.genre for b in books} == {"소설", "에세이", "과학", "역사", "아동", "IT", "자기계발"}


def test_T102_members_json_valid():
    raw = json.loads((DEFAULT_DATA_DIR / "members.json").read_text(encoding="utf-8"))
    members = [Member(**m) for m in raw]
    assert [m.member_id for m in members] == [f"M-000{i}" for i in range(1, 9)]


def test_T103_load_store_returns_independent_instances():
    a, b = load_store(), load_store()
    assert isinstance(a, LibraryStore)
    assert a.today == DEFAULT_TODAY
    a.books["B001"].available = 0
    a.members["M-0003"].fee = 0
    assert b.books["B001"].available == 2
    assert b.members["M-0003"].fee == 1500
    assert load_store().books["B001"].available == 2


def test_T104_search_by_title_ignores_spaces_and_case(store):
    assert [b.id for b in store.search_books("숲속의작은")] == ["B001"]
    assert [b.id for b in store.search_books("langgraph")] == ["B023"]


def test_T105_search_by_author(store):
    assert [b.id for b in store.search_books("한서윤")] == ["B001", "B013"]


def test_T106_search_genre_and_available_only(store):
    assert [b.id for b in store.search_books(genre="IT", available_only=True)] == ["B003", "B004", "B024"]
    assert [b.id for b in store.search_books(genre="IT")] == ["B003", "B004", "B005", "B023", "B024"]


def test_T107_search_default_limit_and_order(store):
    assert [b.id for b in store.search_books("")] == ["B001", "B002", "B003", "B004", "B005"]
    assert len(store.search_books("", limit=30)) == 30
    assert store.search_books("존재하지않는책") == []


def test_T108_get_book_and_member_errors(store):
    assert store.get_book("B007").title == "세포가 들려주는 이야기"
    with pytest.raises(BookNotFoundError) as e:
        store.get_book("B999")
    assert str(e.value) == "도서를 찾을 수 없습니다: B999"
    assert e.value.code == "BOOK_NOT_FOUND"
    with pytest.raises(MemberNotFoundError) as e2:
        store.get_member("M-9999")
    assert str(e2.value) == "회원을 찾을 수 없습니다: M-9999"


def test_T109_member_status(store):
    s = store.member_status("M-0005")
    assert (s.current_loans, s.loan_limit, s.fee, s.suspended) == (4, 5, 0, False)
    s6 = store.member_status("M-0006")
    assert s6.member_type == "신규" and s6.loan_limit == 3 and s6.holds == ["B002"]
    assert LOAN_LIMITS == {"일반": 5, "신규": 3}
    assert store.holds["B002"] == ["M-0006"]
