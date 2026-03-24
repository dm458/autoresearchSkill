"""
Autoresearch Eval — Generic scoring engine.

Reads check definitions from config.py and scores the target file.
All checks are programmatic — no LLM calls required.

Usage:
    python autoresearch/eval.py              # pretty-print report
    python autoresearch/eval.py --json       # JSON to stdout
    python autoresearch/eval.py --log DESC   # score + append to results.tsv

THIS FILE IS READ-ONLY. The autoresearch agent must NOT modify it.
"""

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.py"
RESULTS_PATH = Path(__file__).resolve().parent / "results.tsv"


def load_config():
    if not CONFIG_PATH.exists():
        print("❌ No config.py found. Run: python autoresearch/setup.py", file=sys.stderr)
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("config", str(CONFIG_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Text helpers ────────────────────────────────────────────────────────────

def _lo(text: str) -> str:
    return text.lower()


def has_all(text: str, terms: list[str]) -> bool:
    lo = _lo(text)
    return all(_lo(t) in lo for t in terms)


def has_any(text: str, terms: list[str]) -> bool:
    lo = _lo(text)
    return any(_lo(t) in lo for t in terms)


def count_matches(text: str, terms: list[str]) -> int:
    lo = _lo(text)
    return sum(1 for t in terms if _lo(t) in lo)


def terms_in_order(text: str, terms: list[str]) -> bool:
    lo = _lo(text)
    positions = [lo.find(_lo(t)) for t in terms]
    found = [p for p in positions if p >= 0]
    return len(found) >= 2 and all(found[i] < found[i + 1] for i in range(len(found) - 1))


# ── Check evaluator ────────────────────────────────────────────────────────

def eval_check(check: dict, doc: str) -> int:
    pts = check["pts"]
    ctype = check["type"]

    if ctype == "has_all":
        return pts if has_all(doc, check["terms"]) else 0
    if ctype == "has_any":
        return pts if has_any(doc, check["terms"]) else 0
    if ctype == "count_of":
        n = count_matches(doc, check["terms"])
        total = len(check["terms"])
        return min(pts, round(n / total * pts)) if total else pts
    if ctype == "regex":
        flags = re.MULTILINE if check.get("multiline", True) else 0
        return pts if re.search(check["pattern"], doc, flags) else 0
    if ctype == "word_range":
        wc = len(doc.split())
        return pts if check.get("min", 0) <= wc <= check.get("max", float("inf")) else 0
    if ctype == "headers":
        level = check.get("level", 2)
        count = len(re.findall(rf"^{'#' * level}\s+", doc, re.MULTILINE))
        return pts if count >= check.get("min", 1) else 0
    if ctype == "code_blocks":
        count = len(re.findall(r"```", doc)) // 2
        return pts if count >= check.get("min", 1) else 0
    if ctype == "ordered":
        return pts if terms_in_order(doc, check["terms"]) else 0
    if ctype == "tiered":
        for tier in check["tiers"]:
            cond = tier.get("condition", "has_all")
            if cond == "has_all" and has_all(doc, tier["terms"]):
                return tier["score"]
            if cond == "has_any" and has_any(doc, tier["terms"]):
                return tier["score"]
            if cond == "regex" and re.search(tier["pattern"], doc, re.MULTILINE):
                return tier["score"]
            if cond == "count_of" and count_matches(doc, tier["terms"]) >= tier.get("min", 1):
                return tier["score"]
        return 0

    raise ValueError(f"Unknown check type: {ctype!r} in check {check['id']}")


# ── Main scoring ────────────────────────────────────────────────────────────

def run_eval() -> dict:
    cfg = load_config()
    target_path = REPO_ROOT / cfg.TARGET_FILE
    with open(target_path, encoding="utf-8") as f:
        doc = f.read()

    categories: dict[str, list[dict]] = {}
    for check in cfg.CHECKS:
        cat = check.get("cat", "uncategorized")
        result = {
            "id": check["id"],
            "name": check["name"],
            "max": check["pts"],
            "score": eval_check(check, doc),
        }
        categories.setdefault(cat, []).append(result)

    output_cats = {}
    total_score = 0
    total_max = 0
    for cat_name, results in categories.items():
        cat_score = sum(r["score"] for r in results)
        cat_max = sum(r["max"] for r in results)
        total_score += cat_score
        total_max += cat_max
        output_cats[cat_name] = {"score": cat_score, "max": cat_max, "checks": results}

    return {
        "target": cfg.TARGET_FILE,
        "goal": getattr(cfg, "GOAL", ""),
        "total_score": total_score,
        "total_max": total_max,
        "pct": round(total_score / total_max * 100, 1) if total_max > 0 else 0,
        "categories": output_cats,
    }


def print_report(result: dict) -> None:
    target = result["target"]
    goal = result.get("goal", "")
    print(f"\n{'=' * 60}")
    print(f"  AUTORESEARCH EVAL — {os.path.basename(target)}")
    if goal:
        print(f"  Goal: {goal[:55]}{'...' if len(goal) > 55 else ''}")
    print(f"{'=' * 60}")
    print(f"\n  TOTAL SCORE: {result['total_score']} / {result['total_max']} ({result['pct']}%)\n")

    for cat_name, cat_data in result["categories"].items():
        label = cat_name.replace("_", " ").title()
        print(f"  {label}: {cat_data['score']}/{cat_data['max']}")
        for check in cat_data["checks"]:
            icon = "✅" if check["score"] == check["max"] else ("⚠️" if check["score"] > 0 else "❌")
            print(f"    {icon} [{check['id']}] {check['name']}: {check['score']}/{check['max']}")
        print()


# ── Results logging ─────────────────────────────────────────────────────────

def get_last_score() -> float:
    """Read the last score from results.tsv."""
    if not RESULTS_PATH.exists():
        return 0.0
    with open(RESULTS_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) < 2:
        return 0.0
    last = lines[-1].strip().split("\t")
    return float(last[1]) if len(last) >= 2 else 0.0


def get_iteration_count() -> int:
    """Count iterations in results.tsv."""
    if not RESULTS_PATH.exists():
        return 0
    with open(RESULTS_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    return max(0, len(lines) - 1)  # subtract header


def log_result(result: dict, description: str, status: str = "auto") -> None:
    """Append a row to results.tsv."""
    prev = get_last_score()
    iteration = get_iteration_count()
    score = result["total_score"]
    delta = score - prev

    if status == "auto":
        status = "keep" if delta > 0 else ("same" if delta == 0 else "revert")

    if not RESULTS_PATH.exists():
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            f.write("iteration\tscore\tmax\tpct\tdelta\tstatus\tdescription\n")

    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(f"{iteration}\t{score}\t{result['total_max']}\t{result['pct']}\t{delta:+.1f}\t{status}\t{description}\n")


def print_results_summary() -> None:
    """Print a summary of all iterations from results.tsv."""
    if not RESULTS_PATH.exists():
        print("  No results yet. Run setup first: python autoresearch/setup.py")
        return

    with open(RESULTS_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    if len(lines) < 2:
        print("  No results yet.")
        return

    print(f"\n{'=' * 60}")
    print(f"  AUTORESEARCH RESULTS")
    print(f"{'=' * 60}\n")

    # Parse rows
    rows = []
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

    # Print table
    print(f"  {'#':>3}  {'Score':>7}  {'Δ':>6}  {'Status':<8}  Description")
    print(f"  {'─' * 3}  {'─' * 7}  {'─' * 6}  {'─' * 8}  {'─' * 30}")
    for r in rows:
        icon = {"baseline": "📊", "keep": "✅", "revert": "↩️", "same": "➖"}.get(r["status"], "•")
        print(f"  {r['iteration']:>3}  {r['score']:>4}/{r['max']:<3} {r['delta']:>6}  {icon} {r['status']:<6}  {r['description']}")

    # Summary
    baseline = rows[0] if rows else None
    kept = [r for r in rows if r["status"] == "keep"]
    reverted = [r for r in rows if r["status"] == "revert"]
    latest = rows[-1] if rows else None

    print(f"\n  {'─' * 55}")
    if baseline and latest:
        print(f"  Baseline:  {baseline['score']}/{baseline['max']} ({baseline['pct']}%)")
        print(f"  Current:   {latest['score']}/{latest['max']} ({latest['pct']}%)")
    print(f"  Kept:      {len(kept)} improvements")
    print(f"  Reverted:  {len(reverted)} experiments")
    print(f"  Total:     {len(rows)} iterations\n")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--results" in sys.argv:
        print_results_summary()
    elif "--json" in sys.argv:
        print(json.dumps(run_eval(), indent=2))
    elif "--log" in sys.argv:
        idx = sys.argv.index("--log")
        desc = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "no description"
        result = run_eval()
        log_result(result, desc)
        print(f"Score: {result['total_score']}/{result['total_max']} ({result['pct']}%) — logged to results.tsv")
    else:
        result = run_eval()
        print_report(result)
