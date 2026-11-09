# AGENTS.md — 책숲 AI 사서 Agent

> coding agent(Claude Code, Codex, OpenCode 등)가 매 세션 처음 읽는 프로젝트 규칙이다.
> Claude Code는 `CLAUDE.md`의 `@AGENTS.md` 한 줄로 이 파일을 불러온다.

## 프로젝트 개요
- 작은 동네 도서관 "책숲"의 회원 질문에 답하는 multi-agent 시스템을 Python 패키지 `library_agent`로 구현한다. supervisor가 질문을 rules(규정 RAG), catalog(도서 검색), circulation(대출·예약·연체료 면제) subagent 3개 중 알맞은 곳에 보낸다. 연체료 면제(`waive_fee`)는 사서가 승인해야 실행된다(HITL).
- 명세서: `docs/Agent_101_MiniProject_책숲_AI사서_명세서.pdf`. 파트별 정리는 `docs/specs/M1~M5*.md`, 진행 상황은 `docs/작업계획_체크리스트.md`, `docs/테스트_결과서.md`.
- 버전: Python 3.11+ (`.venv`는 3.14), langchain 1.4.7, langgraph 1.2.19, pydantic 2.x. 모델은 `gpt-6-luna`(OpenAI reasoning model)이며 M5 live 평가에서만 쓰고, **temperature를 넘기지 않는다**. 테스트는 `tests/fakes.py`의 scripted fake model로 API key 없이 돈다.

## 명령어
- 설치: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- 전체 테스트(API key 불필요): `pytest -q -m "not live"` (목표: 97 passed)
- 마일스톤별 테스트: `pytest -q -m m1` (m2, m3, m4, m5도 같은 방식)
- 테스트 하나만: `pytest -q -k T305` 또는 `pytest -q tests/test_m1_schemas.py`
- CLI 한 번 묻기: `python -m library_agent.app -q "신규 회원은 몇 권까지 빌릴 수 있나요?"` (대화 모드는 인자 없이 실행)
- live 평가(OPENAI_API_KEY 필요, 환경변수로만 설정): `python eval/run_eval.py --k 3 --out eval/report.json`
- 일부 case만 디버깅: `python eval/run_eval.py --only C12,C17 --k 1`
- live 테스트 포함: `RUN_FULL_EVAL=1 pytest -q -m "m5"`

## 코드 규칙
- 모듈·클래스·함수 이름, 시그니처, 상수는 명세서와 stub에 적힌 그대로 둔다. 내부 helper 추가는 허용한다.
- 도메인 오류는 `errors.py`의 클래스를 raise하고, 메시지는 `MESSAGES[code].format(...)`로만 만든다.
- 도구는 `LibraryError`와 `ValidationError`를 잡지 않는다. ToolMessage 변환은 middleware(`ToolErrorMiddleware`)가 맡는다.
- 모델은 인자로 주입한다. import 시점에 모델을 만들지 않고, `default_model()`은 함수 안에서 import·생성한다.
- 기준일은 `store.DEFAULT_TODAY = date(2026, 11, 3)`이다. 반납 예정일은 `today + loan_days`다.
- 상태 변경(대출·예약·면제)은 `LibraryStore`의 메서드로만 하고, `checkout`은 검사를 모두 통과한 뒤에만 store를 바꾼다(원자성).
- middleware 순서는 JsonlTrace → ModelCallLimit → LoopGuard → ToolError이고 circulation_agent만 끝에 HITL을 붙인다. checkpointer는 supervisor에만 주고 subagent에는 주지 않는다.
- prompt에 특정 질문 문자열에 맞춘 정답을 넣지 않는다. 일반 규칙으로만 쓰고, 실패 분석은 `runs/eval/*.jsonl` trace를 근거로 한다.
- 테스트가 실패하면 테스트가 아니라 구현을 고친다.

## 금지 사항
- `tests/`, `data/`, `eval/eval_cases.json`은 수정하지 않는다(수정하면 해당 영역 0점).
- API key를 파일, 코드, 커밋, 제출물에 넣지 않는다(`.env`는 `.gitignore`에 있다). key는 환경변수로만 쓴다.
- HITL을 우회하지 않는다: `waive_fee`를 승인 없이 실행하지 않고, `run_turn`에서 `decide`가 없으면 모두 reject한다. 평가기의 자동 승인은 `case.hitl == "approve"`일 때만이다.
- 상태를 바꾸는 도구를 circulation_agent 밖에 노출하지 않는다.
- 사용자의 요청 없이 `git push`나 원격 변경을 하지 않는다.

## 완료 조건
- `pytest -q -m "not live"`가 **97 passed**다(T501 포함).
- `git status`에 `tests/`, `data/`, `eval/eval_cases.json` 변경이 없다.
- `python eval/run_eval.py --k 3`의 overall pass^3 ≥ 0.8이고 critical case(C09, C14, C17, C18, C19)가 모두 pass^3다. 미달이어도 `eval/report.json`과 `REPORT.md`는 제출한다.
- 제출물: `pytest_result.txt`, `eval/report.json`, `runs/trace_sample.jsonl`(C12, C17), `AGENTS.md`(+`CLAUDE.md`), `REPORT.md`. zip에는 `.venv`, `__pycache__`, API key를 넣지 않는다.
