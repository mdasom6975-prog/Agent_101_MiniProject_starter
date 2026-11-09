"""M4: harness middleware (tool error wrapper, ModelCallLimit, LoopGuard, JSONL trace)."""

import itertools
from types import SimpleNamespace

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolErrorMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from fakes import call, say, scripted, scripted_stream
from helpers import tool_messages, user
from library_agent.agents import build_catalog_agent, build_circulation_agent
from library_agent.errors import UnpaidFeeError
from library_agent.middleware import (
    JsonlTraceMiddleware,
    LoopGuardMiddleware,
    default_middleware,
    read_trace,
    tool_error_handler,
)
from library_agent.tools import make_circulation_tools

pytestmark = pytest.mark.m4


def test_T401_tool_error_handler_strings():
    req = SimpleNamespace(tool_call={"name": "checkout_books", "args": {}, "id": "x"})
    assert tool_error_handler(UnpaidFeeError("미납 연체료가 있어 대출할 수 없습니다: 1500원"), req) == (
        "[UNPAID_FEE] 미납 연체료가 있어 대출할 수 없습니다: 1500원"
    )
    assert tool_error_handler(KeyError("k"), req) == (
        "[INTERNAL] checkout_books 실행 중 예기치 못한 오류가 발생했습니다 (KeyError)"
    )


def test_T402_wrapper_turns_domain_error_into_tool_message(store, thread):
    model = scripted(call("checkout_books", {"member_id": "M-0003", "book_ids": ["B001"]}), say("연체료 1500원을 먼저 납부해 주세요."))
    agent = build_circulation_agent(model, store, checkpointer=InMemorySaver())
    result = agent.invoke(user("M-0003 B001 대출"), thread)
    [tm] = tool_messages(result, "checkout_books")
    assert tm.status == "error"
    assert tm.content == "[UNPAID_FEE] 미납 연체료가 있어 대출할 수 없습니다: 1500원"
    assert result["messages"][-1].content.startswith("연체료 1500원")


def test_T403_without_wrapper_domain_error_propagates(store):
    model = scripted(call("checkout_books", {"member_id": "M-0003", "book_ids": ["B001"]}), say("x"))
    bare = create_agent(model, tools=make_circulation_tools(store))
    with pytest.raises(UnpaidFeeError):
        bare.invoke(user("M-0003 B001 대출"))


def test_T404_model_call_limit_ends_run(store):
    endless = scripted_stream(call("search_books", {"query": f"q{i}"}) for i in itertools.count())
    agent = build_catalog_agent(endless, store, model_call_limit=3)
    result = agent.invoke(user("끝없이 검색"))
    assert len(endless.received) == 3
    last = result["messages"][-1]
    assert isinstance(last, AIMessage) and "Model call limits exceeded" in last.content


def test_T405_loop_guard_blocks_third_identical_call(store):
    same = {"query": "숲속"}
    model = scripted(call("search_books", same), call("search_books", same), call("search_books", same), say("B001입니다."))
    agent = build_catalog_agent(model, store)
    result = agent.invoke(user("숲속 찾아줘"))
    tms = tool_messages(result, "search_books")
    assert [m.status for m in tms] == ["success", "success", "error"]
    assert tms[2].content.startswith("[LOOP_GUARD] 같은 인자로 search_books을(를) 3번째 호출하여 차단했습니다.")
    assert result["messages"][-1].content == "B001입니다."


def test_T406_loop_guard_counts_since_last_human_message():
    g = LoopGuardMiddleware(max_repeats=2)
    tc = lambda: AIMessage(content="", tool_calls=[{"name": "search_books", "args": {"query": "a"}, "id": "1"}])  # noqa: E731
    msgs = [HumanMessage("1"), tc(), tc(), HumanMessage("2"), tc()]
    assert g.count_repeats(msgs, "search_books", {"query": "a"}) == 1
    assert g.count_repeats(msgs, "search_books", {"query": "b"}) == 0
    with pytest.raises(ValueError):
        LoopGuardMiddleware(max_repeats=0)


def test_T407_default_middleware_composition(log_path):
    mws = default_middleware("catalog_agent", log_path=log_path, model_call_limit=4, max_repeats=2)
    assert [type(m) for m in mws] == [JsonlTraceMiddleware, ModelCallLimitMiddleware, LoopGuardMiddleware, ToolErrorMiddleware]
    assert mws[1].run_limit == 4 and mws[1].exit_behavior == "end"
    no_log = default_middleware("x")
    assert [type(m) for m in no_log] == [ModelCallLimitMiddleware, LoopGuardMiddleware, ToolErrorMiddleware]


def test_T408_jsonl_trace_records_each_tool_call(store, log_path):
    model = scripted(call("search_books", {"query": "한서윤"}), call("get_book_detail", {"book_id": "B999"}), say("끝"))
    build_catalog_agent(model, store, log_path=log_path).invoke(user("한서윤 책"))
    rows = read_trace(log_path)
    assert [r["tool"] for r in rows] == ["search_books", "get_book_detail"]
    assert [r["status"] for r in rows] == ["success", "error"]
    assert all(r["agent"] == "catalog_agent" for r in rows)
    assert {"ts", "agent", "tool", "args", "tool_call_id", "status", "output", "duration_ms"} <= set(rows[0])
    assert rows[0]["args"] == {"query": "한서윤"}
    assert rows[1]["output"] == "[BOOK_NOT_FOUND] 도서를 찾을 수 없습니다: B999"


def test_T409_read_trace_missing_file(tmp_path):
    assert read_trace(tmp_path / "nope.jsonl") == []
