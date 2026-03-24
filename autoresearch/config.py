"""
Autoresearch Eval Configuration

This file defines WHAT to score. Edit it for your skill file.
The engine (eval.py) defines HOW to score and must not be modified.

Quick start:
  1. Set TARGET_FILE to your skill / instructions file
  2. Set SOURCE_FILES to the code your skill describes (optional, for reference)
  3. Define CHECKS — each check awards points when the target file meets criteria

Run:  python autoresearch/eval.py
"""

# ── Target ──────────────────────────────────────────────────────────────────
# The file the autoresearch agent will iteratively improve.

TARGET_FILE = ".github/instructions/causal.instructions.md"

# ── Source files ────────────────────────────────────────────────────────────
# The source code your skill file describes. The agent reads these (read-only)
# to verify accuracy. Leave empty if not applicable.

SOURCE_FILES = [
    "app/main.py",
    "app/estimation.py",
    "app/data_utils.py",
]

# ── Check types reference ───────────────────────────────────────────────────
#
#   has_all     — ALL terms must appear (case-insensitive)          → full pts or 0
#   has_any     — ANY term must appear                              → full pts or 0
#   count_of    — proportional: score = (matched/total) × pts      → 0 … pts
#   regex       — regex pattern matches (multiline by default)      → full pts or 0
#   word_range  — word count in [min, max]                          → full pts or 0
#   headers     — ≥ min headings at given level (default ##)        → full pts or 0
#   code_blocks — ≥ min ``` code blocks                             → full pts or 0
#   ordered     — terms appear in this sequential order             → full pts or 0
#   tiered      — first matching tier wins (top-down)               → tier score or 0
#                 each tier: {score, condition, terms/pattern, [min]}
#
# Every check needs: id, cat (category name), name, pts, type
# Plus type-specific keys (terms, pattern, min, max, level, tiers).

CHECKS = [

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  STRUCTURE — Is the file well-organized and formatted?              ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    {"id": "s1",  "cat": "structure", "name": "Has clear title",                  "pts": 2, "type": "regex",       "pattern": r"^#\s+.+"},
    {"id": "s2",  "cat": "structure", "name": "Well-organized sections (≥4 ##)",   "pts": 2, "type": "headers",     "min": 4},
    {"id": "s3",  "cat": "structure", "name": "Has code examples (≥3 blocks)",     "pts": 3, "type": "code_blocks", "min": 3},
    {"id": "s4",  "cat": "structure", "name": "Appropriate length (1500–8000w)",   "pts": 2, "type": "word_range",  "min": 1500, "max": 8000},
    {"id": "s5",  "cat": "structure", "name": "Uses bold formatting",              "pts": 1, "type": "has_any",     "terms": ["**"]},
    {"id": "s6",  "cat": "structure", "name": "Uses bullet/numbered lists",        "pts": 1, "type": "regex",       "pattern": r"^[\-\*]\s|^\d+\.\s"},
    {"id": "s7",  "cat": "structure", "name": "Has sequential workflow structure", "pts": 2, "type": "has_any",     "terms": ["Part A", "Step 1", "Phase 1", "Gather Input"]},
    {"id": "s8",  "cat": "structure", "name": "Has section dividers (---)",        "pts": 2, "type": "regex",       "pattern": r"^---"},
    {"id": "s9",  "cat": "structure", "name": "Uses tables",                       "pts": 2, "type": "regex",       "pattern": r"\|.*\|.*\|"},
    {"id": "s10", "cat": "structure", "name": "Has guardrails/validation rules",   "pts": 1, "type": "has_any",     "terms": ["guardrail", "validation", "guard"]},
    {"id": "s11", "cat": "structure", "name": "Has general rules section",         "pts": 1, "type": "has_any",     "terms": ["general rule", "principles", "guidelines"]},
    {"id": "s12", "cat": "structure", "name": "Has error handling guidance",       "pts": 2, "type": "has_all",     "terms": ["error"]},

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  WORKFLOW — Does it cover all steps of the analysis?                ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    {"id": "w1",  "cat": "workflow", "name": "Covers data loading",                    "pts": 2, "type": "has_all",  "terms": ["load", "csv"]},
    {"id": "w2",  "cat": "workflow", "name": "Covers data dictionary",                 "pts": 2, "type": "has_all",  "terms": ["data dictionary"]},
    {"id": "w3",  "cat": "workflow", "name": "Covers treatment & outcome selection",   "pts": 2, "type": "has_all",  "terms": ["treatment", "outcome"]},
    {"id": "w4",  "cat": "workflow", "name": "Distinguishes binary vs continuous",     "pts": 2, "type": "has_all",  "terms": ["binary", "continuous"]},
    {"id": "w5",  "cat": "workflow", "name": "Covers confounder selection",            "pts": 3, "type": "has_any",  "terms": ["confounder"]},
    {"id": "w6",  "cat": "workflow", "name": "Explains include vs exclude confounders","pts": 2, "type": "has_all",  "terms": ["confounder", "exclude"]},
    {"id": "w7",  "cat": "workflow", "name": "Covers all processing steps",            "pts": 3, "type": "count_of", "terms": ["missing", "winsoriz", "log transform", "dummy", "encod"]},
    {"id": "w8",  "cat": "workflow", "name": "Covers treatment predictability check",  "pts": 2, "type": "has_any",  "terms": ["predictability", "cross_val_score", "AUC", "treatment predict"]},
    {"id": "w9",  "cat": "workflow", "name": "Covers propensity/overlap check",        "pts": 2, "type": "has_any",  "terms": ["propensity", "overlap"]},
    {"id": "w10", "cat": "workflow", "name": "Covers result presentation",             "pts": 2, "type": "has_all",  "terms": ["result"]},
    {"id": "w11", "cat": "workflow", "name": "Covers PDF report generation",           "pts": 2, "type": "has_any",  "terms": ["pdf", "report"]},
    {"id": "w12", "cat": "workflow", "name": "Covers iterative refinement",            "pts": 1, "type": "has_any",  "terms": ["iterate", "rerun", "re-run", "refinement", "adjust"]},
    {"id": "w13", "cat": "workflow", "name": "Mentions LLM-assisted suggestions",      "pts": 3, "type": "tiered",   "tiers": [
        {"score": 3, "condition": "has_all",  "terms": ["LLM", "suggest"]},
        {"score": 2, "condition": "has_any",  "terms": ["LLM", "GPT", "OpenAI"]},
        {"score": 1, "condition": "has_any",  "terms": ["AI-assisted", "AI suggest"]},
    ]},
    {"id": "w14", "cat": "workflow", "name": "Covers session save/load",               "pts": 2, "type": "has_all",  "terms": ["session", "save"]},
    {"id": "w15", "cat": "workflow", "name": "Covers variable definition editing",     "pts": 2, "type": "tiered",  "tiers": [
        {"score": 2, "condition": "has_all",  "terms": ["definition", "edit"]},
        {"score": 1, "condition": "has_any",  "terms": ["variable definition", "variable_definitions", "data dictionary"]},
    ]},
    {"id": "w16", "cat": "workflow", "name": "Covers domain knowledge input",          "pts": 2, "type": "has_any",  "terms": ["domain knowledge", "domain expert", "subject matter"]},

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  ACCURACY — Does it match what the code actually does?              ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    {"id": "a1",  "cat": "accuracy", "name": "Mentions all 3 estimators",             "pts": 3, "type": "count_of", "terms": ["OLS", "LinearDML", "LinearDRLearner"]},
    {"id": "a2",  "cat": "accuracy", "name": "Correct estimator↔treatment mapping",   "pts": 3, "type": "tiered",   "tiers": [
        {"score": 3, "condition": "has_all", "terms": ["LinearDML", "continuous", "LinearDRLearner", "binary"]},
        {"score": 2, "condition": "has_all", "terms": ["LinearDML", "continuous"]},
        {"score": 1, "condition": "has_any", "terms": ["LinearDML", "LinearDRLearner"]},
    ]},
    {"id": "a3",  "cat": "accuracy", "name": "Correct EconML fit API",                "pts": 3, "type": "tiered",   "tiers": [
        {"score": 3, "condition": "has_all", "terms": ["X=None", 'inference="statsmodels"']},
        {"score": 2, "condition": "has_any", "terms": ["X=None", 'inference="statsmodels"']},
        {"score": 1, "condition": "has_any", "terms": ["est.fit", ".fit("]},
    ]},
    {"id": "a4",  "cat": "accuracy", "name": "Uses GradientBoosting nuisance models", "pts": 2, "type": "has_any",  "terms": ["GradientBoosting", "GradientBoostingRegressor"]},
    {"id": "a5",  "cat": "accuracy", "name": "Correct effect extraction API",         "pts": 2, "type": "has_any",  "terms": ["effect_interval"]},
    {"id": "a6",  "cat": "accuracy", "name": "Mentions unconditional difference",     "pts": 2, "type": "has_any",  "terms": ["unconditional difference", "unconditional association", "unadjusted"]},
    {"id": "a7",  "cat": "accuracy", "name": "Uses variable role terminology",        "pts": 2, "type": "count_of", "terms": ["outcome (Y", "treatment (T", "confounder", "W)"]},
    {"id": "a8",  "cat": "accuracy", "name": "Mentions float64 conversion",           "pts": 2, "type": "has_any",  "terms": ["float64", "pd.to_numeric"]},
    {"id": "a9",  "cat": "accuracy", "name": "Processing steps in correct order",     "pts": 2, "type": "ordered",  "terms": ["missing", "winsoriz", "log", "dummy"]},
    {"id": "a10", "cat": "accuracy", "name": "Mentions fpdf2/FPDF",                   "pts": 2, "type": "has_any",  "terms": ["fpdf", "FPDF"]},
    {"id": "a11", "cat": "accuracy", "name": "Describes missing indicator method",    "pts": 2, "type": "has_all",  "terms": ["missing", "indicator"]},
    {"id": "a12", "cat": "accuracy", "name": "PDF described as 2-page (accurate)",    "pts": 2, "type": "has_any",  "terms": ["2-page", "two-page", "two page"]},
    {"id": "a13", "cat": "accuracy", "name": "Mentions random_state=42",              "pts": 1, "type": "has_any",  "terms": ["random_state"]},
    {"id": "a14", "cat": "accuracy", "name": "OLS via statsmodels (sm.OLS)",          "pts": 2, "type": "has_any",  "terms": ["sm.OLS", "sm.add_constant", "statsmodels.api"]},
    {"id": "a15", "cat": "accuracy", "name": "Mentions ate_inference() API",          "pts": 2, "type": "has_any",  "terms": ["ate_inference"]},
    {"id": "a16", "cat": "accuracy", "name": "Crump trimming thresholds (0.1, 0.9)", "pts": 1, "type": "has_all",  "terms": ["0.1", "0.9", "propensity"]},

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  CODE EXAMPLES — Does it include working code snippets?             ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    {"id": "c1",  "cat": "code_examples", "name": "LinearDML code example",        "pts": 3, "type": "has_any", "terms": ["LinearDML("]},
    {"id": "c2",  "cat": "code_examples", "name": "LinearDRLearner code example",  "pts": 3, "type": "has_any", "terms": ["LinearDRLearner("]},
    {"id": "c3",  "cat": "code_examples", "name": "OLS code example",              "pts": 2, "type": "has_any", "terms": ["sm.OLS", "sm.add_constant"]},
    {"id": "c4",  "cat": "code_examples", "name": "Processing code examples",      "pts": 2, "type": "has_any", "terms": ["mstats.winsorize", "pd.get_dummies", "get_dummies"]},
    {"id": "c5",  "cat": "code_examples", "name": "Result extraction code",        "pts": 2, "type": "has_all", "terms": ["est.effect(", "effect_interval("]},
    {"id": "c6",  "cat": "code_examples", "name": "Diagnostic code examples",      "pts": 3, "type": "tiered",  "tiers": [
        {"score": 3, "condition": "has_any", "terms": ["cross_val_score"]},
        {"score": 2, "condition": "has_any", "terms": ["predict_proba"]},
        {"score": 1, "condition": "has_any", "terms": ["diagnostic", "AUC"]},
    ]},

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  USEFULNESS — Is it actionable guidance for an AI agent?            ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    {"id": "u1",  "cat": "usefulness", "name": "Non-technical audience guidance",        "pts": 2, "type": "has_any", "terms": ["non-technical", "plain language", "avoid jargon"]},
    {"id": "u2",  "cat": "usefulness", "name": "Causal vs predictive warning",          "pts": 2, "type": "has_all", "terms": ["prediction", "causal"]},
    {"id": "u3",  "cat": "usefulness", "name": "Unmeasured confounder caveat",          "pts": 2, "type": "has_any", "terms": ["unmeasured confounder", "unobserved confounder", "omitted variable"]},
    {"id": "u4",  "cat": "usefulness", "name": "Confounder inclusion bias tradeoff",    "pts": 2, "type": "has_all", "terms": ["bias", "include"]},
    {"id": "u5",  "cat": "usefulness", "name": "Data copy / no mutation warning",       "pts": 1, "type": "has_any", "terms": ["copy", "copies", "do not mutate", "preserve"]},
    {"id": "u6",  "cat": "usefulness", "name": "Result interpretation template",        "pts": 2, "type": "has_any", "terms": ["one-unit increase", "causes"]},
    {"id": "u7",  "cat": "usefulness", "name": "P-value / significance coverage",       "pts": 2, "type": "has_any", "terms": ["p-value", "p_value"]},
    {"id": "u8",  "cat": "usefulness", "name": "Structured user questions",             "pts": 2, "type": "has_all", "terms": ["ask", "user"]},
    {"id": "u9",  "cat": "usefulness", "name": "ATE vs heterogeneous effects (X=None)", "pts": 2, "type": "has_any", "terms": ["ATE", "average treatment effect", "heterogeneous"]},
    {"id": "u10", "cat": "usefulness", "name": "Bias direction (inflating vs masking)",  "pts": 2, "type": "has_any", "terms": ["inflating", "masking"]},
    {"id": "u11", "cat": "usefulness", "name": "Doubly robust property explained",      "pts": 2, "type": "has_any", "terms": ["doubly robust"]},
    {"id": "u12", "cat": "usefulness", "name": "Statistical vs practical significance", "pts": 2, "type": "tiered",  "tiers": [
        {"score": 2, "condition": "has_all",  "terms": ["meaningful", "significant"]},
        {"score": 1, "condition": "has_any",  "terms": ["practical significance", "effect size", "meaningful"]},
    ]},
    {"id": "u13", "cat": "usefulness", "name": "Reverse causality warning",             "pts": 1, "type": "has_any", "terms": ["reverse causality", "reverse causal"]},
]
