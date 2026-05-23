#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

REQUIRED_BUSINESS_FEATURES = {
    "platform-runtime-business-integration-safety",
    "platform-financial-business-consistency",
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a YAML mapping")
    return data


def normalize_groups(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    raise ValueError(f"unsupported groups value: {value!r}")


def selector_event_features(root: Path) -> dict[str, dict[str, Any]]:
    selector = load_yaml(root / "config" / "v-business-gate-selector.yaml")
    features = selector.get("features", {})
    if not isinstance(features, dict):
        raise ValueError("config/v-business-gate-selector.yaml features must be a mapping")
    return {
        str(feature): config
        for feature, config in features.items()
        if isinstance(config, dict) and config.get("event")
    }


def event_routes(root: Path) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "events").glob("*.yaml")):
        route = load_yaml(path)
        event = route.get("event")
        if not event:
            continue
        route["_path"] = str(path.relative_to(root))
        routes[str(event)] = route
    return routes


def check(root: Path) -> dict[str, Any]:
    features = selector_event_features(root)
    routes = event_routes(root)
    cases: list[dict[str, Any]] = []

    for feature, config in sorted(features.items()):
        event = str(config.get("event"))
        selector_groups = sorted(normalize_groups(config.get("groups")))
        route = routes.get(event)
        case = {
            "feature": feature,
            "event": event,
            "selector_groups": selector_groups,
            "route_path": route.get("_path") if route else None,
            "route_feature": route.get("feature") if route else None,
            "route_groups": sorted(normalize_groups(route.get("groups"))) if route else [],
            "ok": False,
            "errors": [],
        }
        if route is None:
            case["errors"].append("missing_event_route")
        else:
            if route.get("feature") != feature:
                case["errors"].append("route_feature_mismatch")
            if sorted(normalize_groups(route.get("groups"))) != selector_groups:
                case["errors"].append("route_groups_mismatch")
        case["ok"] = not case["errors"]
        cases.append(case)

    missing_required = sorted(REQUIRED_BUSINESS_FEATURES - set(features))
    required_cases = [case for case in cases if case["feature"] in REQUIRED_BUSINESS_FEATURES]
    required_failures = [case for case in required_cases if not case["ok"]]
    ok = all(case["ok"] for case in cases) and not missing_required and not required_failures
    return {
        "status": "PASS" if ok else "FAIL",
        "selector": "config/v-business-gate-selector.yaml",
        "events_dir": "events",
        "checked_feature_count": len(cases),
        "required_business_features": sorted(REQUIRED_BUSINESS_FEATURES),
        "missing_required_business_features": missing_required,
        "cases": cases,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    payload = check(root)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("status=" + payload["status"])
        for case in payload["cases"]:
            print(f"{case['feature']}: event={case['event']} route={case['route_path']} errors={case['errors']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
