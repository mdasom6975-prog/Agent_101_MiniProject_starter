"""강연 시연용 웹 서버 (표준 라이브러리만 사용).

실행 (프로젝트 루트에서):
    export OPENAI_API_KEY=...        # 환경변수로만 설정한다. 화면·로그·응답에 key는 나오지 않는다.
    python demo/server.py            # http://127.0.0.1:8000

library_agent 패키지는 수정하지 않고 build_agent()를 그대로 사용한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from langgraph.types import Command  # noqa: E402

from library_agent.app import answer_text, build_agent, get_interrupts  # noqa: E402
from library_agent.middleware import read_trace  # noqa: E402
from library_agent.store import LibraryStore, load_store  # noqa: E402

WATCH_MEMBERS = ["M-0001", "M-0003", "M-0008"]  # 화면 오른쪽 아래 카드에 보여 줄 회원
AgentFactory = Callable[[LibraryStore, Path], Any]


def real_agent_factory(store: LibraryStore, log_path: Path) -> Any:
    """실제 모델(gpt-6-luna)로 agent를 만든다. 시연마다 새 store와 새 checkpointer를 쓴다."""
    return build_agent(store=store, log_path=log_path)


class DemoSession:
    """시연 한 판의 상태: store, agent, 현재 thread, 대기 중인 승인 요청."""

    def __init__(self, agent_factory: AgentFactory, log_path: Path | str) -> None:
        self.agent_factory = agent_factory
        self.log_path = Path(log_path)
        self.lock = threading.Lock()  # agent.invoke는 한 번에 하나만
        self.pending: list[dict[str, Any]] = []
        self.reset()

    def reset(self) -> None:
        """store·agent·대화·trace를 모두 처음 상태로 되돌린다."""
        with self.lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.unlink(missing_ok=True)
            self.store = load_store()
            self.agent = self.agent_factory(self.store, self.log_path)
            self.thread_id = uuid.uuid4().hex
            self.pending = []

    def _config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    def _pack(self, result: Any) -> dict[str, Any]:
        self.pending = [
            {"name": req["name"], "args": req["args"], "description": req.get("description", "")}
            for intr in get_interrupts(result)
            for req in intr.value["action_requests"]
        ]
        return {"answer": None if self.pending else answer_text(result), "pending": self.pending}

    def ask(self, question: str, new_thread: bool = False) -> dict[str, Any]:
        with self.lock:
            if new_thread:
                self.thread_id = uuid.uuid4().hex  # 대화 맥락만 새로 시작 (store는 유지)
                self.pending = []
            result = self.agent.invoke({"messages": [{"role": "user", "content": question}]}, self._config())
            return self._pack(result)

    def resume(self, decision: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if not self.pending:
                raise ValueError("대기 중인 승인 요청이 없습니다")
            kind = decision.get("type")
            if kind not in ("approve", "edit", "reject"):
                raise ValueError("decision.type은 approve, edit, reject 중 하나여야 합니다")
            decisions = []
            for req in self.pending:
                if kind == "edit":
                    args = decision.get("args")
                    if not isinstance(args, dict):
                        raise ValueError("edit에는 수정된 args(JSON 객체)가 필요합니다")
                    decisions.append({"type": "edit", "edited_action": {"name": req["name"], "args": args}})
                elif kind == "reject":
                    decisions.append({"type": "reject", "message": str(decision.get("message") or "사서가 거절했습니다.")})
                else:
                    decisions.append({"type": "approve"})
            result = self.agent.invoke(Command(resume={"decisions": decisions}), self._config())
            return self._pack(result)

    def trace(self, since: int = 0) -> dict[str, Any]:
        rows = read_trace(self.log_path)
        return {"total": len(rows), "rows": rows[since:]}

    def state(self) -> dict[str, Any]:
        members = [self.store.member_status(m).model_dump() for m in WATCH_MEMBERS]
        return {"members": members, "today": self.store.today.isoformat()}


def make_handler(session: DemoSession) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # 접근 로그는 조용히
            pass

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: Any, code: int = 200) -> None:
            self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
            return data if isinstance(data, dict) else {}

        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                self._send(200, (DEMO_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/scenarios":
                self._send(200, (DEMO_DIR / "scenarios.json").read_bytes(), "application/json; charset=utf-8")
            elif url.path == "/api/trace":
                since = int(parse_qs(url.query).get("since", ["0"])[0])
                self._json(session.trace(since))
            elif url.path == "/api/state":
                self._json(session.state())
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            try:
                body = self._body()
                if url.path == "/api/ask":
                    question = str(body.get("question") or "").strip()
                    if not question:
                        return self._json({"error": "질문이 비어 있습니다"}, 400)
                    self._json(session.ask(question, bool(body.get("new_thread"))))
                elif url.path == "/api/resume":
                    self._json(session.resume(body.get("decision") or {}))
                elif url.path == "/api/reset":
                    session.reset()
                    self._json({"ok": True})
                else:
                    self._json({"error": "not found"}, 404)
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                # 오류 원문에는 인증 정보 일부가 섞일 수 있어 화면·콘솔에는 종류만 알린다.
                name = type(exc).__name__
                print(f"[demo] 요청 처리 중 오류: {name}", file=sys.stderr)
                self._json({"error": f"처리 중 오류가 발생했습니다 ({name}). 서버 콘솔을 확인하세요."}, 500)

    return Handler


def make_server(session: DemoSession, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(session))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="책숲 AI 사서 시연 서버")
    parser.add_argument("--host", default="127.0.0.1", help="기본은 이 컴퓨터에서만 접속 (127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log", default=str(ROOT / "runs" / "demo" / "trace.jsonl"))
    args = parser.parse_args(argv)

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY 환경변수가 없습니다. 터미널에서 설정한 뒤 다시 실행하세요.", file=sys.stderr)
        print("  read -rs OPENAI_API_KEY && export OPENAI_API_KEY", file=sys.stderr)
        return 1

    session = DemoSession(real_agent_factory, args.log)
    server = make_server(session, args.host, args.port)
    print(f"책숲 AI 사서 시연 서버: http://{args.host}:{args.port}  (종료: Ctrl+C)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
