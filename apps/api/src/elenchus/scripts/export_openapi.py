"""Export the FastAPI OpenAPI schema to a JSON file.

Used by the frontend type-generation step (``pnpm gen:api-types``): this writes
the schema, then ``openapi-typescript`` turns it into
``apps/web/lib/api-types.ts`` (AGENTS.md section 12.4).

Usage:
    uv run elenchus-export-openapi [OUTPUT_PATH]

Defaults to writing ``openapi.json`` in the current directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from elenchus.main import create_app


def export(output_path: Path) -> Path:
    app = create_app()
    schema = app.openapi()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    written = export(output)
    print(f"Wrote OpenAPI schema to {written}")


if __name__ == "__main__":
    main()
