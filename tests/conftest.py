from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _build(factory):
    """미구현 함수가 fixture에서 불리면 traceback 대신 한 줄 메시지로 알려 준다."""
    try:
        return factory()
    except NotImplementedError as e:
        pytest.fail(f"fixture 준비 실패 - 미구현: {e}", pytrace=False)


@pytest.fixture
def store():
    from library_agent.store import load_store

    return _build(load_store)


@pytest.fixture
def retrievers():
    from library_agent.rag import build_retrievers

    return _build(build_retrievers)


@pytest.fixture
def log_path(tmp_path):
    return tmp_path / "trace.jsonl"


@pytest.fixture
def thread():
    import uuid

    return {"configurable": {"thread_id": uuid.uuid4().hex}}

