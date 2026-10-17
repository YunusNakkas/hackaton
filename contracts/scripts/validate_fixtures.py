"""OpenAPI belgesini ve fixture'ları doğrular.

Kullanım: python contracts/scripts/validate_fixtures.py
Bağımlılıklar: pyyaml, jsonschema, openapi-spec-validator (backend dev bağımlılıklarında var).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate as validate_spec

CONTRACTS = Path(__file__).resolve().parents[1]
SPEC_PATH = CONTRACTS / "openapi.yaml"
FIXTURES = CONTRACTS / "fixtures"


def main() -> int:
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    validate_spec(spec)
    print(f"ok  {SPEC_PATH.name}")

    index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
    index.pop("$comment", None)

    listed = set(index)
    on_disk = {p.name for p in FIXTURES.glob("*.json")} - {"index.json"}
    failures = 0
    for name in sorted(on_disk - listed):
        print(f"ERR {name}: index.json'da şema eşlemesi yok")
        failures += 1

    schemas = spec["components"]["schemas"]
    for name, schema_name in sorted(index.items()):
        if schema_name not in schemas:
            print(f"ERR {name}: bilinmeyen şema {schema_name}")
            failures += 1
            continue
        path = FIXTURES / name
        if not path.exists():
            print(f"ERR {name}: dosya yok")
            failures += 1
            continue
        # Kök belge tüm spec'tir; böylece #/components/... referansları çözülür.
        root = {**spec, "$ref": f"#/components/schemas/{schema_name}"}
        validator = Draft202012Validator(root, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(json.loads(path.read_text(encoding="utf-8"))), key=str)
        if errors:
            failures += 1
            for err in errors:
                loc = "/".join(str(p) for p in err.absolute_path) or "<kök>"
                print(f"ERR {name} [{schema_name}] {loc}: {err.message}")
        else:
            print(f"ok  {name} [{schema_name}]")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
