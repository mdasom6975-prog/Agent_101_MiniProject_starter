# AGENTS.md — 책숲 AI 사서 Agent

> 이 파일은 coding agent(Claude Code, Codex, OpenCode 등)가 매 세션 처음 읽는 프로젝트 규칙이다.
> Claude Code를 쓰면 `CLAUDE.md`에 `@AGENTS.md` 한 줄을 넣어 이 파일을 불러온다.
> 모든 TODO를 지우고 자기 프로젝트에 맞게 채운다. (테스트 T501이 검사한다)

## 프로젝트 개요
- TODO: 무엇을 만드는지 2~3줄 (supervisor + subagent 3개, 명세서 경로)
- TODO: 사용 버전·모델 (Python, langchain, langgraph, gpt-6-luna의 제약)

## 명령어
- TODO: 설치 명령
- TODO: 전체 테스트, 마일스톤별 테스트(`pytest -q -m m1`), 테스트 하나만 돌리는 법
- TODO: CLI 실행, live 평가 실행

## 코드 규칙
- TODO: 이름·시그니처는 명세서를 따른다
- TODO: 오류 메시지·도구 오류 처리 원칙
- TODO: 모델 주입 원칙 (import 시점에 모델 생성 금지)

## 금지 사항
- TODO: 수정하면 안 되는 폴더/파일
- TODO: HITL 우회 금지 등 안전 규칙

## 완료 조건
- TODO: 어떤 명령이 통과하면 "끝"인지
