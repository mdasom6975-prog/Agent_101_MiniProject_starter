# 책숲 AI 사서 Agent

작은 동네 도서관 "책숲"의 회원 질문에 답하는 multi-agent 시스템입니다.
supervisor가 질문을 아래 3개 subagent 중 알맞은 곳에 보냅니다.

| agent | 역할 |
|---|---|
| rules | 도서관 규정 질문 (BM25 기반 RAG) |
| catalog | 도서 검색, 재고 확인 |
| circulation | 대출·예약·연체료 면제 처리 (면제는 사서 승인 필요, HITL) |

세부 규칙은 [AGENTS.md](AGENTS.md), 명세·진행 상황은 `docs/`를 보세요.

## 1. 준비 (처음 한 번)

```bash
cd /Users/fastcampus_m/Desktop/prj/Agent_101_MiniProject_starter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 터미널을 열 때마다 하는 일

```bash
cd /Users/fastcampus_m/Desktop/prj/Agent_101_MiniProject_starter
source .venv/bin/activate
```

실제 모델을 쓰는 명령(평가, 데모, CLI)을 실행하기 전에는 API key를 환경변수로 설정합니다.
명령 뒤에 key를 붙이지 않고, 실행 후 나오는 입력 대기 상태에서 key를 붙여넣고 Enter를 누릅니다(입력은 화면에 보이지 않습니다).

```bash
read -rs OPENAI_API_KEY && export OPENAI_API_KEY
```

- key는 코드, 파일, 커밋에 넣지 않습니다. 터미널을 닫으면 사라지므로 새 터미널마다 다시 설정합니다.
- 아래 "테스트"는 fake 모델을 쓰므로 key가 필요 없습니다.

## 3. 테스트 (API key 불필요)

```bash
pytest -q -m "not live"
```

목표는 `97 passed`입니다. 마일스톤별로는 `pytest -q -m m1` (m2~m5도 동일)입니다.

## 4. CLI로 질문하기

```bash
python -m library_agent.app -q "신규 회원은 몇 권까지 빌릴 수 있나요?"
```

`-q` 없이 실행하면 대화 모드입니다. 연체료 면제가 나오면 터미널에서 승인/거절을 묻습니다.

## 5. 평가 (실제 모델, key 필요)

20개 질문을 3번씩 돌려 모두 통과해야 통과로 보는 pass^3 평가입니다.

```bash
python eval/run_eval.py --k 3 --out eval/report.json
```

- 통과 기준: overall pass^3 ≥ 0.8 이고, critical case(C09, C14, C17, C18, C19)가 모두 pass^3
- 일부 case만: `python eval/run_eval.py --only C12,C17 --k 1`
- 실행 기록(trace)은 `runs/eval/*.jsonl`에 쌓입니다.

## 6. 시연 웹 화면

```bash
python demo/server.py
```

브라우저에서 http://127.0.0.1:8000 을 엽니다. 다른 포트는 `--port 8001`처럼 지정합니다.

- 왼쪽 시나리오 8개, 가운데 대화, 오른쪽에 도구 호출 추적과 회원 카드가 보입니다.
- `waive_fee`가 실행 직전에 멈추면 승인 창이 뜹니다(승인 / 수정 후 실행 / 거절).
- `전체 초기화` 버튼으로 연체료·재고·대화를 처음 상태로 되돌립니다.
- 서버는 이 컴퓨터(127.0.0.1)에서만 접속됩니다. 시연 순서와 멘트는 [docs/시연_스크립트.md](docs/시연_스크립트.md)를 보세요.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `library_agent/` | 구현 (schemas, store, rag, tools, middleware, agents, app, evaluation) |
| `data/` | 규정·도서·회원 데이터 (수정 금지) |
| `tests/` | 오프라인 테스트 (수정 금지) |
| `eval/` | 평가 case와 실행 스크립트 |
| `demo/` | 시연 서버와 화면 |
| `docs/` | 명세 정리, 체크리스트, 테스트 결과서, 평가 증거 |
