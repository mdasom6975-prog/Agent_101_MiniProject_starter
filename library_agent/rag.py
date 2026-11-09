"""이용 규정 RAG (명세서 5.3절). TODO(M2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from .store import DEFAULT_DATA_DIR

DEFAULT_RULES_DIR = DEFAULT_DATA_DIR / "rules"
TOPIC_FILES: dict[str, str] = {
    "loan": "01_대출반납.md",
    "overdue": "02_연체이용제한.md",
    "facility": "03_시설프로그램.md",
}
NO_RESULT = "관련 조항을 찾지 못했습니다."


def load_rules(rules_dir: Path | str = DEFAULT_RULES_DIR, topic: str | None = None) -> list[Document]:
    raise NotImplementedError("M2: load_rules")


def tokenize(text: str) -> list[str]:
    raise NotImplementedError("M2: tokenize")


class BM25Retriever(BaseRetriever):
    """Okapi BM25 (k1=1.5, b=0.75). 명세서 5.3절의 수식과 tie-break 규칙을 따른다."""

    docs: list[Document]
    k: int = 2
    k1: float = 1.5
    b: float = 0.75

    def score(self, query: str) -> list[float]:
        raise NotImplementedError("M2: BM25Retriever.score")

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        raise NotImplementedError("M2: BM25Retriever._get_relevant_documents")


def make_retriever(docs: list[Document], kind: str = "bm25", k: int = 2, embeddings: Any | None = None) -> BaseRetriever:
    raise NotImplementedError("M2: make_retriever")


def build_retrievers(
    rules_dir: Path | str = DEFAULT_RULES_DIR, kind: str = "bm25", k: int = 2, embeddings: Any | None = None
) -> dict[str, BaseRetriever]:
    raise NotImplementedError("M2: build_retrievers")


def format_docs(docs: list[Document]) -> str:
    raise NotImplementedError("M2: format_docs")
