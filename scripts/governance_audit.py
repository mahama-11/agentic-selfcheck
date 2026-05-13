#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, sys, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import yaml, jsonschema

FEATURES = {
    "project-doc-governance": {"scope":"project", "title":"Project documentation freshness and standards"},
    "project-code-health-governance": {"scope":"project", "title":"Project code health and dead-code hygiene"},
    "hermes-self-governance": {"scope":"system", "title":"Hermes/SelfCheck output governance"},
    "skill-library-governance": {"scope":"skills", "title":"Hermes skill library governance"},
    "pitfall-feedback-loop": {"scope":"pitfalls", "title":"Pitfall feedback loop governance"},
}
@dataclass
class Finding:
    severity: str
    category: str
    path: str
    message: str
    recommended_action: str
    human_required: bool = False

def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}

def iter_files(base: Path, patterns: list[str], exclude_parts: set[str] | None = None, limit: int = 5000):
    exclude_parts = exclude_parts or {".git", "node_modules", ".venv", "vendor", "dist", "build", "__pycache__"}
    seen = 0
    for pat in patterns:
        for p in base.glob(pat):
            if seen >= limit: return
            if any(part in exclude_parts for part in p.parts): continue
            if p.is_file():
                seen += 1
                yield p

def rel(root: Path, p: Path | str) -> str:
    pp = Path(p)
    try: return str(pp.resolve().relative_to(root.resolve()))
    except Exception: return str(p)

def add(f, severity, category, path, message, action, human=False):
    f.append(Finding(severity, category, path, message, action, human))

def check_doc_governance(root: Path):
    findings=[]; docs=list(iter_files(root,["README*","docs/**/*.md",".hermes/workflows/**/*.md"],limit=1500))
    if not docs:
        add(findings,"warn","docs",".","No documentation files found in governance scope.","Configure project documentation scope or add docs."); return findings
    stale_words=re.compile(r"\b(TODO|FIXME|temporary|临时|过期|待补|mock|fake)\b",re.I)
    pass_claim=re.compile(r"\b(PASS|通过|已完成|success|succeeded)\b",re.I)
    evidence_hint=re.compile(r"(reports/|\.hermes/workflows/|evidence|证据|screenshot|json)",re.I)
    counts={"stale":0,"claim":0,"link":0}
    for p in docs:
        text=p.read_text(encoding="utf-8",errors="ignore")
        if stale_words.search(text):
            counts["stale"]+=1
            if counts["stale"]<=10: add(findings,"warn","docs",rel(root,p),"Doc contains TODO/FIXME/temporary/mock/fake markers.","Review whether marker is still accurate; convert to tracked task or remove.")
        if pass_claim.search(text) and not evidence_hint.search(text):
            counts["claim"]+=1
            if counts["claim"]<=10: add(findings,"warn","evidence",rel(root,p),"Doc makes pass/success/completion claim without obvious evidence link.","Link report path, workflow evidence, or downgrade wording.")
        for m in re.finditer(r"\]\(([^)]+)\)", text):
            target=m.group(1).split('#',1)[0]
            if not target or re.match(r"^[a-z]+://",target) or target.startswith("mailto:"): continue
            if not (p.parent/target).resolve().exists():
                counts["link"]+=1
                if counts["link"]<=10: add(findings,"warn","docs",rel(root,p),f"Markdown link target not found: {target}","Fix or remove stale link.")
    if len(docs)>1000: add(findings,"info","docs",".",f"Large doc scope scanned ({len(docs)} files); report is capped.","Tune governance scope per project adapter.")
    return findings

def check_code_health(root: Path):
    findings=[]; files=list(iter_files(root,["**/*.py","**/*.go","**/*.ts","**/*.tsx","**/*.js","**/*.jsx"],limit=4000))
    if not files:
        add(findings,"warn","code-health",".","No source files found in governance scope.","Configure project code-health target paths."); return findings
    for p in list(iter_files(root,["**/*.tmp","**/*.bak","**/*.orig","**/*~"],limit=200))[:20]:
        add(findings,"warn","code-health",rel(root,p),"Temporary/backup file found in repository tree.","Remove or move to ignored cache after human-safe review.")
    large=[]
    for p in files:
        try: lines=p.read_text(encoding="utf-8",errors="ignore").count("\n")+1
        except Exception: continue
        if lines>800: large.append((lines,p))
    for lines,p in sorted(large,reverse=True)[:20]:
        add(findings,"warn","code-health",rel(root,p),f"Large source file ({lines} lines) may reduce locality and AI navigability.","Review for deep module seams or split only with tests and design approval.")
    names={}
    for p in files: names.setdefault(p.name,[]).append(p)
    for name,paths in sorted([(k,v) for k,v in names.items() if len(v)>=4], key=lambda kv: len(kv[1]), reverse=True)[:10]:
        add(findings,"info","code-health",rel(root,paths[0]),f"Repeated source filename `{name}` appears {len(paths)} times.","Check if repetition reflects real adapters or accidental duplication.")
    return findings

def check_hermes_self(root: Path):
    findings=[]; workflows=root/".hermes"/"workflows"
    if not workflows.exists(): add(findings,"warn","workflow",rel(root,workflows),"Workflow evidence folder missing.","Create workflow evidence folders."); return findings
    required=["01-requirement.md","02-architecture-review.md","05-spec-review-report.md","06-quality-review-report.md","07-qa-report.md","08-final-verification.md"]
    for d in sorted([p for p in workflows.iterdir() if p.is_dir()])[:200]:
        missing=[n for n in required if not (d/n).exists()]
        if missing and not any((d/n).exists() for n in ["01-summary.md","README.md"]):
            add(findings,"warn","workflow",rel(root,d),f"Workflow folder lacks phase evidence: {', '.join(missing[:4])}.","Run init-workflow or add explicit summary/exception evidence.")
        if not (d/"09-harness-report.md").exists() and any((d/n).exists() for n in required):
            add(findings,"info","workflow",rel(root,d),"Workflow has role evidence but no 09-harness-report.md.","Run selfcheck harness for the associated feature when feature contract exists.")
    for fp in list((root/'features').glob('*.yaml'))[:200] if (root/'features').exists() else []:
        try: fid=load_yaml(fp).get('id')
        except Exception: continue
        rdir=root/'reports'/str(fid)
        if fid and rdir.exists() and not (rdir/'harness.md').exists() and not str(fid).startswith('selfcheck-'):
            add(findings,"info","evidence",rel(root,rdir),f"Reports exist for feature `{fid}` but no harness.md projection.","Run selfcheck harness for the feature.")
    return findings

def check_skill_library(root: Path):
    findings=[]; skill_files=[]
    for base in [Path.home()/'.hermes'/'skills', root/'.hermes'/'skills']:
        if base.exists(): skill_files += list(base.glob('**/SKILL.md'))[:2000]
    if not skill_files: add(findings,"warn","skill","~/.hermes/skills","No skill files found.","Confirm Hermes skill directory location."); return findings
    for p in skill_files[:500]:
        text=p.read_text(encoding='utf-8',errors='ignore'); lower=text.lower(); missing=[]
        if 'description:' not in lower: missing.append('frontmatter description')
        if '## when to use' not in lower and '## when' not in lower: missing.append('When to Use section')
        if 'pitfall' not in lower and 'common mistake' not in lower: missing.append('Pitfalls/Common mistakes')
        if 'verification' not in lower and 'verify' not in lower: missing.append('Verification guidance')
        if missing: add(findings,"warn","skill",str(p),f"Skill may be missing standard sections: {', '.join(missing)}.","Patch local unpinned skill or document exception.")
        if re.search(r"/tmp/|localhost:\d+|TODO|FIXME", text): add(findings,"info","skill",str(p),"Skill contains potentially stale local path/port/TODO marker.","Verify command/path freshness before relying on it.")
    return findings

def load_pitfalls(root: Path):
    findings=[]; out=[]; schema_path=root/'schemas/pitfall.schema.json'; schema=json.loads(schema_path.read_text()) if schema_path.exists() else None; pdir=root/'pitfalls'
    if not pdir.exists(): add(findings,'warn','pitfall','pitfalls/','Pitfall registry directory missing.','Create pitfalls/ and add records.'); return out,findings
    for p in sorted(pdir.glob('*.yaml')):
        try:
            data=load_yaml(p)
            if schema: jsonschema.validate(data,schema)
            out.append(data|{'__path':rel(root,p)})
        except Exception as exc: add(findings,'error','pitfall',rel(root,p),f'Invalid pitfall record: {exc}','Fix pitfall YAML to match schema.')
    return out,findings

def check_pitfalls(root: Path):
    records,findings=load_pitfalls(root)
    if not records: add(findings,'info','pitfall','pitfalls/','No pitfall records yet; registry is ready but empty.','Add records when failures or corrections occur.'); return findings
    seen={}
    for rec in records:
        path=rec.get('__path','pitfalls/')
        if rec.get('status')=='open' and rec.get('prevention_action') in {'accepted_risk',None,''}: add(findings,'error','pitfall',path,'Open pitfall has no concrete prevention action.','Convert to rule/verifier/skill/doc or close with accepted-risk evidence.')
        if rec.get('prevention_action')=='accepted_risk' and not rec.get('rerun_evidence'): add(findings,'human','pitfall',path,'Accepted risk pitfall lacks decision evidence.','Attach human decision evidence.',True)
        key=re.sub(r'\s+',' ',str(rec.get('symptom','')).lower())[:120]; seen.setdefault(key,[]).append(path)
    for key,paths in seen.items():
        if key and len(paths)>1: add(findings,'warn','pitfall',paths[0],f'Potential repeated pitfall appears {len(paths)} times.','Consolidate root cause and prevention action.')
    return findings

def status_from(findings):
    if any(f.human_required or f.severity=='human' for f in findings): return 'NEEDS_HUMAN'
    if any(f.severity=='error' for f in findings): return 'NEEDS_REPAIR'
    if any(f.severity in {'warn','info'} for f in findings): return 'PASS_WITH_NOTES'
    return 'PASS'

def render_md(report):
    lines=[f"# Governance Audit: {report['feature']}",'',f"- Status: `{report['status']}`",f"- Scope: `{report['scope']}`",f"- Generated: `{report['generated_at_epoch']}`",'', '## Top Findings','']
    if not report.get('findings'): lines.append('- none')
    for f in (report.get('findings') or [])[:30]:
        hr=' HUMAN' if f.get('human_required') else ''
        lines.append(f"- [{f['severity']}/{f['category']}{hr}] `{f['path']}` — {f['message']} Action: {f['recommended_action']}")
    lines += ['', '## Human Required', '']
    hrs=report.get('human_required') or []
    if not hrs: lines.append('- none')
    for f in hrs[:20]: lines.append(f"- `{f['path']}` — {f['message']}")
    lines += ['', '## Evidence', '', f"- JSON: `{report['evidence']['json']}`", f"- Markdown: `{report['evidence']['markdown']}`", '']
    return '\n'.join(lines)

def run_feature(root, feature):
    if feature=='project-doc-governance': findings=check_doc_governance(root)
    elif feature=='project-code-health-governance': findings=check_code_health(root)
    elif feature=='hermes-self-governance': findings=check_hermes_self(root)
    elif feature=='skill-library-governance': findings=check_skill_library(root)
    elif feature=='pitfall-feedback-loop': findings=check_pitfalls(root)
    else: raise SystemExit(f'Unknown governance feature: {feature}')
    status=status_from(findings); rdir=root/'reports'/feature; rdir.mkdir(parents=True,exist_ok=True)
    report={'feature':feature,'status':status,'scope':FEATURES.get(feature,{}).get('scope','unknown'),'title':FEATURES.get(feature,{}).get('title',''),'generated_at_epoch':time.time(),'findings':[asdict(f) for f in findings],'auto_fix':[],'human_required':[asdict(f) for f in findings if f.human_required or f.severity=='human'],'evidence':{'json':f'reports/{feature}/audit.json','markdown':f'reports/{feature}/audit.md'},'next_action':'repair findings' if status=='NEEDS_REPAIR' else ('human decision required' if status=='NEEDS_HUMAN' else 'monitor')}
    (rdir/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); (rdir/'audit.md').write_text(render_md(report),encoding='utf-8')
    return report

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='.'); ap.add_argument('--feature',required=True,choices=[*FEATURES.keys(),'all']); ap.add_argument('--format',choices=['json','markdown','both'],default='both'); ap.add_argument('--fail-on-needs',action='store_true'); args=ap.parse_args(argv)
    root=Path(args.root).resolve(); reports=[run_feature(root,f) for f in (list(FEATURES) if args.feature=='all' else [args.feature])]
    payload=reports[0] if len(reports)==1 else {'reports':reports}
    if args.format in {'json','both'}: print(json.dumps(payload,ensure_ascii=False,indent=2))
    if args.format in {'markdown','both'}:
        for r in reports: print(render_md(r))
    if args.fail_on_needs and any(r['status'] in {'NEEDS_REPAIR','NEEDS_HUMAN'} for r in reports): raise SystemExit(1)
if __name__=='__main__': main()
