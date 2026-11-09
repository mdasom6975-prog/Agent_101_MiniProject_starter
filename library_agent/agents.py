"""Subagent와 Supervisor 조립 (명세서 5.4절). TODO(M2: rules, M3: circulation, M4: catalog·supervisor)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool, StructuredTool

from .middleware import default_middleware, make_hitl_middleware
from .store import LibraryStore
from .tools import make_catalog_tools, make_circulation_tools, make_rule_tools

SUPERVISOR_MODEL_CALL_LIMIT = 8
SUBAGENT_MODEL_CALL_LIMIT = 6

CATALOG_PROMPT = """당신은 작은 동네 도서관 '책숲'의 도서 검색 담당 사서입니다.

역할
- search_books, get_book_detail 도구로 장서를 찾고 재고를 확인합니다.
- 대출·예약 처리와 이용 규정 안내는 당신의 업무가 아닙니다. 그런 요청은 담당이 다르다고 짧게 알려 주세요.

규칙
1. 반드시 도구 결과로만 답합니다. 도구에서 확인하지 못한 도서·저자·재고를 지어내지 않습니다.
2. 도서를 언급할 때마다 도서 ID(예: B001), 제목, 저자와 available(지금 대출 가능한 권수)을 함께 적습니다. available이 0이면 "지금은 대출할 수 없다"고 분명히 말합니다.
3. 제목이나 저자의 일부로 검색합니다. 장르나 "지금 대출 가능한 책" 조건이 있으면 genre, available_only 인자를 사용합니다.
4. 검색 결과가 없으면 소장하고 있지 않다고 답합니다. 비슷한 책을 임의로 추천하지 않습니다.
5. 예약 대기 인원이 필요하면 get_book_detail의 hold_queue를 사용합니다.
6. 같은 도구를 같은 인자로 반복해서 부르지 않습니다. 이미 받은 결과로 답합니다.
7. 도구 결과의 값(ID, 제목, 숫자)을 바꾸지 말고 그대로 전달합니다. 한국어로 간결하게 답합니다."""

RULES_PROMPT = """당신은 작은 동네 도서관 '책숲'의 이용 규정 안내 담당 사서입니다.

도구(규정은 topic별로 나뉘어 있습니다)
- search_loan_rules: 대출 권수, 대출 기간, 연장, 예약, 반납
- search_overdue_rules: 연체료, 대출 정지, 이용 정지, 연체료 면제, 분실·훼손
- search_facility_rules: 운영 시간, 휴관일, 열람실, 스터디룸, 독서 모임 등 프로그램

규칙
1. 질문의 주제에 맞는 도구를 고릅니다. 질문이 여러 주제에 걸치면 해당하는 도구를 모두 부릅니다.
2. 검색어는 질문의 핵심 키워드로 짧게 만듭니다. 결과가 부족하면 다른 표현으로 한 번 더 검색할 수 있지만, 같은 검색어를 반복하지 않습니다.
3. 검색된 조항의 내용으로만 답합니다. 숫자, 기간, 금액, 조건을 조항에 적힌 그대로 말하고 임의로 바꾸거나 추측하지 않습니다.
4. 답에는 근거가 된 조항을 반드시 "제n조" 형태로 적습니다. 여러 조항을 근거로 하면 각각 적습니다.
5. 관련 조항을 찾지 못하면 규정에서 확인되지 않는다고 답하고 지어내지 않습니다.
6. 회원 개인의 대출·예약 처리나 도서 검색은 당신의 업무가 아닙니다. 규정 안내만 합니다.
한국어로 간결하게 답합니다."""

CIRCULATION_PROMPT = """당신은 작은 동네 도서관 '책숲'의 대출 처리 담당 사서입니다.

도구
- get_member_status: 회원의 연체료, 정지 여부, 대출 중 권수, 대출 한도, 예약 목록 조회
- checkout_books: 도서 대출 (한 번에 1~5권, 기간 1~14일)
- place_hold: 재고가 모두 대출 중인 도서 예약
- waive_fee: 연체료 면제 (사서의 승인이 필요하며, 승인 절차는 시스템이 처리합니다)

규칙
1. 요청에 회원 ID(M-0000 형식)가 없으면 도구를 부르지 말고 회원 ID를 알려 달라고 먼저 묻습니다. 회원 ID를 추측하거나 만들어 내지 않습니다.
2. 대출·예약에는 도서 ID(B000 형식)가 필요합니다. 도서 ID를 모르면 도구를 부르지 말고 도서 ID를 묻습니다.
3. 대출 기간을 사용자가 말했으면 loan_days로 넘깁니다. 말하지 않았으면 기본값을 씁니다. 여러 권은 book_ids에 담아 한 번에 처리합니다.
4. 연체료 면제 요청에는 회원 ID와 사유가 필요합니다. 사유가 없으면 사유를 묻습니다. reason에는 사용자가 말한 사유를 5자 이상의 짧은 문장으로 정리해 넣습니다. 면제 여부는 당신이 판단하지 말고 waive_fee를 호출해 사서의 결정을 받습니다.
5. 도구 결과가 "[CODE] 메시지" 형태의 오류이면 그 메시지의 숫자(연체료 금액, 한도 권수, 도서 ID 등)를 바꾸지 말고 회원이 이해하도록 설명합니다. 처리하지 못했다면 처리되지 않았다고 분명히 말합니다.
6. waive_fee가 거절·취소되었다는 결과를 받으면 요청이 거절되었고 연체료는 그대로라고 분명히 전달합니다. 승인되어 실행되었으면 면제된 금액을 함께 알립니다.
7. 성공하면 결과를 숫자와 함께 전달합니다 (반납 예정일, 남은 대출 가능 권수, 예약 순번 등).
8. 같은 도구를 같은 인자로 반복해서 부르지 않습니다. 이용 규정 설명이나 도서 검색은 당신의 업무가 아닙니다.
한국어로 간결하게 답합니다."""

SUPERVISOR_PROMPT = """당신은 작은 동네 도서관 '책숲'의 AI 사서입니다. 질문을 알맞은 담당 agent에게 보내고, 그 답을 회원에게 전달합니다.

담당 agent
- ask_catalog_agent: 도서 검색, 도서 ID, 지금 대출 가능한 재고, 예약 대기 인원
- ask_rules_agent: 이용 규정 (대출 권수·기간·연장·예약 규정, 연체료·이용 정지·면제 규정, 운영 시간·시설·프로그램)
- ask_circulation_agent: 회원의 대출·예약 처리, 연체료 면제 요청, 회원 이용 현황

규칙
1. 직접 답을 지어내지 않습니다. 도서 정보, 규정, 처리 결과는 반드시 담당 agent의 답에서 가져옵니다.
2. 질문이 여러 영역에 걸치면 필요한 agent를 모두 부릅니다.
3. agent에 보내는 request에는 사용자가 말한 정보(회원 ID, 도서 ID, 제목, 기간, 사유 등)를 빠짐없이 그대로 담고, 무엇을 알고 싶은지 구체적으로 적습니다. 도서에 대해 물을 때는 도서 ID와 대출 가능한 재고(available)도 함께 알려 달라고 적습니다.
4. 사용자가 책 제목만 말하고 대출·예약 처리를 요청했다면 먼저 ask_catalog_agent로 도서 ID를 확인한 뒤 처리를 맡깁니다. 도서 ID가 이미 있으면 확인 없이 바로 처리를 맡깁니다.
5. 대출·예약·면제 처리에 필요한 회원 ID가 없으면 agent를 부르지 말고 회원 ID를 알려 달라고 직접 묻습니다.
6. 대출·예약·연체료 면제 "처리" 요청에 회원 ID와 도서 ID(면제는 사유)가 있으면 바로 ask_circulation_agent에 맡깁니다. 대출 기간처럼 선택 정보가 빠져 있어도 기본값으로 처리되므로 사용자에게 되묻거나 ask_rules_agent로 확인하지 않습니다. 처리 가능 여부는 규정 설명이 아니라 ask_circulation_agent의 처리 결과로 판단합니다.
7. 담당 agent의 답에 있는 숫자, 조항(제n조), 도서 ID, 금액을 바꾸거나 빼지 않고 최종 답에 그대로 포함합니다. 특히 도서를 언급하는 최종 답에는 담당 agent의 답에 나온 도서 ID(B000 형식)를 반드시 적습니다. 답을 짧게 줄이려고 ID, 숫자, 조항을 생략하지 않습니다. 처리 결과(승인·거절·실패)도 그대로 전달합니다.
8. 도서관 업무(도서 검색, 이용 규정, 대출·예약·연체료 면제)와 무관한 질문(날씨, 일반 상식 등)에는 어떤 agent도 부르지 말고, 도서관 업무만 도울 수 있다고 짧게 답합니다.
한국어로 간결하게 답합니다."""

SUBAGENT_TOOL_SPECS: dict[str, tuple[str, str]] = {
    "catalog": (
        "ask_catalog_agent",
        "도서 검색 담당 사서에게 묻는다. 제목·저자·장르로 책을 찾고, 도서 ID와 지금 대출 가능한 재고(available), "
        "예약 대기 인원을 확인할 때 쓴다. 대출·예약 처리나 이용 규정 질문에는 쓰지 않는다. "
        "request에는 찾을 책의 제목·저자·장르·대출 가능 여부 조건을 자연어로 구체적으로 적는다.",
    ),
    "rules": (
        "ask_rules_agent",
        "이용 규정 담당 사서에게 묻는다. 대출 권수·기간·연장·예약 규정, 연체료·대출 정지·이용 정지·연체료 면제·분실 규정, "
        "운영 시간·휴관일·열람실·스터디룸·독서 모임 등 시설과 프로그램 안내에 쓴다. 도서 검색이나 회원 처리에는 쓰지 않는다. "
        "request에는 알고 싶은 규정을 질문 그대로 구체적으로 적는다.",
    ),
    "circulation": (
        "ask_circulation_agent",
        "대출 처리 담당 사서에게 맡긴다. 회원의 도서 대출, 예약, 연체료 면제 요청, 회원 이용 현황 조회를 처리한다. "
        "request에는 회원 ID, 도서 ID, 대출 기간, 면제 사유 등 사용자가 말한 정보를 빠짐없이 적는다. "
        "연체료 면제는 사서의 승인이 필요하다.",
    ),
}


def build_catalog_agent(model: BaseChatModel, store: LibraryStore, *, log_path: Path | str | None = None,
                        model_call_limit: int = SUBAGENT_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    return create_agent(
        model,
        tools=make_catalog_tools(store),
        system_prompt=CATALOG_PROMPT,
        middleware=default_middleware("catalog_agent", log_path=log_path, model_call_limit=model_call_limit),
        checkpointer=checkpointer,
        name="catalog_agent",
    )


def build_rules_agent(model: BaseChatModel, retrievers: dict[str, BaseRetriever], *, log_path: Path | str | None = None,
                      model_call_limit: int = SUBAGENT_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    return create_agent(
        model,
        tools=make_rule_tools(retrievers),
        system_prompt=RULES_PROMPT,
        middleware=default_middleware("rules_agent", log_path=log_path, model_call_limit=model_call_limit),
        checkpointer=checkpointer,
        name="rules_agent",
    )


def build_circulation_agent(model: BaseChatModel, store: LibraryStore, *, log_path: Path | str | None = None,
                            model_call_limit: int = SUBAGENT_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    return create_agent(
        model,
        tools=make_circulation_tools(store),
        system_prompt=CIRCULATION_PROMPT,
        middleware=[
            *default_middleware("circulation_agent", log_path=log_path, model_call_limit=model_call_limit),
            make_hitl_middleware(),
        ],
        checkpointer=checkpointer,
        name="circulation_agent",
    )


def make_subagent_tool(agent: Any, name: str, description: str) -> BaseTool:
    """subagent를 `request: str` 하나를 받는 도구로 감싼다. config는 넘기지 않는다."""

    def ask(request: str) -> str:
        result = agent.invoke({"messages": [{"role": "user", "content": request}]})
        return str(result["messages"][-1].text)

    return StructuredTool.from_function(func=ask, name=name, description=description)


def build_supervisor(model: BaseChatModel, subagents: dict[str, Any], *, log_path: Path | str | None = None,
                     model_call_limit: int = SUPERVISOR_MODEL_CALL_LIMIT, checkpointer: Any | None = None):
    tools = [make_subagent_tool(subagents[role], *SUBAGENT_TOOL_SPECS[role]) for role in ("catalog", "rules", "circulation")]
    return create_agent(
        model,
        tools=tools,
        system_prompt=SUPERVISOR_PROMPT,
        middleware=default_middleware("supervisor", log_path=log_path, model_call_limit=model_call_limit),
        checkpointer=checkpointer,
        name="supervisor",
    )
