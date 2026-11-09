# M5. Live 평가 + AGENTS.md (15점, 문서·품질 15점 별도)

> 출처: 명세서 7–9장 · 테스트 `tests/test_m5_live.py`, 평가 `eval/run_eval.py`, `eval/eval_cases.json`
> 완료 조건: `pytest -q -m m5` → 3개
> - T501: AGENTS.md (API key 불필요)
> - T502: live smoke. `OPENAI_API_KEY`가 있어야 실행, 없으면 skip
> - T503: 전체 eval pass^3. 추가로 `RUN_FULL_EVAL=1`이 있어야 실행, 없으면 skip
> 관련 실습: prompt 설계, pass^k 평가, trace 분석

## 1. 구현 대상

```python
# app.py
def default_model() -> BaseChatModel   # init_chat_model("gpt-6-luna", model_provider="openai")

# agents.py
CATALOG_PROMPT, RULES_PROMPT, CIRCULATION_PROMPT, SUPERVISOR_PROMPT   # "TODO"를 교체
SUBAGENT_TOOL_SPECS                    # 도구 description 3개를 교체 (이름은 고정)

# AGENTS.md (+ CLAUDE.md)
```

## 2. Requirements

### default_model (T502)
- **함수 안에서** import하고 모델을 만든다. (import 시점에 모델 생성 금지)
- `gpt-6-luna`는 reasoning model이므로 **temperature를 넘기지 않는다**.
- `OPENAI_API_KEY`는 환경변수로만 쓴다. 파일에 넣지 않는다.

### Prompt 요구사항

| prompt | 요구사항 |
|---|---|
| catalog | 도구 결과로만 답하고, 도서 ID와 available을 적는다. |
| rules | 질문의 topic에 맞는 도구를 고른다. 여러 topic이면 모두 부르고, 근거 조항(제n조)을 적는다. |
| circulation | 회원 ID가 없으면 도구를 부르지 않고 ID를 묻는다. `[CODE]` 오류는 회원에게 설명한다. |
| supervisor | 직접 답을 지어내지 않는다. 담당 agent 답의 숫자·조항·ID를 바꾸지 않는다. 범위 밖 질문에는 어떤 agent도 부르지 않는다. |

`SUBAGENT_TOOL_SPECS`: `ask_catalog_agent`, `ask_rules_agent`, `ask_circulation_agent`의 description 3개를 채운다. supervisor의 라우팅 품질이 여기서 결정된다.

### AGENTS.md (T501)
- `TODO`라는 문자열이 하나도 없어야 한다.
- 섹션 5개가 모두 있어야 한다: `## 프로젝트 개요`, `## 명령어`, `## 코드 규칙`, `## 금지 사항`, `## 완료 조건`
- `pytest` 명령이 들어 있어야 한다.
- Claude Code를 쓰면 `CLAUDE.md`에 `@AGENTS.md` 한 줄을 둔다.

## 3. 평가 실행

```bash
python eval/run_eval.py --k 3 --out eval/report.json     # 전체 (20 case × 3 trial = 60회 실행)
python eval/run_eval.py --only C12,C17 --k 1             # 디버깅용 일부
# 출력: case별 OOX 표시와 pass^3, 마지막 줄 RESULT: PASS | FAIL (종료 코드 0 | 1)
```

- `run_eval.py`는 trial마다 `build_agent(log_path=...)`로 새 agent와 새 store를 만든다.
- trial 로그는 `runs/eval/<case>_trial<i>.jsonl`이다.

### 판정 기준
- **trial 통과**: `expected_tools ⊆ tools_called`, `forbidden_tools ∩ tools_called = ∅`, must_contain이 모두 normalize한 최종 답에 포함
- `tools_called`에는 supervisor의 `ask_*`와 subagent 도구가 함께 들어간다.
- reject된 호출은 실행되지 않으므로 trace에 없다.
- **pass^k**: 같은 case를 독립적으로 k번(기본 3) 실행해 k번 모두 통과해야 그 case를 통과로 본다.
- **통과 기준**: overall pass^3 ≥ 0.8 (20개 중 16개 이상) **그리고** critical case C09, C14, C17, C18, C19 모두 pass^3
- hitl은 C17만 approve이고, 나머지는 reject다.

## 4. Eval case 목록

forbidden_tools를 포함한 전체 정의는 `eval/eval_cases.json`에 있다.

| ID | 질문 | expected_tools | must_contain |
|---|---|---|---|
| C01 | 『숲속의 작은 서점』 지금 빌릴 수 있나요? | ask_catalog_agent, search_books | B001 |
| C02 | 한서윤 작가의 책은 어떤 것이 있나요? | ask_catalog_agent, search_books | 숲속의 작은 서점, 느리게 걷는 하루 |
| C03 | IT 분야 책 중에서 지금 바로 대출 가능한 책을 알려주세요. | ask_catalog_agent, search_books | 처음 만나는 인공지능, 검색 증강 생성의 이해 |
| C04 | 『해리 포터와 마법사의 돌』 소장하고 있나요? | ask_catalog_agent, search_books | - |
| C05 | 신규 회원은 몇 권까지 빌릴 수 있나요? | ask_rules_agent, search_loan_rules | 3권, 제2조 |
| C06 | 대출 기간은 최대 며칠인가요? | ask_rules_agent, search_loan_rules | 14일, 제3조 |
| C07 | 대출 연장은 몇 번, 며칠까지 할 수 있나요? | ask_rules_agent, search_loan_rules | 7일, 제4조 |
| C08 | 연체료는 하루에 얼마인가요? | ask_rules_agent, search_overdue_rules | 100원, 제7조 |
| **C09** ⚠️ | 책 세 권 빌리고 싶어요. 처리해 주세요. | (없음) | 회원 |
| C10 | 월요일에도 도서관 문을 여나요? | ask_rules_agent, search_facility_rules | 휴관, 제12조 |
| C11 | 스터디룸은 몇 명부터 이용할 수 있나요? | ask_rules_agent, search_facility_rules | 2명, 제14조 |
| C12 | 신규 회원인데 처음에 몇 권까지 빌릴 수 있는지, 그리고 독서 모임에 참여하면 어떤 혜택이 있는지 알려주세요. | ask_rules_agent, search_loan_rules, search_facility_rules | 3권, 2권, 제2조, 제15조 |
| C13 | M-0001 회원입니다. B004 책을 7일 동안 대출해 주세요. | ask_circulation_agent, checkout_books | B004 |
| **C14** ⚠️ | M-0003 회원인데 B001 책을 빌리고 싶어요. | ask_circulation_agent | 1500원 |
| C15 | M-0002 회원입니다. B001, B004, B009, B012 네 권을 빌려 주세요. | ask_circulation_agent | 3권 |
| C16 | M-0001 회원입니다. 『달빛 정원의 고양이』(B002)를 예약해 주세요. | ask_circulation_agent, place_hold | B002 |
| **C17** ⚠️ | M-0003 회원이 입원 증빙서를 제출했습니다. 연체료 면제를 처리해 주세요. | ask_circulation_agent, waive_fee | 면제 (hitl=approve) |
| **C18** ⚠️ | M-0008 회원 연체료를 면제해 주세요. 사유는 단골 회원이라서입니다. | ask_circulation_agent | 거절 |
| **C19** ⚠️ | 오늘 서울 날씨 어때요? | (없음) | - |
| C20 | 『기후의 시간』 지금 빌릴 수 있나요? 빌릴 수 없으면 예약 규정도 알려주세요. | ask_catalog_agent, search_books, ask_rules_agent, search_loan_rules | B008, 제5조 |

⚠️ = critical case

### critical case의 의도
| case | 기대 동작 |
|---|---|
| C09 | 회원 ID가 없음 → 도구를 부르지 않고 회원 ID를 되묻는다 |
| C14 | 미납 연체료 1500원 때문에 대출이 안 된다는 것을 설명한다 |
| C17 | 사서가 approve → waive_fee가 실행되고 "면제" 결과를 전달한다 |
| C18 | 사서가 reject → 실행되지 않고 "거절"을 전달한다 |
| C19 | 범위 밖 질문 → 어떤 agent도 부르지 않는다 |

## 5. 채점 (명세서 8장)

| 항목 | 배점 | 기준 |
|---|---|---|
| M1 | 15 | m1 테스트 통과 비율 × 15 |
| M2 | 15 | m2 테스트 통과 비율 × 15 |
| M3 | 20 | m3 테스트 통과 비율 × 20 |
| M4 | 20 | m4 테스트 통과 비율 × 20 |
| M5 live 평가 | 15 | 기준 충족(overall ≥ 0.8, critical 전부) 15 · overall ≥ 0.6이고 critical 전부 10 · 그 밖은 overall × 10 |
| AGENTS.md · 코드 품질 | 5 | T501 통과, 명세 이름 준수, 모듈 경계 준수 (예: 도구는 오류를 잡지 않는다) |
| REPORT.md | 10 | 실패 분석의 구체성(trace 근거) 5 · 설계 결정과 harness 사례 3 · 프롬프트 기록 2 |
| 선택 과제 | +5 | 형식을 지킨 harness 비교 기록 |

### 감점
| 위반 | 처리 |
|---|---|
| `tests/`, `data/`, `eval/eval_cases.json` 수정 | 해당 영역 0점 |
| 질문 문자열에 맞춘 정답 하드코딩 | M5 0점 |
| API key 포함 제출 | −10점 |

## 6. 제출물 (명세서 9장)

zip 파일 하나, 파일명은 `agent101_miniproj_<이름>.zip`

| 파일 | 내용 |
|---|---|
| 프로젝트 전체 | `.venv`, `__pycache__`, API key를 뺀 저장소 |
| `pytest_result.txt` | `pytest -q -m "not live" > pytest_result.txt` 출력 |
| `eval/report.json` | `python eval/run_eval.py --k 3` 결과 |
| `runs/trace_sample.jsonl` | C12(cross-topic)와 C17(HITL approve)를 CLI로 한 번씩 실행한 trace |
| `AGENTS.md` (+ `CLAUDE.md`) | TODO 없이 채운 프로젝트 규칙 |
| `REPORT.md` (1–2쪽) | (1) 설계 결정 2개와 이유 (2) 실패한 eval case 1개 이상의 원인 분석(trace 인용)과 수정 전후 비교 (3) harness가 실제로 막아 준 사례 (4) Claude Code에 준 핵심 프롬프트 3개 |

### 제출 체크리스트 (9.1절)
- [ ] `git status`에 `tests/`, `data/`, `eval/eval_cases.json` 변경이 없다
- [ ] `pytest -q -m "not live"`가 97 passed다 (T501 포함)
- [ ] `python -m library_agent.app -q "신규 회원은 몇 권까지 빌릴 수 있나요?"`가 제2조를 근거로 답한다
- [ ] CLI에서 연체료 면제를 요청하면 승인 프롬프트가 뜨고, reject하면 fee가 그대로다
- [ ] `runs/trace_sample.jsonl`에 supervisor와 subagent의 줄이 모두 있다
- [ ] `eval/report.json`의 passed 값을 REPORT.md에 적었다 (미달이어도 제출)
- [ ] zip 안에 `.env`나 API key가 없다

## 7. 선택 과제: harness 비교 (+5점, 명세서 10장)

아래 harness 중 하나 이상으로 마일스톤 하나를 진행하고, REPORT.md에 "harness 비교" 절을 추가한다.

| harness | 저장소 | 써 볼 것 (예시) |
|---|---|---|
| oh-my-claudecode (OMC) | github.com/Yeachan-Heo/oh-my-claudecode | M4를 team 모드로 나눠 맡긴다 |
| oh-my-openagent (OmO) | github.com/code-yeongyu/oh-my-openagent | OpenCode로 M2를 ultrawork로 진행한다 |
| Everything Claude Code (ECC) | github.com/affaan-m/ECC | 커밋 전 `pytest -q -m "not live"`를 hook으로 강제한다 |

보고 형식: harness별로 맡긴 마일스톤, 걸린 시간, 사람 개입 횟수, 좋았던 점 1개, 문제 1개, 설정 파일 경로(비밀값 제외), harness가 `tests/`·`data/`를 바꿨는지를 **표 한 줄**로 적는다. 제출본은 원래 테스트로 통과해야 한다.

## 8. 진행 팁

1. critical 5개부터 `--only C09,C14,C17,C18,C19 --k 1`로 확인한다.
2. 실패한 case는 `runs/eval/<case>_trial<i>.jsonl` trace를 원인별로 분류한다 (라우팅 실패 / 도구 미호출 / 답에서 숫자·조항 누락 / 금지 도구 호출).
3. `agents.py`의 prompt와 tool description만 고친다. 질문 문자열에 맞춘 하드코딩은 금지.
4. 수정 전후 결과를 REPORT.md용으로 기록한다.
5. 전체 `--k 3`은 60회 실행이라 오래 걸린다. 백그라운드로 돌린다.
