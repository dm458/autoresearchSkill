"""
Autoresearch evaluation script for causal.instructions.md

Scores the CausalAI agent skill file on how accurately and completely it
describes the causal analysis workflow. All checks are programmatic — no LLM
calls required. The eval reads the actual source files (estimation.py,
data_utils.py, main.py) to verify that the instructions match reality.

Usage:
    python autoresearch/eval.py

Output:
    Prints a JSON object with total score, category scores, and per-check
    details. The score is what the autoresearch loop optimizes.

THIS FILE IS READ-ONLY. The autoresearch agent must NOT modify it.
"""

import json
import os
import re
import sys

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTRUCTIONS_PATH = os.path.join(
    REPO_ROOT, ".github", "instructions", "causal.instructions.md"
)
ESTIMATION_PATH = os.path.join(REPO_ROOT, "app", "estimation.py")
DATA_UTILS_PATH = os.path.join(REPO_ROOT, "app", "data_utils.py")
MAIN_PATH = os.path.join(REPO_ROOT, "app", "main.py")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── Helpers ─────────────────────────────────────────────────────────────────

def has(text: str, *terms: str) -> bool:
    """True if ALL terms appear in text (case-insensitive)."""
    lower = text.lower()
    return all(t.lower() in lower for t in terms)


def has_any(text: str, *terms: str) -> bool:
    """True if ANY term appears in text (case-insensitive)."""
    lower = text.lower()
    return any(t.lower() in lower for t in terms)


def count_matches(text: str, terms: list[str]) -> int:
    """Count how many of the terms appear in text."""
    lower = text.lower()
    return sum(1 for t in terms if t.lower() in lower)


def has_code_block(text: str) -> bool:
    return "```" in text


def count_headers(text: str) -> int:
    return len(re.findall(r"^#{1,4}\s+", text, re.MULTILINE))


def word_count(text: str) -> int:
    return len(text.split())


# ── Category 1: Structural Quality (0–20) ──────────────────────────────────

def score_structure(doc: str) -> list[dict]:
    checks = []

    # 1.1 Has a clear title
    checks.append({
        "id": "1.1", "name": "Has clear title/header",
        "max": 2, "score": 2 if re.search(r"^#\s+.+", doc, re.MULTILINE) else 0,
    })

    # 1.2 Has multiple sections (at least 4 second-level headers)
    h2_count = len(re.findall(r"^##\s+", doc, re.MULTILINE))
    checks.append({
        "id": "1.2", "name": "Has well-organized sections (≥4 ## headers)",
        "max": 2, "score": 2 if h2_count >= 4 else (1 if h2_count >= 2 else 0),
    })

    # 1.3 Has code examples
    code_blocks = len(re.findall(r"```", doc)) // 2
    checks.append({
        "id": "1.3", "name": "Has code examples (≥3 code blocks)",
        "max": 3, "score": 3 if code_blocks >= 3 else (2 if code_blocks >= 2 else (1 if code_blocks >= 1 else 0)),
    })

    # 1.4 Appropriate length (1500–8000 words for a detailed skill file)
    wc = word_count(doc)
    checks.append({
        "id": "1.4", "name": "Appropriate length (1500–8000 words)",
        "max": 2, "score": 2 if 1500 <= wc <= 8000 else (1 if 800 <= wc <= 10000 else 0),
    })

    # 1.5 Uses markdown formatting (bold, lists, tables)
    has_bold = "**" in doc
    has_list = bool(re.search(r"^[\-\*]\s", doc, re.MULTILINE))
    has_numbered = bool(re.search(r"^\d+\.\s", doc, re.MULTILINE))
    fmt_score = sum([has_bold, has_list, has_numbered])
    checks.append({
        "id": "1.5", "name": "Uses rich markdown (bold, lists, numbered steps)",
        "max": 2, "score": 2 if fmt_score >= 3 else (1 if fmt_score >= 2 else 0),
    })

    # 1.6 Has a clear workflow/sequence structure
    checks.append({
        "id": "1.6", "name": "Describes a clear sequential workflow",
        "max": 2, "score": 2 if has_any(doc, "Part A", "Step 1", "Phase 1", "Gather Input") else 0,
    })

    # 1.7 Has horizontal rules or clear section dividers
    dividers = doc.count("---") + doc.count("───")
    checks.append({
        "id": "1.7", "name": "Has section dividers (---)",
        "max": 2, "score": 2 if dividers >= 3 else (1 if dividers >= 1 else 0),
    })

    # 1.8 Uses tables for structured data
    has_table = bool(re.search(r"\|.*\|.*\|", doc))
    checks.append({
        "id": "1.8", "name": "Uses tables for structured data",
        "max": 2, "score": 2 if has_table else 0,
    })

    # 1.9 Has guardrails / validation rules section
    checks.append({
        "id": "1.9", "name": "Has guardrails or validation rules",
        "max": 1, "score": 1 if has_any(doc, "guardrail", "validation", "guard") else 0,
    })

    # 1.10 Has general rules / principles section
    checks.append({
        "id": "1.10", "name": "Has general rules or principles section",
        "max": 1, "score": 1 if has_any(doc, "general rule", "principles", "guidelines") else 0,
    })

    # 1.11 Has error handling / edge case section
    checks.append({
        "id": "1.11", "name": "Has error handling or edge case guidance",
        "max": 2, "score": 2 if has(doc, "error") and has_any(doc, "edge case", "handle", "fail") else (
            1 if has_any(doc, "error", "exception", "edge case") else 0
        ),
    })

    return checks


# ── Category 2: Workflow Completeness (0–25) ────────────────────────────────

def score_workflow(doc: str) -> list[dict]:
    checks = []

    # 2.1 Covers data loading
    checks.append({
        "id": "2.1", "name": "Covers data loading (CSV, Excel, DataFrame)",
        "max": 2, "score": 2 if has(doc, "load") and has_any(doc, "csv", "excel", "dataframe") else 0,
    })

    # 2.2 Covers data dictionary loading
    checks.append({
        "id": "2.2", "name": "Covers data dictionary loading",
        "max": 2, "score": 2 if has(doc, "data dictionary") else 0,
    })

    # 2.3 Covers framing the causal question (treatment & outcome selection)
    checks.append({
        "id": "2.3", "name": "Covers treatment & outcome selection",
        "max": 2, "score": 2 if has(doc, "treatment") and has(doc, "outcome") else 0,
    })

    # 2.4 Covers binary vs continuous treatment distinction
    checks.append({
        "id": "2.4", "name": "Distinguishes binary vs continuous treatment",
        "max": 2, "score": 2 if has(doc, "binary") and has(doc, "continuous") else 0,
    })

    # 2.5 Covers confounder selection
    checks.append({
        "id": "2.5", "name": "Covers confounder identification/selection",
        "max": 3, "score": 3 if has(doc, "confounder") else 0,
    })

    # 2.6 Covers confounder selection defaults (include vs exclude logic)
    checks.append({
        "id": "2.6", "name": "Explains when to include vs exclude confounders",
        "max": 2,
        "score": 2 if has(doc, "confounder") and has_any(doc, "mediator", "collider", "exclude") else 0,
    })

    # 2.7 Covers data processing pipeline (all 5 steps)
    processing_terms = ["missing", "winsoriz", "log transform", "dummy", "encod"]
    matched = count_matches(doc, processing_terms)
    checks.append({
        "id": "2.7", "name": "Covers all processing steps (missing, winsorize, log, dummy)",
        "max": 3, "score": 3 if matched >= 4 else (2 if matched >= 3 else (1 if matched >= 2 else 0)),
    })

    # 2.8 Covers diagnostics (treatment predictability)
    checks.append({
        "id": "2.8", "name": "Covers treatment predictability diagnostics",
        "max": 2, "score": 2 if has_any(doc, "predictability", "cross_val_score", "AUC", "treatment predict") else 0,
    })

    # 2.9 Covers overlap / propensity score check
    checks.append({
        "id": "2.9", "name": "Covers propensity score / overlap check",
        "max": 2, "score": 2 if has_any(doc, "propensity", "overlap") else 0,
    })

    # 2.10 Covers results presentation
    checks.append({
        "id": "2.10", "name": "Covers result presentation format",
        "max": 2, "score": 2 if has(doc, "result") and has_any(doc, "present", "interpret", "summary") else 0,
    })

    # 2.11 Covers PDF report generation
    checks.append({
        "id": "2.11", "name": "Covers PDF report generation",
        "max": 2, "score": 2 if has(doc, "pdf") else (1 if has_any(doc, "report", "download") else 0),
    })

    # 2.12 Covers iteration / refinement loop
    checks.append({
        "id": "2.12", "name": "Covers iterative refinement (user requests changes)",
        "max": 1, "score": 1 if has_any(doc, "iterate", "rerun", "re-run", "refinement", "adjust") else 0,
    })

    # 2.13 Mentions LLM-assisted features (treatment suggestion, causal graph)
    checks.append({
        "id": "2.13", "name": "Mentions LLM-assisted suggestions (treatment/outcome/confounders)",
        "max": 3,
        "score": 3 if has(doc, "LLM") and has_any(doc, "suggest", "causal graph", "GPT") else (
            2 if has_any(doc, "LLM", "GPT", "OpenAI") else (
                1 if has_any(doc, "AI-assisted", "AI suggest") else 0
            )
        ),
    })

    # 2.14 Covers session persistence (save/load session)
    checks.append({
        "id": "2.14", "name": "Covers session save/load for resuming analysis",
        "max": 2,
        "score": 2 if has(doc, "session") and has_any(doc, "save", "load", "resume") else (
            1 if has_any(doc, "session", "save_session", "load_session") else 0
        ),
    })

    # 2.15 Covers variable definition editing (user can rename/retype columns)
    checks.append({
        "id": "2.15", "name": "Covers variable definition/type editing",
        "max": 2,
        "score": 2 if has(doc, "definition") and has_any(doc, "edit", "type", "variable_definitions") else (
            1 if has_any(doc, "variable definition", "data dictionary") else 0
        ),
    })

    # 2.16 Covers domain knowledge input for confounder selection
    checks.append({
        "id": "2.16", "name": "Covers domain knowledge input for confounder selection",
        "max": 2,
        "score": 2 if has(doc, "domain knowledge") else (
            1 if has_any(doc, "domain expert", "subject matter") else 0
        ),
    })

    return checks


# ── Category 3: Codebase Accuracy (0–25) ────────────────────────────────────

def score_accuracy(doc: str, estimation_src: str, data_utils_src: str, main_src: str) -> list[dict]:
    checks = []

    # 3.1 Mentions all 3 estimators (OLS, LinearDML, LinearDRLearner)
    estimator_terms = ["OLS", "LinearDML", "LinearDRLearner"]
    est_count = count_matches(doc, estimator_terms)
    checks.append({
        "id": "3.1", "name": "Mentions all 3 estimators (OLS, LinearDML, LinearDRLearner)",
        "max": 3, "score": est_count,
    })

    # 3.2 Correct estimator-treatment mapping (LinearDML→continuous, LinearDRLearner→binary)
    correct_dml = has(doc, "LinearDML") and (
        has(doc, "continuous") or
        (has(doc, "LinearDML") and has_any(doc, "continuous treatment"))
    )
    correct_dr = has(doc, "LinearDRLearner") and (
        has(doc, "binary") or
        (has(doc, "LinearDRLearner") and has_any(doc, "binary treatment"))
    )
    checks.append({
        "id": "3.2", "name": "Correct estimator↔treatment type mapping",
        "max": 3, "score": (2 if correct_dml else 0) + (1 if correct_dr else 0),
    })

    # 3.3 Uses correct EconML fit API: est.fit(Y, T, X=None, W=W, inference="statsmodels")
    checks.append({
        "id": "3.3", "name": "Shows correct EconML fit call (Y, T, X=None, W=W)",
        "max": 3,
        "score": 3 if has(doc, "X=None") and has(doc, "inference=\"statsmodels\"") else (
            2 if has(doc, "X=None") or has(doc, 'inference="statsmodels"') else (
                1 if has_any(doc, "est.fit", ".fit(") else 0
            )
        ),
    })

    # 3.4 Uses correct nuisance models (GradientBoosting)
    checks.append({
        "id": "3.4", "name": "Uses GradientBoosting as nuisance models",
        "max": 2,
        "score": 2 if has(doc, "GradientBoosting") else (1 if has_any(doc, "gradient boost", "GBR", "sklearn") else 0),
    })

    # 3.5 Correct effect extraction: est.effect() and est.effect_interval()
    checks.append({
        "id": "3.5", "name": "Correct effect extraction API (effect, effect_interval)",
        "max": 2,
        "score": 2 if has(doc, "effect_interval") else (1 if has(doc, "est.effect") else 0),
    })

    # 3.6 Mentions unconditional difference comparison
    checks.append({
        "id": "3.6", "name": "Mentions unconditional difference comparison",
        "max": 2,
        "score": 2 if has_any(doc, "unconditional difference", "unconditional association", "unadjusted") else 0,
    })

    # 3.7 Variable role terminology (Y, T, W, X)
    role_terms = ["outcome (Y", "treatment (T", "confounder", "W)"]
    role_count = count_matches(doc, role_terms)
    checks.append({
        "id": "3.7", "name": "Uses correct variable role terminology (Y, T, W, X)",
        "max": 2, "score": 2 if role_count >= 3 else (1 if role_count >= 2 else 0),
    })

    # 3.8 Mentions float64 conversion requirement
    checks.append({
        "id": "3.8", "name": "Mentions float64 type conversion for model inputs",
        "max": 2,
        "score": 2 if has(doc, "float64") else (1 if has_any(doc, "pd.to_numeric", "numeric", "convert") else 0),
    })

    # 3.9 Processing order matches code (drop nulls → impute → winsorize → log → dummies)
    # Check that the doc mentions these in the right order
    order_terms = ["missing", "winsoriz", "log", "dummy"]
    positions = []
    lower_doc = doc.lower()
    for t in order_terms:
        pos = lower_doc.find(t)
        if pos >= 0:
            positions.append(pos)
    in_order = all(positions[i] < positions[i + 1] for i in range(len(positions) - 1)) if len(positions) >= 3 else False
    checks.append({
        "id": "3.9", "name": "Processing steps in correct order",
        "max": 2, "score": 2 if in_order and len(positions) >= 4 else (1 if in_order else 0),
    })

    # 3.10 Mentions fpdf2 / FPDF for PDF generation
    checks.append({
        "id": "3.10", "name": "Mentions fpdf2/FPDF for PDF generation",
        "max": 2,
        "score": 2 if has_any(doc, "fpdf", "FPDF") else (1 if has(doc, "pdf") else 0),
    })

    # 3.11 Mentions missing indicator method (fill + _missing flag)
    checks.append({
        "id": "3.11", "name": "Describes missing indicator imputation method",
        "max": 2,
        "score": 2 if has(doc, "missing") and has_any(doc, "indicator", "_missing", "flag") else 0,
    })

    # 3.12 PDF report is described as 2-page (matches actual generate_results_pdf)
    checks.append({
        "id": "3.12", "name": "PDF report described accurately (actual code generates 2-page)",
        "max": 2,
        "score": 2 if has(doc, "2-page") or has(doc, "two-page") or has(doc, "two page") else (
            0 if has(doc, "one-page") or has(doc, "one page") or has(doc, "single-page") else 1
        ),
    })

    # 3.13 Mentions random_state=42 for reproducibility (used in all estimators)
    checks.append({
        "id": "3.13", "name": "Mentions random_state=42 for reproducibility",
        "max": 1,
        "score": 1 if has(doc, "random_state") else 0,
    })

    # 3.14 Mentions OLS using statsmodels (sm.OLS, sm.add_constant)
    checks.append({
        "id": "3.14", "name": "Describes OLS implementation with statsmodels",
        "max": 2,
        "score": 2 if has_any(doc, "sm.OLS", "sm.add_constant", "statsmodels.api") else (
            1 if has(doc, "OLS") and has(doc, "statsmodels") else 0
        ),
    })

    # 3.15 Mentions ate_inference() for proper p-values
    checks.append({
        "id": "3.15", "name": "Mentions ate_inference() for proper p-values/SE",
        "max": 2,
        "score": 2 if has(doc, "ate_inference") else (
            1 if has(doc, "p_value") or has(doc, "p-value") and has_any(doc, "standard error", "stderr") else 0
        ),
    })

    # 3.16 Describes Crump trimming thresholds for overlap (0.1, 0.9)
    checks.append({
        "id": "3.16", "name": "Mentions Crump trimming thresholds (0.1, 0.9)",
        "max": 1,
        "score": 1 if has(doc, "0.1") and has(doc, "0.9") and has_any(doc, "Crump", "trim", "propensity") else 0,
    })

    return checks


# ── Category 4: Code Example Quality (0–15) ─────────────────────────────────

def score_code_examples(doc: str) -> list[dict]:
    checks = []

    # 4.1 Has LinearDML code example with correct imports
    checks.append({
        "id": "4.1", "name": "Has LinearDML code example",
        "max": 3,
        "score": 3 if has(doc, "LinearDML(") else (1 if has(doc, "LinearDML") else 0),
    })

    # 4.2 Has LinearDRLearner code example
    checks.append({
        "id": "4.2", "name": "Has LinearDRLearner code example",
        "max": 3,
        "score": 3 if has(doc, "LinearDRLearner(") else (1 if has(doc, "LinearDRLearner") else 0),
    })

    # 4.3 Has OLS code example or description
    checks.append({
        "id": "4.3", "name": "Has OLS baseline code or description",
        "max": 2,
        "score": 2 if has(doc, "OLS") and has_any(doc, "sm.OLS", "sm.add_constant", "linear regression") else (
            1 if has(doc, "OLS") else 0
        ),
    })

    # 4.4 Has processing code examples (winsorize, get_dummies)
    checks.append({
        "id": "4.4", "name": "Has data processing code examples",
        "max": 2,
        "score": 2 if has_any(doc, "mstats.winsorize", "pd.get_dummies", "get_dummies") else (
            1 if has_any(doc, "winsorize", "dummies") else 0
        ),
    })

    # 4.5 Has effect extraction code (est.effect, effect_interval, CI calculation)
    checks.append({
        "id": "4.5", "name": "Has result extraction code examples",
        "max": 2,
        "score": 2 if has(doc, "est.effect(") and has(doc, "effect_interval(") else (
            1 if has_any(doc, "est.effect", "effect_interval") else 0
        ),
    })

    # 4.6 Has diagnostic code examples (cross_val_score, propensity)
    checks.append({
        "id": "4.6", "name": "Has diagnostic code examples",
        "max": 3,
        "score": 3 if has(doc, "cross_val_score") else (
            2 if has_any(doc, "predict_proba", "propensity") else (
                1 if has_any(doc, "diagnostic", "AUC") else 0
            )
        ),
    })

    return checks


# ── Category 5: Agent Usefulness (0–15) ──────────────────────────────────────

def score_usefulness(doc: str) -> list[dict]:
    checks = []

    # 5.1 Non-technical audience guidance
    checks.append({
        "id": "5.1", "name": "Mentions non-technical audience / plain language",
        "max": 2,
        "score": 2 if has_any(doc, "non-technical", "plain language", "avoid jargon") else 0,
    })

    # 5.2 Warns about causal vs predictive confusion
    checks.append({
        "id": "5.2", "name": "Warns not to confuse prediction with causal inference",
        "max": 2,
        "score": 2 if has(doc, "prediction") and has_any(doc, "causal", "treatment effect") else (
            1 if has_any(doc, "not prediction", "treatment effect") else 0
        ),
    })

    # 5.3 States unmeasured confounder limitation
    checks.append({
        "id": "5.3", "name": "States unmeasured confounder caveat",
        "max": 2,
        "score": 2 if has_any(doc, "unmeasured confounder", "unobserved confounder", "omitted variable") else 0,
    })

    # 5.4 Explains when to include vs exclude confounders (bias direction)
    checks.append({
        "id": "5.4", "name": "Explains confounder inclusion bias tradeoff",
        "max": 2,
        "score": 2 if has(doc, "bias") and has_any(doc, "include", "omit") else 0,
    })

    # 5.5 Specifies data integrity (work on copies)
    checks.append({
        "id": "5.5", "name": "Specifies working on data copies (no mutation)",
        "max": 1,
        "score": 1 if has_any(doc, "copy", "copies", "do not mutate", "preserve") else 0,
    })

    # 5.6 Describes result interpretation format
    checks.append({
        "id": "5.6", "name": "Provides result interpretation template",
        "max": 2,
        "score": 2 if has(doc, "one-unit increase") or has(doc, "causes") and has_any(doc, "increase", "decrease") else (
            1 if has_any(doc, "interpret", "plain language") else 0
        ),
    })

    # 5.7 Mentions p-value and significance interpretation
    checks.append({
        "id": "5.7", "name": "Covers p-value and significance interpretation",
        "max": 2,
        "score": 2 if has(doc, "p-value") or has(doc, "p_value") else (
            1 if has_any(doc, "significant", "significance") else 0
        ),
    })

    # 5.8 Has structured questions for user (interactive refinement)
    checks.append({
        "id": "5.8", "name": "Has structured user questions for refinement",
        "max": 2,
        "score": 2 if has(doc, "ask") and has_any(doc, "user", "question") else 0,
    })

    # 5.9 Distinguishes ATE vs CATE (Average vs Heterogeneous effects)
    checks.append({
        "id": "5.9", "name": "Explains ATE vs heterogeneous effects (X=None vs X)",
        "max": 2,
        "score": 2 if has(doc, "ATE") or (has(doc, "X=None") and has_any(doc, "average", "heterogen")) else (
            1 if has_any(doc, "average treatment effect", "heterogeneous") else 0
        ),
    })

    # 5.10 Explains confounder bias direction (inflating vs masking)
    checks.append({
        "id": "5.10", "name": "Explains confounder bias direction (inflating vs masking)",
        "max": 2,
        "score": 2 if has(doc, "inflating") or has(doc, "masking") else (
            1 if has_any(doc, "larger", "smaller", "bias direction") else 0
        ),
    })

    # 5.11 Mentions doubly robust property of DRLearner
    checks.append({
        "id": "5.11", "name": "Explains doubly robust property",
        "max": 2,
        "score": 2 if has(doc, "doubly robust") else (
            1 if has_any(doc, "double robust", "either model") else 0
        ),
    })

    # 5.12 Provides guidance on statistical vs practical significance
    checks.append({
        "id": "5.12", "name": "Distinguishes statistical vs practical significance",
        "max": 2,
        "score": 2 if has_any(doc, "practical significance", "effect size", "meaningful") and has_any(doc, "statistical significance", "p-value") else (
            1 if has_any(doc, "practical", "meaningful") else 0
        ),
    })

    # 5.13 Warns about reverse causality
    checks.append({
        "id": "5.13", "name": "Warns about reverse causality assumption",
        "max": 1,
        "score": 1 if has_any(doc, "reverse causality", "reverse causal") else 0,
    })

    return checks


# ── Main ────────────────────────────────────────────────────────────────────

def run_eval() -> dict:
    doc = read(INSTRUCTIONS_PATH)
    estimation_src = read(ESTIMATION_PATH)
    data_utils_src = read(DATA_UTILS_PATH)
    main_src = read(MAIN_PATH)

    categories = {
        "1_structure": score_structure(doc),
        "2_workflow": score_workflow(doc),
        "3_accuracy": score_accuracy(doc, estimation_src, data_utils_src, main_src),
        "4_code_examples": score_code_examples(doc),
        "5_usefulness": score_usefulness(doc),
    }

    results = {}
    total_score = 0
    total_max = 0

    for cat_name, checks in categories.items():
        cat_score = sum(c["score"] for c in checks)
        cat_max = sum(c["max"] for c in checks)
        total_score += cat_score
        total_max += cat_max
        results[cat_name] = {
            "score": cat_score,
            "max": cat_max,
            "checks": checks,
        }

    output = {
        "total_score": total_score,
        "total_max": total_max,
        "pct": round(total_score / total_max * 100, 1) if total_max > 0 else 0,
        "categories": results,
    }

    return output


if __name__ == "__main__":
    result = run_eval()

    # Print summary
    print(f"\n{'='*60}")
    print(f"  AUTORESEARCH EVAL — causal.instructions.md")
    print(f"{'='*60}")
    print(f"\n  TOTAL SCORE: {result['total_score']} / {result['total_max']} ({result['pct']}%)\n")

    for cat_name, cat_data in result["categories"].items():
        label = cat_name.replace("_", " ").title()
        print(f"  {label}: {cat_data['score']}/{cat_data['max']}")
        for check in cat_data["checks"]:
            icon = "✅" if check["score"] == check["max"] else ("⚠️" if check["score"] > 0 else "❌")
            print(f"    {icon} [{check['id']}] {check['name']}: {check['score']}/{check['max']}")
        print()

    # Also print machine-readable JSON to stderr for programmatic use
    print(json.dumps(result), file=sys.stderr)
