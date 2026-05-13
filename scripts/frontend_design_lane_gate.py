#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path

TEMPLATE_DIR = Path('templates/frontend/design-lane-generation')
REQUIRED_TEMPLATES = ['DESIGN_LANE_ORCHESTRATION.md','LANE_BRIEF.md','PROTOTYPE_ARTIFACT.md','LANE_NOTES.md']
# Lane screenshot evidence intentionally accepts only PNG for now because it can be
# validated with a strict stdlib parser (IHDR+IDAT+IEND+CRC+zlib scanlines).
# JPEG/WebP require real decoders to avoid structural fake-image fail-open cases.
IMAGE_EXTS={'.png'}
REQUIRED_LANE_FILES=['LANE_BRIEF.md','PROTOTYPE_ARTIFACT.md','LANE_NOTES.md']
PLACEHOLDER_MARKERS=['artifact_path_or_url:', 'generated_at:', 'source_prompt_path:', 'What was produced', 'Known limitations', 'decision: keep|discard|needs_iteration', 'rationale:']


def finding(sev, path, msg): return {'severity':sev,'path':str(path),'message':msg}
def read(p: Path) -> str: return p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
def nonempty(p: Path, min_size: int=60) -> bool: return p.exists() and p.is_file() and p.stat().st_size >= min_size

def is_valid_image(p: Path) -> bool:
    try:
        data=p.read_bytes()
    except OSError:
        return False
    ext=p.suffix.lower()
    if ext=='.png':
        return is_valid_png(data)
    if ext in {'.jpg','.jpeg'}:
        return is_valid_jpeg(data)
    if ext=='.webp':
        return is_valid_webp(data)
    return False

def is_valid_png(data: bytes) -> bool:
    import zlib
    sig=b'\x89PNG\r\n\x1a\n'
    if len(data) < 57 or not data.startswith(sig):
        return False
    pos=len(sig); seen_ihdr=False; seen_idat=False; seen_iend=False
    width=height=bit_depth=color_type=None
    idat_parts=[]
    try:
        while pos + 12 <= len(data):
            length=int.from_bytes(data[pos:pos+4], 'big'); pos += 4
            ctype=data[pos:pos+4]; pos += 4
            if length < 0 or pos + length + 4 > len(data):
                return False
            chunk=data[pos:pos+length]; pos += length
            crc_expected=int.from_bytes(data[pos:pos+4], 'big'); pos += 4
            crc_actual=zlib.crc32(ctype + chunk) & 0xffffffff
            if crc_expected != crc_actual:
                return False
            if not seen_ihdr:
                if ctype != b'IHDR' or length != 13:
                    return False
                width=int.from_bytes(chunk[0:4], 'big')
                height=int.from_bytes(chunk[4:8], 'big')
                bit_depth=chunk[8]; color_type=chunk[9]
                compression_method=chunk[10]; filter_method=chunk[11]; interlace_method=chunk[12]
                valid_depths={0:{1,2,4,8,16},2:{8,16},3:{1,2,4,8},4:{8,16},6:{8,16}}
                if width <= 0 or height <= 0 or color_type not in valid_depths or bit_depth not in valid_depths[color_type]:
                    return False
                # This gate only supports non-interlaced PNG evidence. Reject invalid IHDR
                # methods and Adam7 interlace until a full decoder is introduced.
                if compression_method != 0 or filter_method != 0 or interlace_method != 0:
                    return False
                seen_ihdr=True
            if ctype == b'IDAT':
                seen_idat=True; idat_parts.append(chunk)
            if ctype == b'IEND':
                seen_iend=True
                break
        if not (seen_ihdr and seen_idat and seen_iend and pos == len(data)):
            return False
        # Validate compressed raster payload shape. This is not full PNG rendering,
        # but it rejects placeholder/fake chunks: exact scanline length and legal filter bytes.
        raw=zlib.decompress(b''.join(idat_parts))
        channels={0:1,2:3,3:1,4:2,6:4}[color_type]
        scanline=1 + ((width * channels * bit_depth + 7)//8)
        expected=scanline * height
        if len(raw) != expected:
            return False
        return all(raw[row*scanline] in {0,1,2,3,4} for row in range(height))
    except Exception:
        return False

def is_valid_jpeg(data: bytes) -> bool:
    if len(data) < 64 or not data.startswith(b'\xff\xd8') or not data.rstrip().endswith(b'\xff\xd9'):
        return False
    pos=2; seen_sof=False; seen_sos=False
    try:
        while pos < len(data)-2:
            if data[pos] != 0xff:
                if seen_sos:
                    pos += 1; continue
                return False
            while pos < len(data) and data[pos] == 0xff:
                pos += 1
            if pos >= len(data): return False
            marker=data[pos]; pos += 1
            if marker == 0xd9:
                break
            if marker == 0xda:  # SOS: entropy-coded data follows until EOI
                if pos + 2 > len(data): return False
                seglen=int.from_bytes(data[pos:pos+2], 'big')
                if seglen < 2 or pos + seglen > len(data): return False
                seen_sos=True
                return seen_sof and data.rstrip().endswith(b'\xff\xd9') and len(data) - (pos + seglen) > 2
            if marker in {0x01} or 0xd0 <= marker <= 0xd7:
                continue
            if pos + 2 > len(data): return False
            seglen=int.from_bytes(data[pos:pos+2], 'big')
            if seglen < 2 or pos + seglen > len(data): return False
            if marker in {0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf}:
                if seglen >= 7:
                    h=int.from_bytes(data[pos+3:pos+5], 'big'); w=int.from_bytes(data[pos+5:pos+7], 'big')
                    seen_sof = w > 0 and h > 0
            pos += seglen
        return False
    except Exception:
        return False

def is_valid_webp(data: bytes) -> bool:
    if not (len(data) >= 30 and data.startswith(b'RIFF') and data[8:12]==b'WEBP'):
        return False
    declared=int.from_bytes(data[4:8], 'little') + 8
    if declared != len(data):
        return False
    pos=12; seen_payload=False
    try:
        while pos + 8 <= len(data):
            ctype=data[pos:pos+4]; size=int.from_bytes(data[pos+4:pos+8], 'little'); pos += 8
            if pos + size > len(data): return False
            payload=data[pos:pos+size]
            if ctype in {b'VP8 ', b'VP8L', b'VP8X'} and len(payload) >= 10:
                seen_payload=True
            pos += size + (size % 2)
        return seen_payload and pos == len(data)
    except Exception:
        return False

def substantive_text(text: str, min_len: int=120) -> bool:
    stripped=text.strip()
    if len(stripped) < min_len: return False
    lower=stripped.lower()
    placeholder_hits=sum(1 for m in PLACEHOLDER_MARKERS if m.lower() in lower)
    # Template-only files contain markers but no concrete values. Require at least one non-heading paragraph.
    paragraphs=[l.strip() for l in stripped.splitlines() if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('- artifact_') and not l.strip().startswith('- generated_at') and not l.strip().startswith('- source_prompt') and '|' not in l]
    return placeholder_hits < len(PLACEHOLDER_MARKERS) and any(len(p) > 40 and '<' not in p for p in paragraphs)

def check_base(root: Path) -> dict:
    findings=[]
    for name in REQUIRED_TEMPLATES:
        p=root/TEMPLATE_DIR/name
        if not nonempty(p): findings.append(finding('error', p, 'required design-lane template missing or empty'))
    schema=root/'schemas/frontend-design-lane.schema.json'
    if not nonempty(schema): findings.append(finding('error', schema, 'design-lane schema missing or empty'))
    else:
        try:
            json.loads(schema.read_text(encoding='utf-8'))
        except Exception as exc:
            findings.append(finding('error', schema, f'design-lane schema is not valid JSON: {exc}'))
    return {'status':'PASS' if not findings else 'FAIL','scope':'base','findings':findings}

def lane_dirs(wf: Path) -> list[Path]:
    d=wf/'design-lanes'
    if not d.exists(): return []
    return sorted([p for p in d.iterdir() if p.is_dir() and p.name.startswith('lane-')])

def image_files(lane: Path) -> list[str]:
    imgs=[]
    for rel in ['screenshots','visual-evidence']:
        d=lane/rel
        if d.exists():
            for p in d.rglob('*'):
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.stat().st_size > 0 and is_valid_image(p):
                    imgs.append(str(p))
    return imgs

def has_real_artifact(lane: Path) -> bool:
    text=read(lane/'PROTOTYPE_ARTIFACT.md')
    if 'artifact_path_or_url:' in text:
        m=re.search(r'artifact_path_or_url:\s*(\S+)', text)
        if m and m.group(1).strip() and not m.group(1).startswith('<') and m.group(1).strip() not in {'', 'TODO', 'todo'}:
            return True
    for rel in ['prototype.html','prototype.htm','prototype-artifact.html']:
        if (lane/rel).exists() and (lane/rel).stat().st_size > 200:
            return True
    return substantive_text(text, 180)

def decision_value(lane: Path) -> str | None:
    text=read(lane/'LANE_NOTES.md')
    m=re.search(r'decision:\s*(keep|discard|needs_iteration)\s*$', text, re.I|re.M)
    return m.group(1).lower() if m else None

def check_workflow(root: Path, workflow: Path, risk: str) -> dict:
    wf=workflow if workflow.is_absolute() else root/workflow
    risk=risk.upper()
    findings=[]
    if not wf.exists():
        return {'status':'FAIL','scope':'workflow','workflow':str(wf),'findings':[finding('error', wf, 'workflow does not exist')]}
    try:
        from frontend_design_quality_pack_gate import check_workflow as check_dqp_workflow
        dqp=check_dqp_workflow(root, wf, risk)
        if dqp.get('status') != 'PASS':
            findings.append(finding('error', wf, 'Design Quality Pack gate must pass before design lane generation'))
            findings.extend(dqp.get('findings', []))
    except Exception as exc:
        findings.append(finding('error', wf, f'could not validate prerequisite Design Quality Pack: {exc}'))
    required=2 if risk=='D' else 1
    lanes=lane_dirs(wf)
    if len(lanes) < required:
        findings.append(finding('error', wf/'design-lanes', f'{risk}-risk requires at least {required} design lane(s); found {len(lanes)}'))
    lane_results=[]
    keep_count=0
    for lane in lanes:
        lf=[]
        for name in REQUIRED_LANE_FILES:
            p=lane/name
            if not nonempty(p): lf.append(finding('error', p, 'required lane artifact missing or empty'))
        imgs=image_files(lane)
        if not imgs: lf.append(finding('error', lane/'screenshots', 'lane requires at least one real screenshot image'))
        if not has_real_artifact(lane): lf.append(finding('error', lane/'PROTOTYPE_ARTIFACT.md', 'lane requires a real prototype artifact path/url or substantive artifact notes'))
        dec=decision_value(lane)
        if dec is None: lf.append(finding('error', lane/'LANE_NOTES.md', 'lane decision must be keep|discard|needs_iteration'))
        if dec=='keep': keep_count += 1
        findings.extend(lf)
        lane_results.append({'lane':lane.name,'status':'PASS' if not lf else 'FAIL','decision':dec,'screenshots':imgs,'findings':lf})
    comparison=wf/'VARIANT_COMPARISON.md'
    if risk=='D' and not nonempty(comparison, 120):
        findings.append(finding('error', comparison, 'D-risk requires variant comparison before choosing a lane'))
    if lanes and keep_count < 1:
        findings.append(finding('error', wf/'design-lanes', 'at least one lane must be marked decision: keep'))
    return {'status':'PASS' if not findings else 'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'required_lanes':required,'lane_count':len(lanes),'keep_count':keep_count,'lanes':lane_results,'findings':findings}

def init_lanes(root: Path, workflow: Path, risk: str, force: bool=False) -> list[str]:
    wf=workflow if workflow.is_absolute() else root/workflow
    wf.mkdir(parents=True, exist_ok=True)
    lanes=['lane-a'] if risk.upper()=='C' else ['lane-a','lane-b']
    tmpl=root/TEMPLATE_DIR
    made=[]
    orch=wf/'DESIGN_LANE_ORCHESTRATION.md'
    if force or not orch.exists():
        shutil.copyfile(tmpl/'DESIGN_LANE_ORCHESTRATION.md', orch)
        made.append(str(orch))
    for lane_id in lanes:
        lane=wf/'design-lanes'/lane_id
        (lane/'screenshots').mkdir(parents=True, exist_ok=True)
        (lane/'visual-evidence').mkdir(exist_ok=True)
        for name in ['LANE_BRIEF.md','PROTOTYPE_ARTIFACT.md','LANE_NOTES.md']:
            target=lane/name
            if force or not target.exists():
                text=(tmpl/name).read_text(encoding='utf-8')
                text=text.replace('- lane_id:', f'- lane_id: {lane_id}', 1)
                if lane_id=='lane-a': text=text.replace('- direction: conservative|strong-fit|divergent|custom', '- direction: conservative', 1)
                if lane_id=='lane-b': text=text.replace('- direction: conservative|strong-fit|divergent|custom', '- direction: strong-fit', 1)
                target.write_text(text, encoding='utf-8')
                made.append(str(target))
        keep=lane/'screenshots/.gitkeep'
        keep.write_text('replace with real screenshot; placeholder does not pass gate\n', encoding='utf-8')
    return made

def main() -> int:
    ap=argparse.ArgumentParser(description='Validate and scaffold frontend design lane generation artifacts.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--workflow')
    ap.add_argument('--risk', choices=['C','D'], default='C')
    ap.add_argument('--init-lanes', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    if args.init_lanes:
        if not args.workflow: raise SystemExit('--init-lanes requires --workflow')
        made=init_lanes(root, Path(args.workflow), args.risk, args.force)
        result={'status':'PASS','scope':'init','created_or_refreshed':made}
    else:
        base=check_base(root)
        if args.workflow:
            wf=check_workflow(root, Path(args.workflow), args.risk)
            result={'status':'PASS' if base['status']=='PASS' and wf['status']=='PASS' else 'FAIL','base':base,'workflow':wf}
        else:
            result=base
    if args.format=='json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']}")
        for f in result.get('findings',[]) or result.get('base',{}).get('findings',[])+result.get('workflow',{}).get('findings',[]):
            print(f"{f['severity']}: {f['path']}: {f['message']}")
    return 0 if result['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
