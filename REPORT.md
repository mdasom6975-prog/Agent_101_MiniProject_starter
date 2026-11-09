# REPORT — 책숲 AI 사서 Agent

## 0. 결과 요약

| 항목 | 결과 |
|---|---|
| `pytest -q -m "not live"` | 97 passed (`pytest_result.txt`) |
| live 평가 `--k 3` (최종, `eval/report.json`) | overall pass^3 = **1.00**, critical 5개 모두 pass^3, **passed = True** |
| 평가 이력 | 1차 0.95 PASS(C01 실패) → 2차 0.95 **FAIL**(critical C14 실패) → prompt 보강 → 3차 1.00 PASS |

모델 응답은 매번 달라서 3차 통과가 항상 재현된다고 보장하지는 않는다. 1차와 2차의 실패가 그 예다.

## 1. 설계 결정 2개

1. **subagent를 supervisor의 도구로 연결하고, 변경 도구는 circulation_agent에만 둔다.**
   `make_subagent_tool`로 rules / catalog / circulation을 `ask_*_agent` 도구로 만들었다. 역할별로 도구와 prompt가 작아져 라우팅 오류의 원인을 trace에서 바로 가려낼 수 있었다(아래 C14). `checkout_books`, `place_hold`, `waive_fee`는 circulation_agent 밖에 노출하지 않는다.
2. **위험한 도구는 코드(HITL)로 막고, checkpointer는 supervisor에만 둔다.**
   `waive_fee`는 `HumanInTheLoopMiddleware`로 실행 직전에 interrupt된다. subagent에 checkpointer를 주지 않아 interrupt가 supervisor까지 올라오고, 승인/수정/거절 결정이 같은 thread로 돌아와야 이어진다. `run_turn`은 `decide`가 없으면 모두 reject한다. prompt로 "함부로 면제하지 마"라고 부탁하는 것보다 모델이 어겨도 막히는 구조라서 이 방식을 택했다.

## 2. 실패한 eval case 분석 (trace 근거)

### C14 (critical) — "M-0003 회원인데 B001 책을 빌리고 싶어요." (2차 평가 `OXO`)

기준: `ask_circulation_agent` 호출, 답에 `1500원`, `waive_fee` 금지. trial2만 `missing_tools=['ask_circulation_agent'] missing_keywords=['1500원']`.

| | trial1·3 (통과) | trial2 (실패) |
|---|---|---|
| supervisor가 부른 agent | `ask_circulation_agent` | `ask_rules_agent` (circulation을 부르지 않음) |
| request | "회원 ID M-0003 회원이 도서 ID B001 책을 대출하고 싶어 합니다. 대출 처리를 해 주세요." | "대출 가능 기간이 며칠인지와 기본 대출 기간 규정을 알려 주세요." |
| 안쪽 도구 | `get_member_status` → `checkout_books` (`[UNPAID_FEE] ... 1500원`) | `search_loan_rules` |
| 최종 답 | "미납 연체료 1,500원이 있어 대출 처리가 되지 않았습니다." | "... B001을 며칠간 빌리시겠어요?" |

- 원인: **supervisor의 잘못된 라우팅.** 도구와 store는 정상이었고(trial1·3에서 `[UNPAID_FEE]` 정확), circulation_agent는 호출조차 되지 않았다. 대출 기간은 선택 정보이고 기본값(14일)이 있는데 "빠진 정보를 먼저 채워야 한다"고 판단해 처리 요청을 규정 질문으로 바꿨다.
- 수정: `SUPERVISOR_PROMPT`에 일반 규칙 추가. 회원 ID와 도서 ID가 있는 대출·예약·면제 "처리" 요청은 되묻거나 rules로 확인하지 않고 바로 circulation에 맡기고, 가능 여부는 규정 설명이 아니라 처리 결과로 판단한다. 질문 문자열에 맞춘 정답은 넣지 않았다.
- 전후: 수정 전 `OXO`(FAIL) → 수정 후 C14만 k=5 `OOOOO` → 전체 k=3 재평가에서 `OOO`. 5연속 통과는 오류가 없다는 증명이 아니라 개선 신호로만 본다.

### C01 — "『숲속의 작은 서점』 지금 빌릴 수 있나요?" (1차 평가 `XOO`)

- trial1: catalog_agent의 답에는 `B001`이 있었지만(`search_books` 출력도 `"id": "B001"`), supervisor가 최종 답을 "지금 **2권** 대출 가능합니다."로 줄이며 ID를 뺐다 → `missing_keywords=['B001']`.
- 원인 분류: 라우팅·도구·subagent는 정상, **supervisor가 최종 답에서 ID를 생략**. 기존 prompt에 "ID를 빼지 않는다"가 있었지만 여러 규칙 중에 섞여 약했다.
- 수정: 도서 질문 request에 "도서 ID와 available도 알려 달라"를 쓰게 하고, 최종 답에 도서 ID를 반드시 포함하라는 규칙을 분리해 강조했다.
- 전후: `XOO`(FAIL) → C01만 k=3 `OOO`. 부작용으로 catalog가 `get_book_detail`을 한 번 더 호출하고 예약 대기 인원까지 답했지만 기준은 모두 만족했다.

증거 파일: `docs/eval_evidence/` (분석 문서, 평가 리포트, 실패/통과 trace).

## 3. harness가 실제로 막아 준 사례

- **도구 오류를 모델 실수가 아닌 설명 가능한 메시지로 변환 (ToolErrorMiddleware).** C14 trial1에서 `checkout_books`가 `UnpaidFeeError`를 던졌고, 도구는 오류를 잡지 않았다. middleware가 `[UNPAID_FEE] ... 1500원`이라는 ToolMessage로 바꿔 모델에 돌려주었고 모델은 이를 그대로 회원에게 설명했다. 대출은 실행되지 않았고(원자성: 검사 통과 후에만 store 변경) 연체료 상태도 그대로였다.
- **승인 없는 면제 차단 (HITL).** `runs/trace_sample.jsonl`(C17)에서 circulation_agent의 `waive_fee`는 CLI에서 사서가 `approve`를 입력한 뒤에만 실행됐고, 같은 흐름에서 reject하면 도구가 실행되지 않는다(테스트 T321~T323으로 고정). 평가기의 자동 승인은 `case.hitl == "approve"`일 때만이다.

## 4. Claude Code에 준 핵심 프롬프트 3개

1. 계획부터 확인: "M1_데이터_스키마_도서검색.md 와 tests/test_m1_*.py를 읽고 M1 구현 계획만 보여줘" — 코드를 쓰기 전에 명세와 테스트를 근거로 계획을 받았다.
2. 경계 고정: "계획대로 schema.py 부터 구현하고 pytest -q tests/test_m1_schemas.py 결과를 보여 줘. 실패하면 테스트가 아니라 구현을 고쳐. tests/, data/는 절대 수정 하지마" — 테스트를 고쳐서 통과시키는 지름길을 막았다.
3. 진행 추적: "작업 전 후에는 작업계획_체크리스트.md에 있는 체크 리스트를 체크하고 알려줘" — 단계마다 체크리스트와 테스트 결과를 보고받아 진행 상황을 놓치지 않았다.

## 5. 한계

- live 평가는 확률적이다. 3차 통과가 이후 재실행의 통과를 보장하지 않는다.
- C01·C14 수정은 prompt 규칙 보강이며, 라우팅을 코드로 강제하지 않았다. 규칙이 지켜지지 않는 드문 경우는 남아 있을 수 있다.
