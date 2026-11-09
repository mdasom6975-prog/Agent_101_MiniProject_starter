"""LangChain 도구 정의 (명세서 5.2절). TODO(M1: catalog, M2: rules, M3: circulation)."""

from __future__ import annotations

import json

from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool, tool

from .schemas import Genre
from .store import LibraryStore

NO_BOOKS = "검색 결과가 없습니다."

CATALOG_TOOL_NAMES = ["search_books", "get_book_detail"]
RULE_TOOL_NAMES = ["search_loan_rules", "search_overdue_rules", "search_facility_rules"]
CIRCULATION_TOOL_NAMES = ["get_member_status", "checkout_books", "place_hold", "waive_fee"]


def make_catalog_tools(store: LibraryStore) -> list[BaseTool]:
    @tool
    def search_books(query: str = "", genre: Genre | None = None, available_only: bool = False) -> str:
        """도서관 장서를 검색한다. 제목이나 저자의 일부로 찾고, 장르와 대출 가능 여부로 거를 수 있다.

        Args:
            query: 제목 또는 저자 검색어. 비워 두면 전체 도서를 대상으로 한다.
            genre: 장르 필터 (소설, 에세이, 과학, 역사, 아동, IT, 자기계발 중 하나).
            available_only: True이면 지금 대출 가능한(available > 0) 도서만 반환한다.
        """
        books = store.search_books(query=query, genre=genre, available_only=available_only)
        if not books:
            return NO_BOOKS
        return json.dumps([b.model_dump() for b in books], ensure_ascii=False)

    @tool
    def get_book_detail(book_id: str) -> str:
        """도서 ID로 도서 한 권의 상세 정보와 예약 대기 인원(hold_queue)을 조회한다.

        Args:
            book_id: 도서 ID (예: B001).
        """
        book = store.get_book(book_id)
        detail = book.model_dump()
        detail["hold_queue"] = len(store.holds.get(book_id, []))
        return json.dumps(detail, ensure_ascii=False)

    return [search_books, get_book_detail]


def make_rule_tools(retrievers: dict[str, BaseRetriever]) -> list[BaseTool]:
    raise NotImplementedError("M2: make_rule_tools")


def make_circulation_tools(store: LibraryStore) -> list[BaseTool]:
    raise NotImplementedError("M3: make_circulation_tools")
