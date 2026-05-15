#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from prototype_path_utils import resolve_under

REQUIRED_LEDGER_TOKENS = [
    "current_business_backbone_version",
    "Product/SKU",
    "Source Reference",
    "Deconstruction Session",
    "Intent / Asset Mapping",
    "Prompt / Generation Plan",
    "Variant Group",
    "Refinement Session",
    "Final Asset",
    "SKU Asset Library / Listing Draft / Export Trace",
]

# Product UI can use Chinese/product language, so checks are semantic token groups rather than exact internal terms.
PROTOTYPE_TOKEN_GROUPS = {
    "sku_product_entry": ["SKU", "商品"],
    "source_reference": ["参考", "素材"],
    "deconstruction": ["解构", "拆"],
    "intent_mapping": ["意图", "映射"],
    "prompt_plan": ["Prompt", "方案"],
    "variant_group": ["候选", "生成"],
    "refinement": ["微调"],
    "final_asset": ["保存", "图片"],
    "handoff": ["商品图库", "Listing", "下载记录"],
    "route_extract": ["双轨解析", "画面解构"],
    "route_decision": ["实时意图决策", "意图映射"],
    "route_execute": ["策略配置", "执行", "Prompt"],
    "route_save": ["候选", "保存同步"],
}

DELTA_FIELDS = [
    "previous_business_backbone_version",
    "candidate_business_backbone_version",
    "preserved",
    "strengthened",
    "removed",
    "weakened",
    "backbone_evidence",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def finding(path: Path, message: str) -> dict:
    return {"severity": "error", "path": str(path), "message": message}


def parse_field(text: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, re.M)
    return m.group(1).strip() if m else ""


def has_group(text: str, tokens: list[str]) -> bool:
    return all(tok in text for tok in tokens)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ensure prototypes preserve the locked business backbone.")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--prototype", required=True)
    ap.add_argument("--delta", help="Business backbone delta file, relative to workflow")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    wf = Path(args.workflow).resolve()
    findings: list[dict] = []
    try:
        prototype = resolve_under(wf, args.prototype, "prototype")
    except ValueError as exc:
        prototype = wf / "<invalid-prototype-path>"
        findings.append(finding(wf, str(exc)))
    ledger = wf / "BUSINESS_BACKBONE_LEDGER.md"
    metrics: dict[str, object] = {}

    if not ledger.exists():
        findings.append(finding(ledger, "BUSINESS_BACKBONE_LEDGER.md missing"))
        ledger_text = ""
    else:
        ledger_text = read(ledger)
        for token in REQUIRED_LEDGER_TOKENS:
            if token not in ledger_text:
                findings.append(finding(ledger, f"ledger missing locked backbone token: {token}"))
    current_version = parse_field(ledger_text, "current_business_backbone_version")
    metrics["current_business_backbone_version"] = current_version

    if not prototype.exists():
        findings.append(finding(prototype, "prototype missing"))
        proto_text = ""
    else:
        proto_text = read(prototype)
        missing_groups = [name for name, tokens in PROTOTYPE_TOKEN_GROUPS.items() if not has_group(proto_text, tokens)]
        metrics["missing_backbone_groups"] = missing_groups
        if missing_groups:
            findings.append(finding(prototype, "prototype missing business backbone groups: " + ", ".join(missing_groups)))

    if args.delta:
        try:
            delta = resolve_under(wf, args.delta, "delta")
        except ValueError as exc:
            delta = wf / "<invalid-delta-path>"
            findings.append(finding(wf, str(exc)))
        if not delta.exists():
            findings.append(finding(delta, "business backbone delta missing"))
            delta_text = ""
        else:
            delta_text = read(delta)
            for field in DELTA_FIELDS:
                if not parse_field(delta_text, field) and f"{field}:" not in delta_text:
                    findings.append(finding(delta, f"delta missing field: {field}"))
            prev = parse_field(delta_text, "previous_business_backbone_version")
            metrics["delta_previous_business_backbone_version"] = prev
            if current_version and prev and prev != current_version:
                findings.append(finding(delta, f"delta previous version {prev} does not match ledger {current_version}"))
            for field in ["removed", "weakened"]:
                val = parse_field(delta_text, field).lower()
                if val and val not in {"none", "无"} and "accepted_tradeoff" not in delta_text:
                    findings.append(finding(delta, f"{field} is not none; explicit accepted_tradeoff required"))
    else:
        findings.append(finding(wf, "missing --delta; every serious prototype must declare business backbone delta"))

    result = {"status": "PASS" if not findings else "FAIL", "metrics": metrics, "findings": findings}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} version={current_version or 'UNKNOWN'} missing_groups={len(metrics.get('missing_backbone_groups', []))} findings={len(findings)}")
        for f in findings:
            print(f"ERROR: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
