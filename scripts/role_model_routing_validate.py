#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import jsonschema
import yaml


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="default-role-model-routing")
    parser.add_argument("--report", default="reports/role-model-routing/role-model-routing-validate.json")
    args = parser.parse_args()
    root = Path(args.root)
    schema = json.loads((root / "schemas" / "role-model-routing.schema.json").read_text(encoding="utf-8"))
    policy = load_yaml(root / "role-model-routing" / f"{args.policy}.yaml")
    jsonschema.validate(policy, schema)
    models = policy["models"]
    assertions = {
        "minimax_highspeed_defined": models.get("minimax_highspeed", {}).get("provider") == "minimax-cn" and models.get("minimax_highspeed", {}).get("model") == "MiniMax-M2.7-highspeed",
        "no_api_keys_in_policy": not re.search(r"sk-[A-Za-z0-9_.-]{20,}", json.dumps(policy)),
        "deterministic_roles_use_minimax": all(policy["roles"][role]["primary_model"] == "minimax_highspeed" for role in ["spec-reviewer", "qa", "final-verifier", "reporter"]),
        "architect_developer_high_capability": all(policy["roles"][role]["primary_model"] == "high_capability_default" for role in ["architect", "developer"]),
        "every_role_model_exists": all(cfg["primary_model"] in models and cfg["fallback_model"] in models for cfg in policy["roles"].values()),
        "secret_policy_never_emit": policy["defaults"]["secret_policy"] == "never_emit",
    }
    report = {"status": "PASS" if all(assertions.values()) else "FAIL", "policy": args.policy, "assertions": assertions}
    out = root / args.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
