# M2. 규정 RAG (15점)

> 출처: 명세서 4장 · 테스트 `tests/test_m2_rag.py`
> 완료 조건: `pytest -q -m m2` → **23 passed** (T201–T210, T205는 14 case)
> 관련 실습: Agentic RAG, topic별 retriever tool, `create_agent`

## 1. 구현 대상

```python
# rag.py  (상수 DEFAULT_RULES_DIR, TOPIC_FILES, NO_RESULT는 stub에 있다)
def load_rules(rules_dir=DEFAULT_RULES_DIR, topic=None) -> list[Document]
def tokenize(text) -> list[str]
class BM25Retriever(BaseRetriever):            # 필드: docs, k=2, k1=1.5, b=0.75
    def score(self, query) -> list[float]
    def _get_relevant_documents(self, query, *, run_manager) -> list[Document]
def make_retriever(docs, kind="bm25", k=2, embeddings=None) -> BaseRetriever
def build_retrievers(rules_dir=DEFAULT_RULES_DIR, kind="bm25", k=2, embeddings=None) -> dict[str, BaseRetriever]
def format_docs(docs) -> str

# tools.py
def make_rule_tools(retrievers) -> list[BaseTool]
    # [search_loan_rules, search_overdue_rules, search_facility_rules]

# agents.py
def build_rules_agent(model, retrievers, *, log_path=None, model_call_limit=6, checkpointer=None)
```

> **선행 작업**: M2의 agent 테스트(T209)는 `default_middleware()`를 쓴다. 그래서 M2에서 `default_middleware`, `make_tool_error_middleware`, `LoopGuardMiddleware`를 **최소한으로 먼저** 구현하고 M4에서 완성한다 (명세서 2.6절, 상세는 [M4 문서](M4_Harness_Supervisor_평가기.md)).

## 2. 규정 데이터

| 파일 | topic | 조항 |
|---|---|---|
| `data/rules/01_대출반납.md` | `loan` | 제1–6조 |
| `data/rules/02_연체이용제한.md` | `overdue` | 제7–11조 |
| `data/rules/03_시설프로그램.md` | `facility` | 제12–16조 |

각 조는 한 줄이다. 총 16개.

## 3. Requirements

### load_rules (T201, T202)
- 정규식 `^(제\d+조)\(([^)]+)\)\s*(.+)$`에 맞는 줄 하나를 Document 하나로 만든다.
- `page_content`는 그 줄(strip)이다.
- `metadata = {"topic", "article", "title", "source"}`
  - 예: `{"topic": "loan", "article": "제2조", "title": "대출 권수", "source": "01_대출반납.md"}`
- `topic=None`이면 `TOPIC_FILES` 순서로 16개를 반환한다. topic을 주면 그 파일만 반환한다.
- 모르는 topic은 `ValueError`.

### tokenize (T203)
1. 소문자화
2. `re.findall(r"[0-9a-z가-힣]+")`
3. 길이 1인 토큰은 그대로 두고, 길이 2 이상은 문자 bigram으로 펼친다.

예:
- `"신규 회원은"` → `["신규", "회원", "원은"]`
- `"제2조(대출)"` → `["제2", "2조", "대출"]`

### BM25Retriever.score (T205)
Okapi BM25:

- `idf(t) = ln((N − n_t + 0.5) / (n_t + 0.5) + 1)`
- `score = Σ_t idf(t) · f · (k1 + 1) / (f + k1 · (1 − b + b · dl / avgdl))`
- 질의 토큰이 중복되면 **중복만큼 더한다**.

(N = 문서 수, n_t = 토큰 t를 포함한 문서 수, f = 문서 내 t의 빈도, dl = 문서 길이(토큰 수), avgdl = 평균 문서 길이)

### BM25Retriever._get_relevant_documents (T205, T206)
- 점수 내림차순으로 정렬한다. **동점이면 원래 순서**를 유지한다.
- **점수 0인 문서는 뺀다.**
- 앞에서 k개를 반환한다.

### make_retriever (T204, T210)
- `"bm25"` → `BM25Retriever`
- `"vector"` → `InMemoryVectorStore.from_documents(docs, embeddings).as_retriever(search_kwargs={"k": k})`
- vector인데 embeddings가 없거나, 다른 kind면 `ValueError`.

### build_retrievers (T205, T210)
- `loan`, `overdue`, `facility` 각각에 대해 `make_retriever(load_rules(rules_dir, topic), kind, k, embeddings)`를 만든 dict를 반환한다.

### format_docs (T206, T207)
- page_content를 `"\n\n"`로 잇는다.
- 빈 목록이면 `NO_RESULT` (`관련 조항을 찾지 못했습니다.`)

### 규정 도구 3개 (T206–T208)
- `query: str`를 받아 `format_docs(retrievers[topic].invoke(query))`를 반환한다.
- 각 도구는 **자기 topic만** 검색한다.
- 순서: `search_loan_rules`, `search_overdue_rules`, `search_facility_rules`

### build_rules_agent (T209)
```python
create_agent(model, tools=make_rule_tools(retrievers),
             system_prompt=RULES_PROMPT,
             middleware=default_middleware("rules_agent", ...),
             checkpointer=checkpointer, name="rules_agent")
```

## 4. T205: BM25 top-1 기대 조항 (14 case)

| topic | query | top-1 |
|---|---|---|
| loan | 신규 회원은 몇 권까지 빌릴 수 있나요? | 제2조 |
| loan | 대출 기간은 며칠인가요? | 제3조 |
| loan | 대출 기간을 연장하고 싶어요 | 제4조 |
| loan | 예약은 1인당 최대 몇 권까지 가능한가요? | 제5조 |
| loan | 휴관일에 책을 반납하려면? | 제6조 |
| overdue | 연체료는 하루에 얼마인가요? | 제7조 |
| overdue | 이용 정지는 언제 되나요? | 제9조 |
| overdue | 입원해서 연체됐는데 연체료 면제가 되나요? | 제10조 |
| overdue | 분실하거나 훼손한 도서는 어떻게 하나요? | 제11조 |
| facility | 월요일에도 문을 여나요? | 제12조 |
| facility | 노트북을 쓸 수 있는 곳 | 제13조 |
| facility | 스터디룸 예약 방법 | 제14조 |
| facility | 독서 모임에 참여하면 어떤 혜택이 있나요? | 제15조 |
| facility | 동화 구연은 언제 하나요? | 제16조 |

## 5. 테스트 목록

| Test | 내용 |
|---|---|
| T201 | load_rules가 조 단위로 16개를 나누고 metadata가 맞는지 |
| T202 | topic별 로딩, 모르는 topic은 ValueError |
| T203 | tokenize bigram 규칙 |
| T204 | make_retriever kind 분기와 ValueError |
| T205 | BM25 top-1 조항 (14 case) |
| T206 | 매칭이 없으면 빈 결과 → NO_RESULT |
| T207 | 규정 도구 출력 형식 |
| T208 | cross-topic 질문은 도구 두 개가 필요 |
| T209 | rules agent가 도구 두 개를 호출 (fake model) |
| T210 | `DeterministicFakeEmbedding`으로 vector 경로 확인 |

## 6. 구현 시 주의점 (부록 A.3)

BM25 top-1이 T205와 다르면 아래 다섯 가지를 확인한다.
1. 길이 1 토큰을 유지했는가
2. 길이 2 이상을 bigram으로 펼쳤는가
3. idf 안에 `+1`이 있는가
4. 점수 0인 문서를 뺐는가
5. 동점일 때 원래 순서를 유지했는가 (안정 정렬)

추가:
- 도구가 자기 topic의 retriever만 쓰도록, 클로저로 topic을 묶을 때 late binding에 주의한다.
- `BM25Retriever`는 pydantic 기반 `BaseRetriever`다. 필드 선언 방식(`docs: list[Document]`, `k: int = 2` 등)을 따른다.
