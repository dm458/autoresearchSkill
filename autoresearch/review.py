#!/usr/bin/env python3
"""
Autoresearch Review — Generate a before/after comparison document.

Reads the baseline snapshot, current file, and results log to produce
a markdown review showing what changed, why, and the full before/after.

Usage:
    python autoresearch/review.py              # generate and print to stdout
    python autoresearch/review.py --save       # also save to autoresearch/review.md

THIS FILE IS READ-ONLY. The autoresearch agent must NOT modify it.
"""

import difflib
import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.py"
BASELINE_PATH = Path(__file__).resolve().parent / ".baseline"
RESULTS_PATH = Path(__file__).resolve().parent / "results.tsv"
REVIEW_OUTPUT = Path(__file__).resolve().parent / "review.md"


def load_config():
    if not CONFIG_PATH.exists():
        print("❌ No config.py found. Run: python autoresearch/setup.py", file=sys.stderr)
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("config", str(CONFIG_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_results() -> list[dict]:
    """Parse results.tsv into a list of iteration dicts."""
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


def generate_diff(before: str, after: str, filename: str) -> str:
    """Generate a unified diff between before and after."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines, after_lines,
        fromfile=f"BEFORE: {filename}",
        tofile=f"AFTER: {filename}",
        lineterm="",
    )
    return "".join(diff)


def generate_review() -> str:
    """Build the full review markdown document."""
    cfg = load_config()
    target = cfg.TARGET_FILE
    goal = getattr(cfg, "GOAL", "")

    # Load before
    if not BASELINE_PATH.exists():
        print("❌ No baseline snapshot found. Re-run: python autoresearch/setup.py", file=sys.stderr)
        sys.exit(1)
    with open(BASELINE_PATH, encoding="utf-8") as f:
        before = f.read()

    # Load after
    target_path = REPO_ROOT / target
    if not target_path.exists():
        print(f"❌ Target file not found: {target}", file=sys.stderr)
        sys.exit(1)
    with open(target_path, encoding="utf-8") as f:
        after = f.read()

    # Load results
    rows = load_results()
    baseline_row = rows[0] if rows else None
    kept = [r for r in rows if r["status"] == "keep"]
    reverted = [r for r in rows if r["status"] == "revert"]
    latest = rows[-1] if rows else None

    # Build document
    lines = []
    lines.append(f"# Autoresearch Review: {os.path.basename(target)}")
    lines.append("")
    lines.append(f"> Auto-generated comparison of the skill file before and after improvement.")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| **File** | `{target}` |")
    lines.append(f"| **Goal** | {goal} |")
    if baseline_row and latest:
        lines.append(f"| **Baseline score** | {baseline_row['score']}/{baseline_row['max']} ({baseline_row['pct']}%) |")
        lines.append(f"| **Final score** | {latest['score']}/{latest['max']} ({latest['pct']}%) |")
    lines.append(f"| **Iterations** | {len(rows)} total ({len(kept)} kept, {len(reverted)} reverted) |")
    lines.append("")

    # Changes made
    if kept:
        lines.append("## Changes Made")
        lines.append("")
        for i, r in enumerate(kept, 1):
            lines.append(f"### {i}. {r['description']}")
            lines.append("")
            lines.append(f"- **Score impact:** {r['delta']} points (→ {r['score']}/{r['max']})")
            lines.append(f"- **Why:** This change addressed a gap detected by the scoring checks. "
                        f"The eval identified missing content and this edit added it to improve coverage.")
            lines.append("")

    if reverted:
        lines.append("### Reverted experiments")
        lines.append("")
        for r in reverted:
            lines.append(f"- ~~{r['description']}~~ (score {r['delta']})")
        lines.append("")

    # Diff
    diff_text = generate_diff(before, after, target)
    if diff_text:
        lines.append("## Diff")
        lines.append("")
        lines.append("```diff")
        lines.append(diff_text)
        lines.append("```")
        lines.append("")

    # Before and After
    lines.append("## Before (baseline)")
    lines.append("")
    lines.append("<details>")
    lines.append(f"<summary>Click to expand original {os.path.basename(target)}</summary>")
    lines.append("")
    lines.append("```markdown")
    lines.append(before)
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    lines.append("## After (current)")
    lines.append("")
    lines.append("<details>")
    lines.append(f"<summary>Click to expand improved {os.path.basename(target)}</summary>")
    lines.append("")
    lines.append("```markdown")
    lines.append(after)
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines)


def main():
    review = generate_review()

    # Handle Windows encoding
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print(review)

    if "--save" in sys.argv:
        with open(REVIEW_OUTPUT, "w", encoding="utf-8") as f:
            f.write(review)
        print(f"\n📝 Review saved to: {REVIEW_OUTPUT.relative_to(REPO_ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
