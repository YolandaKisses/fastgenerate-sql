#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.database import Session, engine  # noqa: E402
from app.services.knowledge_graph_rebuild import rebuild_datasource_graph_artifacts  # noqa: E402


def main() -> int:
    with Session(engine) as session:
        result = rebuild_datasource_graph_artifacts(
            session,
            datasource_name="dd_etl",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
