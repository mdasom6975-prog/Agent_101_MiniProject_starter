"""M2: 이용 규정 RAG (조 단위 분할, BM25, topic별 검색 도구)."""

import pytest
from langchain_core.retrievers import BaseRetriever

from fakes import call, say, scripted
from helpers import tool_messages, user
from library_agent.agents import build_rules_agent
from library_agent.rag import (
    DEFAULT_RULES_DIR,
    NO_RESULT,
    TOPIC_FILES,
    build_retrievers,
    format_docs,
    load_rules,
    make_retriever,
    tokenize,
)
from library_agent.tools import make_rule_tools

pytestmark = pytest.mark.m2


def test_T201_load_rules_splits_by_article():
    docs = load_rules()
    assert len(docs) == 16
    assert [d.metadata["article"] for d in docs] == [f"제{i}조" for i in range(1, 17)]
    assert {k: sum(d.metadata["topic"] == k for d in docs) for k in TOPIC_FILES} == {"loan": 6, "overdue": 5, "facility": 5}
    d2 = docs[1]
    assert d2.metadata == {"topic": "loan", "article": "제2조", "title": "대출 권수", "source": "01_대출반납.md"}
    assert d2.page_content.startswith("제2조(대출 권수) 일반 회원은")
    assert not any(d.page_content.startswith("#") for d in docs)


def test_T202_load_rules_by_topic():
    assert [d.metadata["article"] for d in load_rules(DEFAULT_RULES_DIR, "overdue")] == ["제7조", "제8조", "제9조", "제10조", "제11조"]
    with pytest.raises(ValueError):
        load_rules(DEFAULT_RULES_DIR, "parking")


def test_T203_tokenize_char_bigrams():
    assert tokenize("신규 회원은") == ["신규", "회원", "원은"]
    assert tokenize("A 1권!") == ["a", "1권"]
    assert tokenize("제2조(대출)") == ["제2", "2조", "대출"]
    assert tokenize("   ") == []


def test_T204_make_retriever_kinds():
    docs = load_rules(topic="loan")
    r = make_retriever(docs, kind="bm25", k=3)
    assert isinstance(r, BaseRetriever)
    assert len(r.invoke("대출 기간 연장 예약 반납")) == 3
    with pytest.raises(ValueError):
        make_retriever(docs, kind="vector")  # embeddings 없음
    with pytest.raises(ValueError):
        make_retriever(docs, kind="tfidf")


@pytest.mark.parametrize(
    "topic,query,article",
    [
        ("loan", "신규 회원은 몇 권까지 빌릴 수 있나요?", "제2조"),
        ("loan", "대출 기간은 며칠인가요?", "제3조"),
        ("loan", "대출 기간을 연장하고 싶어요", "제4조"),
        ("loan", "예약은 1인당 최대 몇 권까지 가능한가요?", "제5조"),
        ("loan", "휴관일에 책을 반납하려면?", "제6조"),
        ("overdue", "연체료는 하루에 얼마인가요?", "제7조"),
        ("overdue", "이용 정지는 언제 되나요?", "제9조"),
        ("overdue", "입원해서 연체됐는데 연체료 면제가 되나요?", "제10조"),
        ("overdue", "분실하거나 훼손한 도서는 어떻게 하나요?", "제11조"),
        ("facility", "월요일에도 문을 여나요?", "제12조"),
        ("facility", "노트북을 쓸 수 있는 곳", "제13조"),
        ("facility", "스터디룸 예약 방법", "제14조"),
        ("facility", "독서 모임에 참여하면 어떤 혜택이 있나요?", "제15조"),
        ("facility", "동화 구연은 언제 하나요?", "제16조"),
    ],
)
def test_T205_bm25_top1_article(retrievers, topic, query, article):
    docs = retrievers[topic].invoke(query)
    assert 1 <= len(docs) <= 2
    assert docs[0].metadata["article"] == article


def test_T206_no_match_returns_empty(retrievers):
    assert retrievers["loan"].invoke("xyz") == []
    assert format_docs([]) == NO_RESULT == "관련 조항을 찾지 못했습니다."
    tools = {t.name: t for t in make_rule_tools(retrievers)}
    assert tools["search_overdue_rules"].invoke({"query": "qwerty"}) == NO_RESULT


def test_T207_rule_tools_output_format(retrievers):
    tools = make_rule_tools(retrievers)
    assert [t.name for t in tools] == ["search_loan_rules", "search_overdue_rules", "search_facility_rules"]
    out = tools[0].invoke({"query": "신규 회원은 몇 권까지 빌릴 수 있나요?"})
    parts = out.split("\n\n")
    assert len(parts) == 2
    assert parts[0].startswith("제2조(대출 권수)")


def test_T208_cross_topic_needs_two_tools(retrievers):
    tools = {t.name: t for t in make_rule_tools(retrievers)}
    q = "신규 회원 첫 대출 권수와 독서 모임 혜택"
    loan_out = tools["search_loan_rules"].invoke({"query": q})
    fac_out = tools["search_facility_rules"].invoke({"query": q})
    assert "제2조" in loan_out and "제15조" not in loan_out  # topic 격리
    assert "제15조" in fac_out and "제2조" not in fac_out


def test_T209_rules_agent_calls_two_tools(retrievers):
    model = scripted(
        call("search_loan_rules", {"query": "신규 회원 대출 권수"}, ("search_facility_rules", {"query": "독서 모임 혜택"})),
        say("신규 회원은 3권(제2조), 독서 모임 참여 시 2권 추가(제15조)."),
    )
    agent = build_rules_agent(model, retrievers)
    result = agent.invoke(user("신규 회원 첫 대출 권수와 독서 모임 혜택 알려줘"))
    tms = tool_messages(result)
    assert [m.name for m in tms] == ["search_loan_rules", "search_facility_rules"]
    assert tms[0].content.startswith("제2조") and tms[1].content.startswith("제15조")
    assert "제15조" in result["messages"][-1].content


def test_T210_vector_path_with_fake_embeddings():
    from langchain_core.embeddings import DeterministicFakeEmbedding

    rs = build_retrievers(kind="vector", k=2, embeddings=DeterministicFakeEmbedding(size=32))
    assert set(rs) == {"loan", "overdue", "facility"}
    docs = rs["facility"].invoke("스터디룸")
    assert len(docs) == 2 and all(d.metadata["topic"] == "facility" for d in docs)
