# M4. Harness · Supervisor · 평가기 (20점)

> 출처: 명세서 6장 · 테스트 `tests/test_m4_harness.py`, `tests/test_m4_supervisor.py`, `tests/test_m4_evaluation.py`
> 완료 조건: `pytest -q -m m4` → **23 passed** (T401–T409, T411–T417, T421–T427)
> M4까지 마치면 `pytest -q -m "not live"`에서 **T501(AGENTS.md)만** 남는다.
> 관련 실습: tool error wrapper, ModelCallLimit, custom middleware, supervisor(agents as tools), memory

## 1. 구현 대상

```python
# middleware.py  (HITL_TOOLS, OUTPUT_PREVIEW_CHARS = 300은 stub에 있다)
def tool_error_handler(exc, request) -> str
def make_tool_error_middleware() -> AgentMiddleware
class LoopGuardMiddleware(AgentMiddleware):
    def __init__(self, max_repeats=2)
    def count_repeats(self, messages, name, args) -> int
    def wrap_tool_call(self, request, handler)
class JsonlTraceMiddleware(AgentMiddleware):
    def __init__(self, log_path, agent_name)
    def wrap_tool_call(self, request, handler)
def read_trace(log_path) -> list[dict]
def default_middleware(agent_name, *, log_path=None, model_call_limit=8, max_repeats=2) -> list[AgentMiddleware]

# agents.py
def build_catalog_agent(model, store, *, log_path=None, model_call_limit=6, checkpointer=None)
def make_subagent_tool(agent, name, description) -> BaseTool
def build_supervisor(model, subagents, *, log_path=None, model_call_limit=8, checkpointer=None)

# app.py
def build_agent(model=None, *, models=None, store=None, retrievers=None, checkpointer=None, log_path=None)
def answer_text(result) -> str
def run_turn(agent, question, *, thread_id=None, decide=None, max_resumes=3) -> dict
def main(argv=None) -> int

# evaluation.py: stub의 함수 7개와 CaseResult·EvalReport property 전부 (dataclass 필드는 고정)
```

## 2. Middleware

### 순서

| 순서 | middleware | 역할 |
|---|---|---|
| 1 | `JsonlTraceMiddleware(log_path, agent_name)` — **log_path가 있을 때만** | 도구 호출 1건을 JSON 한 줄로 기록 |
| 2 | `ModelCallLimitMiddleware(run_limit=model_call_limit, exit_behavior="end")` | 한 run의 모델 호출 상한 (supervisor 8, subagent 6) |
| 3 | `LoopGuardMiddleware(max_repeats)` | 같은 (도구, 인자) 반복 차단 |
| 4 | `ToolErrorMiddleware(on_error=tool_error_handler)` | 도메인 오류를 ToolMessage로 변환 |
| 5 | `HumanInTheLoopMiddleware` — **circulation_agent만** | waive_fee 실행 전 승인 |

### Requirements
- `default_middleware`는 위 1–4를 이 순서로 담은 리스트를 반환한다. log_path가 없으면 1을 뺀다. (T407)
- `tool_error_handler` (T401)
  - `LibraryError`면 `[{code}] {message}`
  - 그 밖의 예외면 `[INTERNAL] {tool_name} 실행 중 예기치 못한 오류가 발생했습니다 ({ExcType})`
  - tool_name은 `request.tool_call["name"]`
- `make_tool_error_middleware`는 `ToolErrorMiddleware(on_error=tool_error_handler)` 인스턴스를 반환한다. 도메인 오류는 `status="error"` ToolMessage가 되고 run은 계속된다. wrapper가 없는 agent에서는 예외가 전파된다. (T402, T403, T407)
- 모델 호출이 상한에 닿으면 run이 끝나고, 마지막 AIMessage에 `Model call limits exceeded`가 들어간다. (T404)

### LoopGuard (T405, T406)
- `count_repeats`는 **마지막 HumanMessage 이후** AIMessage들의 tool_calls 중 (name, args)가 같은 개수를 센다. **현재 호출 포함**.
- `max_repeats < 1`이면 `ValueError`.
- 그 수가 max_repeats보다 크면 도구를 실행하지 않고 `ToolMessage(status="error")`를 반환한다. 내용:
  `[LOOP_GUARD] 같은 인자로 {name}을(를) {n}번째 호출하여 차단했습니다. 이미 받은 결과로 답하세요.`
- 기본 max_repeats=2이므로 **세 번째** 같은 호출이 차단된다.

### JsonlTrace (T408, T409, T415)
- 도구 실행이 끝난 뒤 한 줄을 append한다.
- 필드: `ts`(UTC ISO-8601), `agent`, `tool`, `args`, `tool_call_id`, `status`(success | error | exception | command), `output`(앞 300자), `duration_ms`
- interrupt(`GraphBubbleUp`)는 기록하지 않고 다시 raise한다.
- 다른 예외는 `status="exception"`으로 기록하고 다시 raise한다.
- 한 graph에 여러 인스턴스가 붙으므로 **`name` property를 agent별로 다르게** 한다. (같으면 create_agent에서 middleware 이름 중복 오류)
- `read_trace`는 JSONL 파일을 dict 목록으로 읽는다. 파일이 없으면 `[]`.

## 3. Supervisor와 app.py

### agents.py
- `build_catalog_agent`: `name="catalog_agent"`, `CATALOG_PROMPT`, `make_catalog_tools(store)`, `default_middleware`로 만든다. (T404, T405, T408)
- `make_subagent_tool`은 `request: str` 인자 하나를 받는 도구를 만든다. `agent.invoke({"messages": [{"role": "user", "content": request}]})`의 마지막 메시지 `.text`를 그대로 반환한다. **config는 넘기지 않는다.** (T412)
- `build_supervisor`의 subagents key는 `catalog`, `rules`, `circulation`이다. 도구는 `SUBAGENT_TOOL_SPECS`의 이름·설명으로 만들고, 순서는 `ask_catalog_agent`, `ask_rules_agent`, `ask_circulation_agent`다. `name="supervisor"`. (T411, T413)

### build_agent (T411, T415)
- role별 모델: `models[role]` → `model` → `default_model()` 순으로 정한다.
- `models`에 `ROLES` 밖의 key가 있으면 `ValueError`.
- 모든 role이 models에 있으면 `default_model()`을 부르지 않는다.
- store·retrievers가 None이면 `load_store()`·`build_retrievers()`로 만든다.
- checkpointer가 None이면 **supervisor에만** `InMemorySaver()`를 주고, subagent에는 checkpointer를 주지 않는다.
- log_path는 모든 agent에 전달한다.
- `ROLES = ("supervisor", "catalog", "rules", "circulation")`

### trace와 HITL 전파 (T412–T415)
- trace 순서: subagent 도구 줄이 그 subagent를 부른 supervisor 줄보다 **먼저**다.
- 범위 밖 질문에서 supervisor가 도구를 부르지 않으면 trace는 비어 있다.
- subagent 안의 waive_fee interrupt는 supervisor의 invoke 결과까지 올라온다. 같은 thread_id로 resume하면 실행된다.

### answer_text · run_turn · main (T416, T417)
- `answer_text(result)` = `result["messages"][-1].text`
- `run_turn`은 thread_id(없으면 새 uuid)로 질문을 invoke한다. interrupt가 있으면 `action_requests`마다 `decide(req)`로 decision을 만들어 resume한다. 최대 `max_resumes`번 반복하며, **decide가 None이면 모두 reject**한다.
- `main(argv)` 인자
  - `-q/--question`: 한 번 묻고 답을 출력한 뒤 0 반환
  - `--thread`: 기본 `"cli"`
  - `--log`: 기본 `"runs/trace.jsonl"`
  - 인자가 없으면 대화 모드이고, interrupt는 터미널에서 approve/edit/reject를 고른다.
  - `build_agent`는 **키워드 인자로만** 호출한다.
  - 실행: `python -m library_agent.app`

## 4. 평가기 (evaluation.py)

### 고정 dataclass (수정 금지)
```python
EvalCase(id, question, expected_tools, forbidden_tools=[], must_contain=[],
         hitl="reject", category="general", critical=False)
TrialResult(passed, tools_called, answer, missing_tools=[], forbidden_used=[],
            missing_keywords=[], error=None)
CaseResult(case_id, trials, critical=False)      # property: pass_k, pass_rate
EvalReport(k, cases)                             # property: overall_pass_k, critical_ok, passed / to_dict()
```
상수: `PASS_THRESHOLD = 0.8`, `DEFAULT_K = 3`, `AUTO_REJECT_MESSAGE = "평가용 자동 거절"`

### Requirements
- `load_cases`: JSON 배열을 EvalCase 목록으로 읽는다. (T421)
- `normalize`: 공백과 쉼표를 지우고 소문자화한다. `normalize("3,000 원") == "3000원"` (T422)
- `pass_hat_k(results)`: 목록이 비어 있지 않고 모두 True일 때만 True. (T423)
- `score_trial` (T422)
  - `missing_tools`: expected 중 안 불린 것 (순서 유지)
  - `forbidden_used`: forbidden 중 불린 것
  - `missing_keywords`: must_contain 중 normalize 후 답에 없는 것
  - 셋 다 비면 passed
- `run_trial` (T424–T426)
  - log_path를 지우고 `agent_factory(log_path)`로 새 agent를 만든다.
  - 새 thread_id로 invoke한다.
  - interrupt는 `case.hitl`에 따라 모두 approve 또는 `reject(message=AUTO_REJECT_MESSAGE)`로 최대 3번 resume한다.
  - `tools_called`는 trace의 tool 목록이다.
  - 예외는 `passed=False`와 `error`에 기록한다.
- `run_case` (T424, T425)
  - trial i(1부터)의 로그 경로는 `workdir / f"{case.id}_trial{i}.jsonl"`
  - `pass_k = pass_hat_k(trial 결과)`, `pass_rate = 통과 trial 비율`
- `EvalReport` (T427)
  - `overall_pass_k` = pass_k인 case 비율
  - `critical_ok` = critical case가 모두 pass_k
  - `passed` = `overall_pass_k ≥ PASS_THRESHOLD` **그리고** `critical_ok`
  - `to_dict()`의 key는 `{k, overall_pass_k, critical_ok, passed, cases}`
- `run_eval`: case마다 run_case를 돌리고, 끝날 때마다 `on_case(case_result)`를 부른다. (T427)

## 5. 테스트 목록

| Test | 내용 |
|---|---|
| T401 | tool_error_handler 문자열 형식 |
| T402 | wrapper가 도메인 오류를 ToolMessage로 변환 |
| T403 | wrapper가 없으면 도메인 오류가 전파 |
| T404 | 모델 호출 상한에 닿으면 run 종료 |
| T405 | LoopGuard가 세 번째 같은 호출을 차단 |
| T406 | LoopGuard는 마지막 HumanMessage 이후만 셈 |
| T407 | default_middleware 구성과 순서 |
| T408 | JsonlTrace가 도구 호출마다 기록 |
| T409 | read_trace: 파일이 없으면 [] |
| T411 | supervisor 도구 목록과 build_agent factory 계약 |
| T412 | rules 질문 라우팅 |
| T413 | catalog → rules 순서 라우팅 |
| T414 | 범위 밖 질문은 어떤 agent도 부르지 않음 |
| T415 | HITL이 supervisor까지 올라오고 approve로 실행 |
| T416 | run_turn으로 reject |
| T417 | CLI one-shot (`-q`) |
| T421 | eval_cases.json 형식 |
| T422 | score_trial, normalize |
| T423 | pass_hat_k |
| T424 | run_case pass^3 |
| T425 | trial 하나만 실패해도 pass^3 실패 |
| T426 | trial 안의 HITL 정책 (approve/reject) |
| T427 | 리포트 기준(threshold, critical) |

## 6. 구현 시 주의점 (부록 A.3)

| 증상 | 원인과 해결 |
|---|---|
| resume 후 처음부터 다시 실행된다 | 다른 thread_id로 resume했다. 같은 config를 넘긴다. |
| interrupt가 supervisor까지 안 올라온다 | subagent에 checkpointer를 따로 줬거나, supervisor에 checkpointer가 없다. |
| create_agent에서 middleware 이름 중복 오류 | 같은 이름의 middleware가 두 번 붙었다. `JsonlTraceMiddleware.name`을 agent별로 다르게 한다. |

- M2에서 최소 구현한 middleware 3개를 여기서 완성한다. M2·M3 테스트가 계속 통과하는지 회귀 확인한다.
- `make_subagent_tool`에서 config를 넘기면 subagent가 supervisor의 checkpointer 상태와 엉킬 수 있다. 명세대로 넘기지 않는다.
