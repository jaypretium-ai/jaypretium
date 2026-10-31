"""케이스 YAML + 계산 결과 → app/index.html (단일 정적 파일, 서버 불필요).

사용: python build_app.py   → app/index.html 생성
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import yaml

from casebook import HERE, evaluate, load_cases


def _jsonable(o):
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def main() -> None:
    tax = yaml.safe_load(open(HERE / "taxonomy.yaml", encoding="utf-8"))
    cases = []
    for c in load_cases(HERE / "cases"):
        r = evaluate(c, HERE / "prices")
        c["result"] = {k: v for k, v in r.__dict__.items() if k != "horizon"} | {"horizon": r.horizon}
        cases.append(c)
    data = json.dumps({"patterns": tax["patterns"], "cases": cases}, ensure_ascii=False, default=_jsonable)
    tpl = (HERE / "app" / "template.html").read_text(encoding="utf-8")
    out = HERE / "app" / "index.html"
    out.write_text(tpl.replace("/*__DATA__*/null", data), encoding="utf-8")
    print(f"[app] {out} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
