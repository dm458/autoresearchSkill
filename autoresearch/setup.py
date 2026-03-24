#!/usr/bin/env python3
"""
Autoresearch Setup — Interactive configuration generator.

Scans your skill file and source code, then generates a scoring config
that the autoresearch loop uses to iteratively improve the skill file.

Usage:
    python autoresearch/setup.py                    # interactive wizard
    python autoresearch/setup.py --skill path.md    # skip skill prompt
    python autoresearch/setup.py --non-interactive  # use defaults from existing config
"""

import argparse
import ast
import json
import os
import re
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.py"
RESULTS_PATH = Path(__file__).resolve().parent / "results.tsv"

# ── Source code scanner ─────────────────────────────────────────────────────

def scan_python_file(path: str) -> dict:
    """Extract key symbols from a Python file."""
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except Exception:
        return {"functions": [], "classes": [], "constants": [], "imports": []}

    functions = []
    classes = []
    constants = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not node.name.startswith("_"):
                functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])

    return {
        "functions": list(set(functions)),
        "classes": list(set(classes)),
        "constants": list(set(constants)),
        "imports": list(set(imports)),
    }


def scan_source_files(paths: list[str]) -> dict:
    """Aggregate symbols across all source files."""
    all_funcs, all_classes, all_consts, all_imports = [], [], [], []
    for p in paths:
        full = os.path.join(REPO_ROOT, p)
        if not os.path.exists(full):
            continue
        info = scan_python_file(full)
        all_funcs.extend(info["functions"])
        all_classes.extend(info["classes"])
        all_consts.extend(info["constants"])
        all_imports.extend(info["imports"])
    return {
        "functions": sorted(set(all_funcs)),
        "classes": sorted(set(all_classes)),
        "constants": sorted(set(all_consts)),
        "imports": sorted(set(all_imports)),
    }


def find_source_files(skill_dir: str) -> list[str]:
    """Auto-detect source files near the skill file."""
    candidates = []
    for root, dirs, files in os.walk(REPO_ROOT):
        # Skip hidden dirs and common non-source dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                   {"node_modules", "__pycache__", "venv", ".venv", "dist", "build", "autoresearch"}]
        for f in files:
            if f.endswith((".py", ".ts", ".js", ".go", ".rs", ".java")):
                rel = os.path.relpath(os.path.join(root, f), REPO_ROOT)
                candidates.append(rel.replace("\\", "/"))
    return sorted(candidates)[:20]  # cap at 20


# ── Check generators ────────────────────────────────────────────────────────

def generate_structure_checks() -> list[dict]:
    """Universal structure checks — apply to any skill file."""
    return [
        {"id": "s1",  "cat": "structure", "name": "Has clear title",                  "pts": 2, "type": "regex",       "pattern": r"^#\s+.+"},
        {"id": "s2",  "cat": "structure", "name": "Well-organized sections (≥4 ##)",   "pts": 2, "type": "headers",     "min": 4},
        {"id": "s3",  "cat": "structure", "name": "Has code examples (≥2 blocks)",     "pts": 3, "type": "code_blocks", "min": 2},
        {"id": "s4",  "cat": "structure", "name": "Appropriate length (800–10000w)",   "pts": 2, "type": "word_range",  "min": 800, "max": 10000},
        {"id": "s5",  "cat": "structure", "name": "Uses bold formatting",              "pts": 1, "type": "has_any",     "terms": ["**"]},
        {"id": "s6",  "cat": "structure", "name": "Uses lists",                        "pts": 1, "type": "regex",       "pattern": r"^[\-\*]\s|^\d+\.\s"},
        {"id": "s7",  "cat": "structure", "name": "Has section dividers",              "pts": 1, "type": "regex",       "pattern": r"^---"},
    ]


def generate_coverage_checks(symbols: dict) -> list[dict]:
    """Generate checks that verify the skill file mentions key source symbols."""
    checks = []
    idx = 1

    # Top functions (up to 10)
    top_funcs = symbols["functions"][:10]
    if top_funcs:
        checks.append({
            "id": f"cov{idx}", "cat": "coverage",
            "name": f"Mentions key functions ({len(top_funcs)} found in source)",
            "pts": min(5, len(top_funcs)),
            "type": "count_of",
            "terms": top_funcs,
        })
        idx += 1

    # Classes
    if symbols["classes"]:
        checks.append({
            "id": f"cov{idx}", "cat": "coverage",
            "name": f"Mentions key classes ({len(symbols['classes'])} found)",
            "pts": min(3, len(symbols["classes"])),
            "type": "count_of",
            "terms": symbols["classes"][:5],
        })
        idx += 1

    # Constants (often important config)
    if symbols["constants"]:
        checks.append({
            "id": f"cov{idx}", "cat": "coverage",
            "name": f"Mentions key constants",
            "pts": min(3, len(symbols["constants"])),
            "type": "count_of",
            "terms": symbols["constants"][:5],
        })
        idx += 1

    # Key imports (libraries)
    important_imports = [i for i in symbols["imports"]
                        if i not in {"os", "sys", "re", "json", "typing", "io", "pathlib", "logging", "collections"}]
    if important_imports:
        checks.append({
            "id": f"cov{idx}", "cat": "coverage",
            "name": f"Mentions key libraries",
            "pts": min(4, len(important_imports)),
            "type": "count_of",
            "terms": important_imports[:8],
        })
        idx += 1

    return checks


def generate_goal_checks(goal: str) -> list[dict]:
    """Parse the goal for keywords and generate targeted checks."""
    checks = []
    goal_lower = goal.lower()
    idx = 1

    # Common goal patterns → check templates
    patterns = [
        (["accuracy", "accurate", "correct", "match"],
         {"name": "Content is accurate", "terms": ["correct", "accurate"]}),
        (["complete", "comprehensive", "cover", "missing"],
         {"name": "Comprehensive coverage", "terms": ["complete", "cover"]}),
        (["clear", "clarity", "readable", "understandable"],
         {"name": "Clear and readable", "terms": ["clear"]}),
        (["example", "code example", "snippet"],
         {"name": "Includes practical examples", "terms": ["example"]}),
        (["beginner", "non-technical", "simple", "plain language"],
         {"name": "Accessible to target audience", "terms": ["plain language", "non-technical", "simple"]}),
        (["error", "edge case", "handle", "robust"],
         {"name": "Covers error handling / edge cases", "terms": ["error", "edge case"]}),
        (["workflow", "step", "process", "guide"],
         {"name": "Describes clear workflow steps", "terms": ["step", "workflow"]}),
        (["api", "interface", "function", "method"],
         {"name": "Documents key APIs / interfaces", "terms": ["api", "function", "method"]}),
        (["test", "testing", "verify", "validate"],
         {"name": "Includes testing guidance", "terms": ["test", "verify"]}),
        (["security", "auth", "permission"],
         {"name": "Addresses security concerns", "terms": ["security", "auth"]}),
        (["performance", "fast", "optimize", "efficient"],
         {"name": "Covers performance considerations", "terms": ["performance", "optimize"]}),
    ]

    for keywords, template in patterns:
        if any(k in goal_lower for k in keywords):
            checks.append({
                "id": f"goal{idx}", "cat": "goal",
                "name": template["name"],
                "pts": 3,
                "type": "has_any",
                "terms": template["terms"],
            })
            idx += 1

    # If no patterns matched, add generic quality checks
    if not checks:
        checks = [
            {"id": "goal1", "cat": "goal", "name": "Actionable guidance",
             "pts": 3, "type": "has_any", "terms": ["should", "must", "always", "never", "rule"]},
            {"id": "goal2", "cat": "goal", "name": "Includes examples",
             "pts": 3, "type": "code_blocks", "min": 1},
        ]

    return checks


# ── Config writer ───────────────────────────────────────────────────────────

def write_config(target: str, sources: list[str], goal: str, checks: list[dict]) -> None:
    """Write autoresearch/config.py."""
    # Format checks as Python literal
    checks_str = "[\n"
    current_cat = None
    for c in checks:
        if c["cat"] != current_cat:
            current_cat = c["cat"]
            checks_str += f"\n    # ── {current_cat.upper()} ──\n"
        checks_str += f"    {json.dumps(c)},\n"
    checks_str += "]"

    config_content = f'''"""
Autoresearch Eval Configuration — AUTO-GENERATED by setup.py

Target:  {target}
Goal:    {goal}
Sources: {', '.join(sources) if sources else 'none'}

To regenerate: python autoresearch/setup.py
To customize:  edit the CHECKS list below, then run: python autoresearch/eval.py
"""

TARGET_FILE = {json.dumps(target)}

SOURCE_FILES = {json.dumps(sources)}

GOAL = {json.dumps(goal)}

CHECKS = {checks_str}
'''
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(config_content)


# ── Interactive wizard ──────────────────────────────────────────────────────

def prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {question}{suffix}: ").strip()
    return answer or default


def prompt_choice(question: str, choices: list[str]) -> str:
    print(f"\n  {question}")
    for i, c in enumerate(choices, 1):
        print(f"    {i}) {c}")
    while True:
        answer = input(f"  Choice [1-{len(choices)}]: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        print(f"  Please enter a number 1-{len(choices)}")


def run_wizard(args) -> None:
    print("\n" + "=" * 60)
    print("  AUTORESEARCH SETUP")
    print("  Improve any skill / instruction file autonomously")
    print("=" * 60)

    # Step 1: Skill file
    print("\n─── STEP 1: Point to your skill file ───\n")
    if args.skill:
        target = args.skill
        print(f"  Skill file: {target}")
    else:
        # Try to auto-detect
        candidates = []
        for pattern in ["**/*.instructions.md", "**/*CLAUDE.md", "**/*AGENTS.md",
                        "**/*copilot-instructions.md", "**/*.md"]:
            for p in REPO_ROOT.glob(pattern):
                rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
                if "autoresearch" not in rel and "node_modules" not in rel:
                    candidates.append(rel)
        candidates = sorted(set(candidates))[:10]

        if candidates:
            print("  Found these instruction/skill files:")
            for i, c in enumerate(candidates, 1):
                print(f"    {i}) {c}")
            print(f"    {len(candidates) + 1}) Enter a different path")
            choice = input(f"\n  Which file? [1-{len(candidates) + 1}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                target = candidates[int(choice) - 1]
            else:
                target = prompt("Path to skill file (relative to repo root)")
        else:
            target = prompt("Path to skill file (relative to repo root)")

    if not os.path.exists(os.path.join(REPO_ROOT, target)):
        print(f"\n  ❌ File not found: {target}")
        sys.exit(1)
    print(f"  ✅ Found: {target}")

    # Step 2: Goal
    print("\n─── STEP 2: Define your goal ───\n")
    print("  What do you want to improve? Describe in plain language.")
    print("  Examples:")
    print("    • Make it more accurate against the actual codebase")
    print("    • Add missing sections about error handling and edge cases")
    print("    • Improve code examples to match real patterns")
    print("    • Make it clearer for non-technical users")
    if args.goal:
        goal = args.goal
        print(f"\n  Goal: {goal}")
    else:
        goal = prompt("\n  Your goal")

    if not goal:
        goal = "Improve accuracy, completeness, and clarity"
        print(f"  Using default: {goal}")

    # Step 3: Source files
    print("\n─── STEP 3: Source files (optional) ───\n")
    print("  Source files help verify the skill file matches your actual code.")
    sources_detected = find_source_files(str(REPO_ROOT))
    sources = []

    if args.sources:
        sources = args.sources
        print(f"  Using provided sources: {', '.join(sources)}")
    elif sources_detected:
        print(f"  Found {len(sources_detected)} source files:")
        for s in sources_detected[:10]:
            print(f"    • {s}")
        include = prompt("\n  Include these for accuracy checks? (y/n)", "y")
        if include.lower().startswith("y"):
            sources = sources_detected[:10]
    else:
        print("  No source files detected. Skipping accuracy checks.")

    # Step 4: Generate config
    print("\n─── GENERATING CONFIG ───\n")

    all_checks = []

    # Structure checks (universal)
    struct_checks = generate_structure_checks()
    all_checks.extend(struct_checks)
    print(f"  ✅ {len(struct_checks)} structure checks (universal)")

    # Coverage checks (from source scan)
    if sources:
        symbols = scan_source_files(sources)
        cov_checks = generate_coverage_checks(symbols)
        all_checks.extend(cov_checks)
        func_count = len(symbols["functions"])
        class_count = len(symbols["classes"])
        print(f"  ✅ {len(cov_checks)} coverage checks (scanned {func_count} functions, {class_count} classes)")
    else:
        print("  ⏭️  Skipping coverage checks (no source files)")

    # Goal checks
    goal_checks = generate_goal_checks(goal)
    all_checks.extend(goal_checks)
    print(f"  ✅ {len(goal_checks)} goal-based checks")

    total_pts = sum(c["pts"] for c in all_checks)
    print(f"\n  Total: {len(all_checks)} checks, {total_pts} points max")

    # Write config
    write_config(target, sources, goal, all_checks)
    print(f"  📝 Config written to: autoresearch/config.py")

    # Step 5: Baseline
    print("\n─── BASELINE SCORE ───\n")
    # Import and run eval
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from eval import run_eval, print_report
    result = run_eval()
    print_report(result)

    # Initialize results.tsv
    if not RESULTS_PATH.exists():
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            f.write("iteration\tscore\tmax\tpct\tdelta\tstatus\tdescription\n")
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        f.write(f"0\t{result['total_score']}\t{result['total_max']}\t{result['pct']}\t0.0\tbaseline\tinitial state\n")

    print(f"\n  Baseline: {result['total_score']}/{result['total_max']} ({result['pct']}%)")
    print(f"  Results log: autoresearch/results.tsv")

    # Step 6: Ready
    print("\n" + "=" * 60)
    print("  ✅ SETUP COMPLETE")
    print("=" * 60)
    print(f"""
  Your autoresearch is ready to run. Next steps:

  Option A — Run with a coding agent:
    Open this repo in Claude Code, Copilot CLI, or Cursor and say:
    "Read autoresearch/program.md and follow the instructions."

  Option B — Run manually:
    Edit {target}, then: python autoresearch/eval.py
    If score improved: git commit. If not: git checkout.

  Tip: Add --iterations N to program.md to limit rounds.
""")


def main():
    parser = argparse.ArgumentParser(
        description="Autoresearch Setup — generate eval config for your skill file"
    )
    parser.add_argument("--skill", help="Path to skill/instruction file (relative to repo root)")
    parser.add_argument("--goal", help="Improvement goal (plain language)")
    parser.add_argument("--sources", nargs="*", help="Source files for accuracy checks")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Use existing config without prompting")
    args = parser.parse_args()

    if args.non_interactive:
        if CONFIG_PATH.exists():
            print("Using existing config.py")
            sys.exit(0)
        else:
            print("No config.py found. Run without --non-interactive first.")
            sys.exit(1)

    run_wizard(args)


if __name__ == "__main__":
    main()
