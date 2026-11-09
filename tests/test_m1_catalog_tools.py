"""M1: 도서 검색 도구."""

import json

import pytest
from pydantic import ValidationError

from library_agent.errors import BookNotFoundError
from library_agent.tools import NO_BOOKS, make_catalog_tools

pytestmark = pytest.mark.m1


def _tools(store):
    return {t.name: t for t in make_catalog_tools(store)}


def test_T121_catalog_tool_names(store):
    assert [t.name for t in make_catalog_tools(store)] == ["search_books", "get_book_detail"]


def test_T122_search_books_returns_json(store):
    out = _tools(store)["search_books"].invoke({"query": "한서윤"})
    data = json.loads(out)
    assert [d["id"] for d in data] == ["B001", "B013"]
    assert set(data[0]) == {"id", "title", "author", "genre", "year", "copies", "available"}
    out2 = _tools(store)["search_books"].invoke({"genre": "아동", "available_only": True})
    assert [d["id"] for d in json.loads(out2)] == ["B015", "B017", "B028"]


def test_T123_search_books_no_result(store):
    assert _tools(store)["search_books"].invoke({"query": "해리 포터"}) == NO_BOOKS == "검색 결과가 없습니다."


def test_T124_get_book_detail_hold_queue(store):
    d = json.loads(_tools(store)["get_book_detail"].invoke({"book_id": "B002"}))
    assert d["id"] == "B002" and d["available"] == 0 and d["hold_queue"] == 1
    assert json.loads(_tools(store)["get_book_detail"].invoke({"book_id": "B001"}))["hold_queue"] == 0


def test_T125_get_book_detail_raises_domain_error(store):
    # 도구는 도메인 오류를 삼키지 않는다. ToolMessage 변환은 middleware(M4)의 일이다.
    with pytest.raises(BookNotFoundError):
        _tools(store)["get_book_detail"].invoke({"book_id": "B999"})


def test_T126_search_books_genre_literal(store):
    with pytest.raises(ValidationError):
        _tools(store)["search_books"].invoke({"genre": "만화"})
