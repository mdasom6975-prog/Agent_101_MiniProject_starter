"""이용 규정 RAG (명세서 5.3절)."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import InMemoryVectorStore

from .store import DEFAULT_DATA_DIR

DEFAULT_RULES_DIR = DEFAULT_DATA_DIR / "rules"
TOPIC_FILES: dict[str, str] = {
    "loan": "01_대출반납.md",
    "overdue": "02_연체이용제한.md",
    "facility": "03_시설프로그램.md",
}
NO_RESULT = "관련 조항을 찾지 못했습니다."

_ARTICLE_RE = re.compile(r"^(제\d+조)\(([^)]+)\)\s*(.+)$")
_TOKEN_RE = re.compile(r"[0-9a-z가-힣]+")


def load_rules(rules_dir: Path | str = DEFAULT_RULES_DIR, topic: str | None = None) -> list[Document]:
    """규정 파일을 조(條) 단위 Document로 나눈다. topic이 None이면 TOPIC_FILES 순서로 모두 읽는다."""
    if topic is not None and topic not in TOPIC_FILES:
        raise ValueError(f"알 수 없는 topic입니다: {topic}")
    topics = [topic] if topic is not None else list(TOPIC_FILES)
    docs: list[Document] = []
    for t in topics:
        filename = TOPIC_FILES[t]
        text = (Path(rules_dir) / filename).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            match = _ARTICLE_RE.match(line)
            if match:
                docs.append(
                    Document(
                        page_content=line,
                        metadata={"topic": t, "article": match.group(1), "title": match.group(2), "source": filename},
                    )
                )
    return docs


def tokenize(text: str) -> list[str]:
    """소문자화 후 한글·영숫자 덩어리를 뽑고, 길이 2 이상은 문자 bigram으로 펼친다."""
    tokens: list[str] = []
    for chunk in _TOKEN_RE.findall(text.lower()):
        if len(chunk) == 1:
            tokens.append(chunk)
        else:
            tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return tokens


class BM25Retriever(BaseRetriever):
    """Okapi BM25 (k1=1.5, b=0.75). 명세서 5.3절의 수식과 tie-break 규칙을 따른다."""

    docs: list[Document]
    k: int = 2
    k1: float = 1.5
    b: float = 0.75

    def score(self, query: str) -> list[float]:
        """모든 문서에 대한 BM25 점수를 문서 순서대로 반환한다. 질의 토큰이 중복되면 중복만큼 더한다."""
        doc_tokens = [tokenize(d.page_content) for d in self.docs]
        n = len(doc_tokens)
        if n == 0:
            return []
        avgdl = sum(len(t) for t in doc_tokens) / n
        freqs = [Counter(t) for t in doc_tokens]
        df: Counter[str] = Counter()
        for f in freqs:
            df.update(f.keys())

        scores = [0.0] * n
        for term in tokenize(query):
            nt = df.get(term, 0)
            if nt == 0:
                continue
            idf = math.log((n - nt + 0.5) / (nt + 0.5) + 1)
            for i, f in enumerate(freqs):
                tf = f.get(term, 0)
                if tf == 0:
                    continue
                dl = len(doc_tokens[i])
                norm = tf + self.k1 * (1 - self.b + self.b * dl / avgdl) if avgdl else tf + self.k1
                scores[i] += idf * tf * (self.k1 + 1) / norm
        return scores

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        scores = self.score(query)
        # 점수 내림차순, 동점이면 원래 순서(index 오름차순). 점수 0은 제외한다.
        ranked = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [self.docs[i] for i in ranked if scores[i] > 0][: self.k]


def make_retriever(docs: list[Document], kind: str = "bm25", k: int = 2, embeddings: Any | None = None) -> BaseRetriever:
    if kind == "bm25":
        return BM25Retriever(docs=docs, k=k)
    if kind == "vector":
        if embeddings is None:
            raise ValueError("vector retriever에는 embeddings가 필요합니다")
        return InMemoryVectorStore.from_documents(docs, embeddings).as_retriever(search_kwargs={"k": k})
    raise ValueError(f"알 수 없는 retriever 종류입니다: {kind}")


def build_retrievers(
    rules_dir: Path | str = DEFAULT_RULES_DIR, kind: str = "bm25", k: int = 2, embeddings: Any | None = None
) -> dict[str, BaseRetriever]:
    return {topic: make_retriever(load_rules(rules_dir, topic), kind, k, embeddings) for topic in ("loan", "overdue", "facility")}


def format_docs(docs: list[Document]) -> str:
    if not docs:
        return NO_RESULT
    return "\n\n".join(d.page_content for d in docs)
