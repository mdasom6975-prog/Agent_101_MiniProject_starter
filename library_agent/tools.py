"""LangChain 도구 정의 (명세서 5.2절). TODO(M1: catalog, M2: rules, M3: circulation)."""

from __future__ import annotations

from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool

from .store import LibraryStore

NO_BOOKS = "검색 결과가 없습니다."

CATALOG_TOOL_NAMES = ["search_books", "get_book_detail"]
RULE_TOOL_NAMES = ["search_loan_rules", "search_overdue_rules", "search_facility_rules"]
CIRCULATION_TOOL_NAMES = ["get_member_status", "checkout_books", "place_hold", "waive_fee"]


def make_catalog_tools(store: LibraryStore) -> list[BaseTool]:
    raise NotImplementedError("M1: make_catalog_tools")


def make_rule_tools(retrievers: dict[str, BaseRetriever]) -> list[BaseTool]:
    raise NotImplementedError("M2: make_rule_tools")


def make_circulation_tools(store: LibraryStore) -> list[BaseTool]:
    raise NotImplementedError("M3: make_circulation_tools")
