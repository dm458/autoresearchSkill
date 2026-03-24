"""
Autoresearch Eval — Generic scoring engine for skill / instruction files.

Reads check definitions from config.py and scores the target file.
All checks are programmatic — no LLM calls required.

Usage:
    python autoresearch/eval.py            # pretty-print report
    python autoresearch/eval.py --json     # machine-readable JSON to stdout

THIS FILE IS READ-ONLY. The autoresearch agent must NOT modify it.
To change scoring criteria, edit config.py instead.
"""

import importlib.util
import json
import os
import re
import sys

# ── Load config ─────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")


def load_config():
    spec = importlib.util.spec_from_file_location("config", CONFIG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Text helpers ────────────────────────────────────────────────────────────

def _lower(text: str) -> str:
    return text.lower()


def has_all(text: str, terms: list[str]) -> bool:
    """True if ALL terms appear (case-insensitive)."""
    lo = _lower(text)
    return all(_lower(t) in lo for t in terms)


def has_any(text: str, terms: list[str]) -> bool:
    """True if ANY term appears (case-insensitive)."""
    lo = _lower(text)
    return any(_lower(t) in lo for t in terms)


def count_matches(text: str, terms: list[str]) -> int:
    """How many of the terms appear (case-insensitive)."""
    lo = _lower(text)
    return sum(1 for t in terms if _lower(t) in lo)


def terms_in_order(text: str, terms: list[str]) -> bool:
    """True if terms appear in the given order (first occurrence of each)."""
    lo = _lower(text)
    positions = [lo.find(_lower(t)) for t in terms]
    found = [p for p in positions if p >= 0]
    return len(found) >= 2 and all(found[i] < found[i + 1] for i in range(len(found) - 1))


# ── Check evaluators ───────────────────────────────────────────────────────
# Each returns an integer score (0 … check["pts"]).

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
        # Proportional scoring, rounded up at ≥50%
        if total == 0:
            return pts
        frac = n / total
        return min(pts, round(frac * pts))

    if ctype == "regex":
        flags = re.MULTILINE if check.get("multiline", True) else 0
        return pts if re.search(check["pattern"], doc, flags) else 0

    if ctype == "word_range":
        wc = len(doc.split())
        lo, hi = check.get("min", 0), check.get("max", float("inf"))
        return pts if lo <= wc <= hi else 0

    if ctype == "headers":
        level = check.get("level", 2)
        pattern = rf"^{'#' * level}\s+"
        count = len(re.findall(pattern, doc, re.MULTILINE))
        return pts if count >= check.get("min", 1) else 0

    if ctype == "code_blocks":
        count = len(re.findall(r"```", doc)) // 2
        return pts if count >= check.get("min", 1) else 0

    if ctype == "ordered":
        return pts if terms_in_order(doc, check["terms"]) else 0

    if ctype == "tiered":
        # Evaluate tiers top-down; return first match
        for tier in check["tiers"]:
            tier_type = tier.get("condition", "has_all")
            if tier_type == "has_all" and has_all(doc, tier["terms"]):
                return tier["score"]
            if tier_type == "has_any" and has_any(doc, tier["terms"]):
                return tier["score"]
            if tier_type == "regex" and re.search(tier["pattern"], doc, re.MULTILINE):
                return tier["score"]
            if tier_type == "count_of":
                n = count_matches(doc, tier["terms"])
                if n >= tier.get("min", 1):
                    return tier["score"]
        return 0

    raise ValueError(f"Unknown check type: {ctype!r} in check {check['id']}")


# ── Main ────────────────────────────────────────────────────────────────────

def run_eval() -> dict:
    cfg = load_config()
    target_path = os.path.join(REPO_ROOT, cfg.TARGET_FILE)
    with open(target_path, encoding="utf-8") as f:
        doc = f.read()

    # Optionally load source files (some configs don't need them)
    sources = {}
    for src in getattr(cfg, "SOURCE_FILES", []):
        path = os.path.join(REPO_ROOT, src)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                sources[src] = f.read()

    checks = cfg.CHECKS
    categories: dict[str, list[dict]] = {}
    for check in checks:
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
        "total_score": total_score,
        "total_max": total_max,
        "pct": round(total_score / total_max * 100, 1) if total_max > 0 else 0,
        "categories": output_cats,
    }


def print_report(result: dict) -> None:
    target = result["target"]
    print(f"\n{'=' * 60}")
    print(f"  AUTORESEARCH EVAL — {os.path.basename(target)}")
    print(f"{'=' * 60}")
    print(f"\n  TOTAL SCORE: {result['total_score']} / {result['total_max']} ({result['pct']}%)\n")

    for cat_name, cat_data in result["categories"].items():
        label = cat_name.replace("_", " ").title()
        print(f"  {label}: {cat_data['score']}/{cat_data['max']}")
        for check in cat_data["checks"]:
            icon = "✅" if check["score"] == check["max"] else ("⚠️" if check["score"] > 0 else "❌")
            print(f"    {icon} [{check['id']}] {check['name']}: {check['score']}/{check['max']}")
        print()


if __name__ == "__main__":
    result = run_eval()

    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
        # Also print JSON to stderr for programmatic use
        print(json.dumps(result), file=sys.stderr)
