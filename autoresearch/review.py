#!/usr/bin/env python3
"""
Autoresearch Review — GitHub-style before/after comparison in the browser.

Generates an HTML page with a split diff view (like GitHub PR merge),
score progression, and change summary, then opens it in the default browser.

Usage:
    python autoresearch/review.py          # generate HTML and open in browser
    python autoresearch/review.py --save   # also save to autoresearch/review.html

THIS FILE IS READ-ONLY. The autoresearch agent must NOT modify it.
"""

import difflib
import html
import importlib.util
import os
import sys
import tempfile
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.py"
BASELINE_PATH = Path(__file__).resolve().parent / ".baseline"
RESULTS_PATH = Path(__file__).resolve().parent / "results.tsv"
REVIEW_OUTPUT = Path(__file__).resolve().parent / "review.html"


def load_config():
    if not CONFIG_PATH.exists():
        print("❌ No config.py found. Run: python autoresearch/setup.py", file=sys.stderr)
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("config", str(CONFIG_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        return []
    rows = []
    with open(RESULTS_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[1:]:
        parts = line.strip().split("\t")
        if len(parts) >= 7:
            rows.append({
                "iteration": parts[0],
                "score": parts[1],
                "max": parts[2],
                "pct": parts[3],
                "delta": parts[4],
                "status": parts[5],
                "description": parts[6],
            })
    return rows


# ── Side-by-side diff builder ──────────────────────────────────────────────

CONTEXT_LINES = 3


def build_split_diff_rows(before: str, after: str) -> list[dict]:
    """Build row data for a GitHub-style split diff."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    sm = difflib.SequenceMatcher(None, before_lines, after_lines)
    rows = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            block = list(range(i1, i2))
            if len(block) > CONTEXT_LINES * 2 + 1:
                for k in range(CONTEXT_LINES):
                    idx = block[k]
                    rows.append({
                        "left_num": idx + 1, "left_line": before_lines[idx], "left_type": "context",
                        "right_num": j1 + k + 1, "right_line": after_lines[j1 + k], "right_type": "context",
                    })
                skipped = len(block) - CONTEXT_LINES * 2
                rows.append({
                    "left_num": "", "left_line": f"\u22ef {skipped} unchanged lines \u22ef",
                    "left_type": "hunk",
                    "right_num": "", "right_line": "", "right_type": "hunk",
                })
                for k in range(CONTEXT_LINES):
                    idx = block[-(CONTEXT_LINES - k)]
                    rows.append({
                        "left_num": idx + 1, "left_line": before_lines[idx], "left_type": "context",
                        "right_num": j2 - CONTEXT_LINES + k + 1, "right_line": after_lines[j2 - CONTEXT_LINES + k],
                        "right_type": "context",
                    })
            else:
                for k, idx in enumerate(block):
                    rows.append({
                        "left_num": idx + 1, "left_line": before_lines[idx], "left_type": "context",
                        "right_num": j1 + k + 1, "right_line": after_lines[j1 + k], "right_type": "context",
                    })

        elif tag == "replace":
            left_block = list(range(i1, i2))
            right_block = list(range(j1, j2))
            max_len = max(len(left_block), len(right_block))
            for k in range(max_len):
                left = ({"left_num": left_block[k] + 1, "left_line": before_lines[left_block[k]], "left_type": "remove"}
                        if k < len(left_block)
                        else {"left_num": "", "left_line": "", "left_type": "empty"})
                right = ({"right_num": right_block[k] + 1, "right_line": after_lines[right_block[k]], "right_type": "add"}
                         if k < len(right_block)
                         else {"right_num": "", "right_line": "", "right_type": "empty"})
                rows.append({**left, **right})

        elif tag == "delete":
            for idx in range(i1, i2):
                rows.append({
                    "left_num": idx + 1, "left_line": before_lines[idx], "left_type": "remove",
                    "right_num": "", "right_line": "", "right_type": "empty",
                })

        elif tag == "insert":
            for idx in range(j1, j2):
                rows.append({
                    "left_num": "", "left_line": "", "left_type": "empty",
                    "right_num": idx + 1, "right_line": after_lines[idx], "right_type": "add",
                })

    return rows


def diff_rows_to_html(rows: list[dict]) -> str:
    cls_map = {"context": "ctx", "remove": "del", "add": "add", "empty": "empty"}
    prefix_map = {"remove": "-", "context": " ", "add": "+"}
    parts = []
    for r in rows:
        lt, rt = r["left_type"], r["right_type"]
        if lt == "hunk":
            parts.append(
                f'<tr class="hunk">'
                f'<td class="ln"></td><td class="code hunk-text">{html.escape(r["left_line"])}</td>'
                f'<td class="ln"></td><td class="code hunk-text">{html.escape(r["left_line"])}</td>'
                f'</tr>')
            continue
        lc, rc = cls_map.get(lt, "ctx"), cls_map.get(rt, "ctx")
        lp, rp = prefix_map.get(lt, ""), prefix_map.get(rt, "")
        parts.append(
            f'<tr>'
            f'<td class="ln {lc}">{r.get("left_num","")}</td>'
            f'<td class="code {lc}"><span class="pfx">{lp}</span>{html.escape(r.get("left_line",""))}</td>'
            f'<td class="ln {rc}">{r.get("right_num","")}</td>'
            f'<td class="code {rc}"><span class="pfx">{rp}</span>{html.escape(r.get("right_line",""))}</td>'
            f'</tr>')
    return "\n".join(parts)


# ── HTML generation ─────────────────────────────────────────────────────────

CSS = """\
:root{
  --bg:#0d1117;--sf:#161b22;--bd:#30363d;--tx:#e6edf3;--tm:#8b949e;--ac:#58a6ff;
  --ga:#12261e;--gn:#1a3a2a;--gt:#3fb950;--ra:#2d1215;--rn:#3d1a1e;--rt:#f85149;
  --hk:#1c2128;--bg-green:#238636;--bg-red:#da3633;--bg-gray:#30363d;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:var(--bg);color:var(--tx);line-height:1.5}
.ctr{max-width:1440px;margin:0 auto;padding:24px}
.hdr{border-bottom:1px solid var(--bd);padding-bottom:16px;margin-bottom:24px}
.hdr h1{font-size:24px;font-weight:600}
.hdr .fn{color:var(--ac)}
.hdr .sub{color:var(--tm);font-size:14px;margin-top:4px}
.banner{display:flex;align-items:center;gap:16px;background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:16px 20px;margin-bottom:24px}
.sbox{text-align:center;min-width:100px}
.sbox .lb{font-size:11px;text-transform:uppercase;color:var(--tm);letter-spacing:.5px}
.sbox .vl{font-size:28px;font-weight:700}
.sbox .vl.grn{color:var(--gt)}
.sarr{font-size:24px;color:var(--tm)}
.sgoal{flex:1;border-left:1px solid var(--bd);padding-left:16px;margin-left:8px}
.sgoal .lb{font-size:11px;text-transform:uppercase;color:var(--tm);letter-spacing:.5px}
.sgoal .txt{font-size:14px;margin-top:2px}
.sec{margin-bottom:24px}
.sec h2{font-size:16px;font-weight:600;margin-bottom:12px}
.card{background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:12px 16px;margin-bottom:8px;display:flex;align-items:flex-start;gap:12px}
.card .ix{background:var(--bg-green);color:#fff;font-size:12px;font-weight:600;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.card.rev .ix{background:var(--bg-red)}
.card .bd{flex:1}
.card .ti{font-size:14px;font-weight:600}
.card .me{font-size:12px;color:var(--tm);margin-top:2px}
.badge{font-size:11px;padding:2px 8px;border-radius:12px;font-weight:500}
.badge.kept{background:var(--bg-green);color:#fff}
.badge.reverted{background:var(--bg-red);color:#fff;text-decoration:line-through}
.dhdr{background:var(--sf);border:1px solid var(--bd);border-radius:6px 6px 0 0;padding:8px 16px;font-size:13px;display:flex;justify-content:space-between;color:var(--tm)}
.dstat .a{color:var(--gt)}.dstat .d{color:var(--rt)}
.slbl{display:flex;font-size:12px;font-weight:600;margin-bottom:4px}
.slbl span{width:50%;padding:4px 12px}
.slbl .bl{color:var(--rt)}.slbl .al{color:var(--gt)}
.dwrap{border:1px solid var(--bd);border-top:none;border-radius:0 0 6px 6px;overflow-x:auto}
table.diff{width:100%;border-collapse:collapse;font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace;font-size:12px;table-layout:fixed}
table.diff td{padding:0 10px;white-space:pre;overflow:hidden;text-overflow:ellipsis;vertical-align:top}
table.diff td.ln{width:50px;min-width:50px;text-align:right;color:var(--tm);user-select:none;padding-right:8px;border-right:1px solid var(--bd)}
table.diff td.code{width:calc(50% - 50px);padding-left:10px;line-height:20px}
table.diff td.code .pfx{display:inline-block;width:12px;user-select:none;opacity:.6}
table.diff td:nth-child(3){border-left:2px solid var(--bd)}
.ctx{background:var(--bg)}.del{background:var(--ra)}.add{background:var(--ga)}.empty{background:var(--hk)}
td.ln.del{background:var(--rn)}td.ln.add{background:var(--gn)}
.hunk-text{background:var(--hk);color:var(--tm);text-align:center;font-style:italic;font-size:11px}
tr.hunk td{border-top:1px solid var(--bd);border-bottom:1px solid var(--bd)}
.nochange{background:var(--sf);border:1px solid var(--bd);border-radius:6px;padding:40px;text-align:center;color:var(--tm)}
"""


def generate_html() -> str:
    cfg = load_config()
    target = cfg.TARGET_FILE
    goal = getattr(cfg, "GOAL", "")
    filename = os.path.basename(target)

    if not BASELINE_PATH.exists():
        print("\u274c No baseline snapshot. Re-run: python autoresearch/setup.py", file=sys.stderr)
        sys.exit(1)
    with open(BASELINE_PATH, encoding="utf-8") as f:
        before = f.read()
    with open(REPO_ROOT / target, encoding="utf-8") as f:
        after = f.read()

    rows = load_results()
    baseline_row = rows[0] if rows else None
    kept = [r for r in rows if r["status"] == "keep"]
    reverted = [r for r in rows if r["status"] == "revert"]
    latest = rows[-1] if rows else None

    bscore = f"{baseline_row['score']}/{baseline_row['max']}" if baseline_row else "\u2014"
    bpct = f"{baseline_row['pct']}%" if baseline_row else ""
    fscore = f"{latest['score']}/{latest['max']}" if latest else "\u2014"
    fpct = f"{latest['pct']}%" if latest else ""

    before_lines = before.splitlines()
    after_lines = after.splitlines()
    sm = difflib.SequenceMatcher(None, before_lines, after_lines)
    additions = deletions = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"): deletions += i2 - i1
        if tag in ("replace", "insert"): additions += j2 - j1
    has_changes = additions > 0 or deletions > 0

    # Change cards
    cards = []
    for i, r in enumerate(kept, 1):
        cards.append(
            f'<div class="card"><div class="ix">{i}</div><div class="bd">'
            f'<div class="ti">{html.escape(r["description"])}</div>'
            f'<div class="me">Score impact: {html.escape(r["delta"])} pts \u2192 {r["score"]}/{r["max"]}</div>'
            f'</div><span class="badge kept">kept</span></div>')
    for r in reverted:
        cards.append(
            f'<div class="card rev"><div class="ix">\u2715</div><div class="bd">'
            f'<div class="ti" style="text-decoration:line-through;opacity:.6">{html.escape(r["description"])}</div>'
            f'<div class="me">Score impact: {html.escape(r["delta"])} pts (reverted)</div>'
            f'</div><span class="badge reverted">reverted</span></div>')
    changes_block = f'<div class="sec"><h2>Changes Made</h2>{"".join(cards)}</div>' if cards else ""

    # Diff
    if has_changes:
        diff_body = diff_rows_to_html(build_split_diff_rows(before, after))
        diff_block = (
            f'<div class="dhdr"><span>{html.escape(target)}</span>'
            f'<span class="dstat"><span class="a">+{additions}</span>&ensp;<span class="d">-{deletions}</span></span></div>'
            f'<div class="slbl"><span class="bl">Before (baseline)</span><span class="al">After (improved)</span></div>'
            f'<div class="dwrap"><table class="diff">{diff_body}</table></div>')
    else:
        diff_block = '<div class="nochange">No changes detected \u2014 before and after are identical.</div>'

    iters_text = f"{len(rows)} iterations ({len(kept)} kept, {len(reverted)} reverted)"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Review: {html.escape(filename)}</title><style>{CSS}</style></head>
<body><div class="ctr">
<div class="hdr"><h1>Autoresearch Review: <span class="fn">{html.escape(filename)}</span></h1>
<div class="sub">{html.escape(iters_text)}</div></div>
<div class="banner">
<div class="sbox"><div class="lb">Baseline</div><div class="vl">{html.escape(bscore)}</div><div class="lb">{html.escape(bpct)}</div></div>
<div class="sarr">\u2192</div>
<div class="sbox"><div class="lb">Final</div><div class="vl grn">{html.escape(fscore)}</div><div class="lb">{html.escape(fpct)}</div></div>
<div class="sgoal"><div class="lb">Goal</div><div class="txt">{html.escape(goal)}</div></div>
</div>
{changes_block}
<div class="sec"><h2>Side-by-Side Diff</h2>{diff_block}</div>
</div></body></html>"""


def main():
    page = generate_html()

    save_path = REVIEW_OUTPUT if "--save" in sys.argv else Path(tempfile.mktemp(suffix=".html", prefix="autoresearch_review_"))
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(page)

    webbrowser.open(save_path.as_uri())
    if "--save" in sys.argv:
        print(f"Review saved to: {REVIEW_OUTPUT.relative_to(REPO_ROOT)}")
    print(f"Opened in browser: {save_path.name}")


if __name__ == "__main__":
    main()
