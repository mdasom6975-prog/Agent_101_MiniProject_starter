# M3. 대출 · 예약 · HITL (20점)

> 출처: 명세서 5장, 부록 A.2 · 테스트 `tests/test_m3_circulation.py`, `tests/test_m3_hitl.py`
> 완료 조건: `pytest -q -m m3` → **18 passed** (T301–T313, T321–T325)
> 관련 실습: Pydantic args_schema, `HumanInTheLoopMiddleware`, checkpointer

## 1. 구현 대상

```python
# store.py  (LOAN_LIMITS = {"일반": 5, "신규": 3}, MAX_HOLDS = 3)
def checkout(self, req: CheckoutRequest) -> CheckoutResult
def place_hold(self, req: HoldRequest) -> HoldResult
def waive_fee(self, req: FeeWaiverRequest) -> FeeWaiverResult

# tools.py
def make_circulation_tools(store) -> list[BaseTool]
    # [get_member_status, checkout_books, place_hold, waive_fee]

# middleware.py
def make_hitl_middleware() -> HumanInTheLoopMiddleware

# agents.py
def build_circulation_agent(model, store, *, log_path=None, model_call_limit=6, checkpointer=None)

# app.py
def get_interrupts(result) -> list
```

## 2. store 동작

| 메서드 | 검사 순서 (처음 걸린 오류를 raise) | 성공 시 |
|---|---|---|
| `checkout` | MEMBER_NOT_FOUND → MEMBER_SUSPENDED → UNPAID_FEE → BOOK_NOT_FOUND(요청 순서) → LOAN_LIMIT → NOT_AVAILABLE(요청 순서) | 각 도서 available −1, member.loans에 추가, `due_date = today + loan_days`, `remaining_quota = 한도 − 대출 수` |
| `place_hold` | MEMBER_NOT_FOUND → MEMBER_SUSPENDED → BOOK_NOT_FOUND → HOLD_NOT_ALLOWED → HOLD_DUPLICATE → HOLD_LIMIT | 대기열 끝과 member.holds에 추가, `queue_position = 추가 후 대기열 길이` |
| `waive_fee` | MEMBER_NOT_FOUND → NO_FEE | `waived_amount = fee 전액`, `fee = 0`, `remaining_fee = 0` |

### 오류 메시지 템플릿 (errors.py, 완성본)

| code | 메시지 |
|---|---|
| MEMBER_NOT_FOUND | `회원을 찾을 수 없습니다: {member_id}` |
| MEMBER_SUSPENDED | `이용이 정지된 회원입니다: {member_id}` |
| UNPAID_FEE | `미납 연체료가 있어 대출할 수 없습니다: {fee}원` |
| BOOK_NOT_FOUND | `도서를 찾을 수 없습니다: {book_id}` |
| LOAN_LIMIT | `대출 한도를 초과합니다: 현재 {current}권 + 요청 {requested}권 > 한도 {limit}권` |
| NOT_AVAILABLE | `대출 가능한 재고가 없습니다: {book_id}` |
| HOLD_NOT_ALLOWED | `대출 가능한 도서는 예약할 수 없습니다: {book_id}` |
| HOLD_DUPLICATE | `이미 예약한 도서입니다: {book_id}` |
| HOLD_LIMIT | `예약 한도를 초과합니다: 최대 {limit}권` |
| NO_FEE | `면제할 연체료가 없습니다: {member_id}` |

메시지는 반드시 `MESSAGES[code].format(...)`으로만 만든다.

## 3. Requirements

### store
- 세 메서드는 위 표의 순서로 검사하고, 해당 코드의 `LibraryError`를 raise한다. (T302–T310)
- **checkout은 원자적이다.** 검사를 모두 통과한 뒤에만 store를 바꾸고, 실패하면 아무것도 바꾸지 않는다. (T301, T305)
- LOAN_LIMIT은 `현재 대출 수 + 요청 수 > 한도`일 때 발생한다. (T304)
- HOLD_LIMIT은 회원의 예약이 **이미 MAX_HOLDS(3)권**일 때 발생한다. (T309)
- 반납 예정일은 `today + loan_days`이다. 기준일은 `DEFAULT_TODAY = 2026-11-03`. (T301)

### 도구 (T311–T313)
- 도구 4개를 `[get_member_status, checkout_books, place_hold, waive_fee]` 순서로 반환한다.
- `get_member_status(member_id: str)` → `MemberStatus.model_dump_json()`
- `checkout_books`, `place_hold`, `waive_fee`는 각각 args_schema로 `CheckoutRequest`, `HoldRequest`, `FeeWaiverRequest`를 쓰고, 결과 모델의 `model_dump_json()`을 반환한다.
- 도구를 직접 invoke할 때 잘못된 인자는 `ValidationError`로 raise된다.
- agent 안에서는 ToolNode가 이를 `status="error"` ToolMessage로 바꾸며, store는 바뀌지 않는다.
- 도구는 `LibraryError`와 `ValidationError`를 **잡지 않는다**.

### HITL (T321–T325)
- `make_hitl_middleware()`는 다음을 반환한다. interrupt mode는 기본값을 쓴다.
  ```python
  HumanInTheLoopMiddleware(interrupt_on={
      "waive_fee": {"allowed_decisions": ["approve", "edit", "reject"], "description": ...}
  })
  ```
- `build_circulation_agent`는 `build_rules_agent`와 같은 방식으로 만든다 (`name="circulation_agent"`, `CIRCULATION_PROMPT`). **middleware 목록 끝**에 `make_hitl_middleware()`를 더한다.
- `waive_fee`는 실행 전에 interrupt된다.
  - **approve**: 실행한다.
  - **reject**: 실행하지 않고, 거절 메시지를 담은 오류 ToolMessage를 남긴다.
  - **edit**: 수정된 인자로 실행한다.
- 다른 도구는 interrupt하지 않는다.
- `get_interrupts(result)`는 `result.get("__interrupt__", [])`를 반환한다.

## 4. interrupt 값과 resume 형식 (부록 A.2)

```python
result = agent.invoke({"messages": [...]}, config)
intr = result["__interrupt__"][0]
# intr.value == {
#   "action_requests": [{"name": "waive_fee", "args": {...}, "description": "..."}],
#   "review_configs":  [{"action_name": "waive_fee",
#                        "allowed_decisions": ["approve", "edit", "reject"]}]
# }

from langgraph.types import Command
agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config)
agent.invoke(Command(resume={"decisions": [{"type": "reject", "message": "증빙 미확인"}]}), config)
agent.invoke(Command(resume={"decisions": [{"type": "edit", "edited_action":
    {"name": "waive_fee", "args": {"member_id": "M-0008", "reason": "시스템 오류 확인"}}}]}), config)
```

resume에는 interrupt가 난 run과 **같은 config(같은 thread_id)**를 쓴다.

## 5. 테스트 목록

| Test | 내용 |
|---|---|
| T301 | checkout 성공 시 store 변경, due_date, remaining_quota |
| T302 | 정지 회원 (M-0004) |
| T303 | 미납 연체료 (M-0003 1500원, M-0008 800원) |
| T304 | 대출 한도 (일반 5, 신규 3) |
| T305 | 재고 없음 → 원자성 (store 그대로) |
| T306 | 없는 회원·도서 ID |
| T307 | 예약 대기열 순번과 중복 예약 |
| T308 | 대출 가능한 도서는 예약 불가 |
| T309 | 예약 한도 (M-0007은 이미 3권) |
| T310 | 연체료 면제 |
| T311 | circulation 도구 계약 (이름, 순서, 반환 형식) |
| T312 | 직접 invoke 시 ValidationError |
| T313 | agent 안에서는 ValidationError가 오류 ToolMessage가 됨 |
| T321 | waive_fee가 실행 전에 interrupt됨 |
| T322 | approve → 실행 |
| T323 | reject → 실행 안 함 |
| T324 | edit → 수정된 인자로 실행 |
| T325 | 다른 도구는 interrupt하지 않음 |

## 6. 시나리오별 회원 매핑

| 회원 | 쓰이는 시나리오 |
|---|---|
| M-0001 (일반, 깨끗) | 정상 대출·예약 |
| M-0002 (신규) | 신규 한도 3권 |
| M-0003 (fee 1500) | UNPAID_FEE, waive_fee 대상 |
| M-0004 (정지) | MEMBER_SUSPENDED |
| M-0005 (대출 4권) | LOAN_LIMIT (1권만 더 가능) |
| M-0006 (신규, 대출 2, 예약 B002) | 신규 한도, 대기열 |
| M-0007 (예약 3권) | HOLD_LIMIT |
| M-0008 (fee 800) | UNPAID_FEE, waive_fee 거절 시나리오 |

## 7. 구현 시 주의점

- 원자성: 검사 단계와 변경 단계를 완전히 분리한다. 검사 도중에는 store를 건드리지 않는다.
- BOOK_NOT_FOUND와 NOT_AVAILABLE은 **요청 순서대로** 확인해서 첫 번째 문제 도서를 보고한다.
- LOAN_LIMIT 검사는 BOOK_NOT_FOUND 다음, NOT_AVAILABLE 앞이다.
- HITL은 checkpointer가 있어야 interrupt/resume이 동작한다. 테스트는 `thread` fixture로 thread_id를 넘긴다.
