"""M5 live 평가 CLI.

사용법 (프로젝트 루트에서):
    python eval/run_eval.py --k 3 --out eval/report.json
    python eval/run_eval.py --only C05,C12 --k 1
OPENAI_API_KEY가 필요하다. 종료 코드: 통과 0, 미달 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from library_agent.app import build_agent  # noqa: E402
from library_agent.evaluation import PASS_THRESHOLD, load_cases, run_eval  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cases", default=str(ROOT / "eval" / "eval_cases.json"))
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--out", default=str(ROOT / "eval" / "report.json"))
    p.add_argument("--workdir", default=str(ROOT / "runs" / "eval"))
    p.add_argument("--only", default="", help="쉼표로 구분한 case id")
    a = p.parse_args(argv)

    cases = load_cases(a.cases)
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c.id in keep]

    def factory(log_path: Path):
        return build_agent(log_path=log_path)  # 매 trial마다 새 store

    def show(cr):
        marks = "".join("O" if t.passed else "X" for t in cr.trials)
        flag = " (critical)" if cr.critical else ""
        print(f"{cr.case_id}  {marks}  pass^{a.k}={'PASS' if cr.pass_k else 'FAIL'}{flag}")
        for i, t in enumerate(cr.trials, 1):
            if not t.passed:
                print(f"    trial{i}: missing_tools={t.missing_tools} forbidden={t.forbidden_used} "
                      f"missing_kw={t.missing_keywords} error={t.error}")

    report = run_eval(cases, factory, k=a.k, workdir=a.workdir, on_case=show)
    Path(a.out).write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\noverall pass^{a.k} = {report.overall_pass_k:.2f} (기준 {PASS_THRESHOLD}) | critical_ok = {report.critical_ok}")
    print("RESULT:", "PASS" if report.passed else "FAIL")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
