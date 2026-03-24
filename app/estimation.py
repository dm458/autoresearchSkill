"""
Causal estimation engine wrapping EconML estimators.

Provides a simplified interface for the Streamlit app, with plain-language
descriptions of each estimator suitable for non-technical users.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from econml.dml import LinearDML
from econml.dr import LinearDRLearner
import statsmodels.api as sm
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estimator catalog — plain-language descriptions for non-technical users
# ---------------------------------------------------------------------------

ESTIMATORS = {
    "OLS": {
        "name": "Ordinary Least Squares (OLS)",
        "short": "Classic linear regression of outcome on treatment and confounders.",
        "description": (
            "OLS fits a single linear regression: Outcome = β₀ + β₁·Treatment + β₂·Confounders + ε. "
            "The coefficient on treatment (β₁) is the estimated effect. This is the simplest and most "
            "widely understood method, but it assumes the relationship between all variables is linear "
            "and that confounders are correctly specified."
        ),
        "when_to_use": (
            "Best as a transparent baseline. Use it when you want a simple, interpretable estimate "
            "to compare against the more flexible ML-based methods."
        ),
        "complexity": "Simplest",
        "treatment_type": "any",
    },
    "LinearDML": {
        "name": "Linear Double Machine Learning",
        "short": "Assumes the treatment effect changes smoothly (e.g. linearly) with your features.",
        "description": (
            "This method first uses machine learning to remove the influence of confounders, "
            "then fits a simple (polynomial) model to describe how the treatment effect "
            "varies across your chosen features. It's a good starting point and produces "
            "easy-to-interpret coefficients."
        ),
        "when_to_use": (
            "Best for continuous treatments when you expect the treatment effect to follow "
            "a smooth, predictable pattern — for example, 'higher income → less price-sensitive'."
        ),
        "complexity": "Simple",
        "treatment_type": "continuous",
    },
    "LinearDRLearner": {
        "name": "Linear Doubly Robust Learner",
        "short": "Combines outcome modeling and propensity weighting for robust binary treatment effects.",
        "description": (
            "This method uses a doubly robust approach: it models both the outcome and the "
            "probability of receiving treatment (propensity score). If either model is correct, "
            "the estimate is consistent. It then fits a linear model for the treatment effect. "
            "Designed specifically for binary treatments."
        ),
        "when_to_use": (
            "Best for binary treatments (e.g., treated vs. untreated) when you want a robust "
            "estimate that protects against model misspecification."
        ),
        "complexity": "Simple",
        "treatment_type": "binary",
    },
}


def get_estimator_recommendation(df: pd.DataFrame, is_binary_treatment: bool = False) -> str:
    """Recommend an estimator based on treatment type."""
    if is_binary_treatment:
        return "LinearDRLearner"
    else:
        return "LinearDML"


def compute_unconditional_difference(T: np.ndarray, Y: np.ndarray) -> float:
    """Compute the unconditional association between treatment and outcome.

    For binary treatment: difference in means (treated - untreated).
    For continuous treatment: OLS slope of Y on T (no confounders).
    """
    T = T.flatten()
    Y = Y.flatten()
    is_binary = set(np.unique(T)).issubset({0, 1, 0.0, 1.0})
    if is_binary:
        treated = T == 1
        mean_t = float(np.mean(Y[treated])) if treated.any() else 0
        mean_u = float(np.mean(Y[~treated])) if (~treated).any() else 0
        return mean_t - mean_u
    else:
        # OLS slope: cov(T,Y) / var(T)
        t_var = np.var(T, ddof=1)
        if t_var == 0:
            return 0.0
        return float(np.cov(T, Y, ddof=1)[0, 1] / t_var)


# ---------------------------------------------------------------------------
# Model fitting
# ---------------------------------------------------------------------------

def fit_model(
    df: pd.DataFrame,
    outcome_col: str,
    treatment_col: str,
    confounder_cols: list[str],
    estimator_name: str,
) -> dict:
    """
    Fit a causal model and return results dict with:
      - model: fitted estimator
      - te_pred: average treatment effect prediction
      - te_interval: (lower, upper) confidence interval arrays
      - summary_df: summary DataFrame (for LinearDML)
      - Y, T, W arrays used
    """
    Y = pd.to_numeric(df[outcome_col], errors="coerce").astype(np.float64).values
    T = pd.to_numeric(df[treatment_col], errors="coerce").astype(np.float64).values
    W = df[confounder_cols].apply(pd.to_numeric, errors="coerce").astype(np.float64).values if confounder_cols else None

    # Check for any values that couldn't be converted
    if np.any(np.isnan(Y)):
        raise ValueError(f"Outcome column '{outcome_col}' contains non-numeric values that could not be converted.")
    if np.any(np.isnan(T)):
        raise ValueError(f"Treatment column '{treatment_col}' contains non-numeric values that could not be converted.")
    if W is not None and np.any(np.isnan(W)):
        bad_cols = [c for c in confounder_cols if pd.to_numeric(df[c], errors="coerce").isna().any() and df[c].notna().any()]
        raise ValueError(f"Confounder column(s) {bad_cols} contain non-numeric values. Please encode them in Step 5.")

    if estimator_name == "OLS":
        # Build design matrix: intercept + treatment + confounders
        X_ols = sm.add_constant(T.reshape(-1, 1) if W is None else np.column_stack([T, W]))
        ols_model = sm.OLS(Y, X_ols).fit()
        # Treatment coefficient is index 1 (after constant)
        te_coef = ols_model.params[1]
        ci = ols_model.conf_int(alpha=0.05)[1]  # 95% CI for treatment coefficient
        te_pred = np.array([te_coef])
        te_lower = np.array([ci[0]])
        te_upper = np.array([ci[1]])
        summary_text = str(ols_model.summary())

        return {
            "model": ols_model,
            "estimator_name": estimator_name,
            "te_pred": te_pred,
            "te_lower": te_lower,
            "te_upper": te_upper,
            "summary_text": summary_text,
            "Y": Y,
            "T": T,
            "W": W,
            "W_cols": confounder_cols,
            "outcome_col": outcome_col,
            "treatment_col": treatment_col,
        }

    if estimator_name == "LinearDML":
        est = LinearDML(
            model_y=GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42),
            model_t=GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42),
            random_state=42,
        )
        est.fit(Y, T, X=None, W=W, inference="statsmodels")
    elif estimator_name == "LinearDRLearner":
        est = LinearDRLearner(
            model_regression=GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42),
            model_propensity=GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42),
            random_state=42,
        )
        est.fit(Y, T, X=None, W=W, inference="statsmodels")
    else:
        raise ValueError(f"Unknown estimator: {estimator_name}")

    # Predict average treatment effect
    te_pred = est.effect()
    te_interval = est.effect_interval(alpha=0.05)

    # Summary
    summary_text = None
    try:
        summary_text = str(est.summary())
        logger.debug("est.summary() [%s]:\n%s", estimator_name, summary_text)
    except Exception:
        pass

    # Extract ATE inference object for proper p-values and standard errors
    ate_inference_obj = None
    try:
        ate_inference_obj = est.ate_inference()
    except Exception:
        pass

    return {
        "model": est,
        "estimator_name": estimator_name,
        "te_pred": te_pred,
        "te_lower": te_interval[0],
        "te_upper": te_interval[1],
        "summary_text": summary_text,
        "ate_inference": ate_inference_obj,
        "Y": Y,
        "T": T,
        "W": W,
        "W_cols": confounder_cols,
        "outcome_col": outcome_col,
        "treatment_col": treatment_col,
    }


# ---------------------------------------------------------------------------
# Interpretation helpers
# ---------------------------------------------------------------------------

def create_effect_plot(results: dict) -> plt.Figure:
    """
    Single-panel visualization comparing unconditional difference (horizontal line)
    with the causal effect estimate (dot with whiskers). Effect on y-axis.
    """
    te = results["te_pred"].flatten()
    te_lower = results["te_lower"].flatten()
    te_upper = results["te_upper"].flatten()
    Y = results["Y"].flatten()
    T = results["T"].flatten()

    avg_te = float(np.mean(te))
    avg_lower = float(np.mean(te_lower))
    avg_upper = float(np.mean(te_upper))

    raw_diff = compute_unconditional_difference(T, Y)
    is_binary = set(np.unique(T)).issubset({0, 1, 0.0, 1.0})

    treatment_col = results["treatment_col"]
    outcome_col = results["outcome_col"]

    fig, ax = plt.subplots(figsize=(5, 3.5))

    # Zero reference line
    ax.axhline(y=0, color="grey", linestyle="--", alpha=0.5, lw=1)

    # Unconditional difference/association as a horizontal line
    uncond_label = "Unconditional difference" if is_binary else "Unconditional association"
    ax.axhline(y=raw_diff, color="#ff7f0e", linestyle="-", lw=2, label=f"{uncond_label}: {raw_diff:+.4f}")

    # Causal effect estimate as dot with whiskers
    err_low = max(avg_te - avg_lower, 0)
    err_high = max(avg_upper - avg_te, 0)
    ax.errorbar(
        0.5, avg_te, yerr=[[err_low], [err_high]],
        fmt="o", color="#1f77b4", markersize=10, capsize=8, capthick=2, elinewidth=2,
        label=f"Causal effect (ATE): {avg_te:+.4f}  [{avg_lower:+.4f}, {avg_upper:+.4f}]",
    )

    ax.set_xticks([])
    ax.set_ylabel(f"Effect on {outcome_col}", fontsize=11)
    ax.set_title(f"Effect of {treatment_col} on {outcome_col}", fontsize=12, fontweight="bold")
    ax.legend(loc="best", fontsize=9, framealpha=0.9)

    fig.tight_layout()
    return fig


def get_effect_summary(results: dict) -> dict:
    """Return plain-language summary statistics of treatment effects."""
    from scipy import stats as sp_stats

    te = results["te_pred"].flatten()
    te_lower = results["te_lower"].flatten()
    te_upper = results["te_upper"].flatten()

    pct_negative = (te < 0).mean() * 100
    pct_positive = (te > 0).mean() * 100
    pct_significant = ((te_lower > 0) | (te_upper < 0)).mean() * 100

    avg_effect = float(np.mean(te))
    avg_lower = float(np.mean(te_lower))
    avg_upper = float(np.mean(te_upper))

    # Extract p-value and SE from ATE inference object if available, else fall back to CI approximation
    ate_inference_obj = results.get("ate_inference")
    if ate_inference_obj is not None:
        try:
            p_value = float(ate_inference_obj.pvalue()[0])
            se = float(ate_inference_obj.stderr[0])
        except Exception:
            ate_inference_obj = None  # fall back below

    if ate_inference_obj is None:
        # TODO: This logic is sketchy; instead of computing the bounds on the ATE
        #       it is averaging the bounds for each individual effect, which is not the same.
        #       We should ideally extract the standard error of the ATE directly.
        #       Also, we should assert that this is only used for OLS, not for our CATE estimators.
        ci_width = avg_upper - avg_lower
        if ci_width > 0:
            se = ci_width / (2 * 1.96)
            z = avg_effect / se if se > 0 else 0.0
            p_value = float(2 * sp_stats.norm.sf(abs(z)))
        else:
            se = 0.0
            p_value = 0.0 if avg_effect != 0 else 1.0

    return {
        "average_effect": avg_effect,
        "median_effect": float(np.median(te)),
        "std_effect": float(np.std(te)),
        "min_effect": float(np.min(te)),
        "max_effect": float(np.max(te)),
        "pct_positive": pct_positive,
        "pct_negative": pct_negative,
        "pct_significant": pct_significant,
        "n_observations": len(te),
        "avg_lower": avg_lower,
        "avg_upper": avg_upper,
        "p_value": p_value,
        "standard_error": se,
    }


def get_individual_effects_df(results: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Build a DataFrame of individual-level treatment effects for download."""
    n = len(df)
    te = results["te_pred"].flatten()
    te_lower = results["te_lower"].flatten()
    te_upper = results["te_upper"].flatten()

    # ATE estimation returns a single value; broadcast to all rows
    if len(te) == 1:
        te = np.full(n, te[0])
    if len(te_lower) == 1:
        te_lower = np.full(n, te_lower[0])
    if len(te_upper) == 1:
        te_upper = np.full(n, te_upper[0])

    out = df.copy()
    out["estimated_treatment_effect"] = te
    out["effect_lower_95"] = te_lower
    out["effect_upper_95"] = te_upper
    out["statistically_significant"] = (te_lower > 0) | (te_upper < 0)
    out["recommended_action"] = np.where(te > 0, "Apply Treatment", "Do Not Treat")

    return out


def generate_results_pdf(
    results: dict,
    summary: dict,
    fig: plt.Figure,
    estimator_info: dict,
    processing_log: list[str],
    causal_question: str = "",
    domain_knowledge: str = "",
    confounders: list[str] | None = None,
    diagnostics: dict | None = None,
) -> bytes:
    """Generate a polished 2-page consulting-style PDF report."""
    import tempfile
    from fpdf import FPDF

    if confounders is None:
        confounders = results.get("W_cols", [])
    if diagnostics is None:
        diagnostics = {}

    treatment = results["treatment_col"]
    outcome = results["outcome_col"]

    # Save the figure to a temp file (small)
    fig_path = tempfile.mktemp(suffix=".png")
    fig.savefig(fig_path, dpi=150, bbox_inches="tight", facecolor="white")

    # ── Design tokens ──
    NAVY = (24, 42, 68)
    DARK = (44, 44, 44)
    MID = (100, 100, 100)
    LIGHT = (160, 160, 160)
    RULE = (200, 205, 212)
    CARD_BG = (246, 248, 250)
    ACCENT = (0, 102, 179)
    WARN_BG = (255, 248, 230)
    WHITE = (255, 255, 255)

    def _s(text: str) -> str:
        """Sanitize non-latin1 characters."""
        reps = {
            "\u2014": "--", "\u2013": "-", "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"', "\u2022": "-", "\u2026": "...",
            "\u2192": "->", "\u2190": "<-", "\u03b2": "B", "\u03b5": "e",
            "\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3",
            "\u00b7": "*",
        }
        for o, r in reps.items():
            text = text.replace(o, r)
        return text.encode("latin-1", errors="replace").decode("latin-1")

    import numpy as np

    # Pre-compute all text content
    ate = summary["average_effect"]
    se = summary["standard_error"]
    ci_lo, ci_hi = summary["avg_lower"], summary["avg_upper"]
    p_val = summary["p_value"]
    p_str = f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001"

    direction = "decreases" if ate < 0 else ("increases" if ate > 0 else "has no average effect on")
    sig_word = "statistically significant" if p_val < 0.05 else "not statistically significant"

    T_arr = results["T"].flatten()
    Y_arr = results["Y"].flatten()
    raw_diff = compute_unconditional_difference(T_arr, Y_arr)
    is_binary = set(np.unique(T_arr)).issubset({0, 1, 0.0, 1.0})
    avg_lower = float(np.mean(results["te_lower"].flatten()))
    avg_upper = float(np.mean(results["te_upper"].flatten()))
    ci_crosses = avg_lower <= 0 <= avg_upper

    class PDF(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(*LIGHT)
            self.cell(0, 8, "Generated by Causal Analysis Companion", align="L")
            self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="R")

        # ── Reusable components ──

        def section(self, title):
            """Navy section header with underline."""
            self.ln(5)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*NAVY)
            self.multi_cell(0, 6, _s(title).upper(), new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(*NAVY)
            self.set_line_width(0.6)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.set_line_width(0.2)
            self.ln(3)

        def kpi(self, label, value, x, y, w):
            """Single KPI card at absolute position."""
            self.set_xy(x, y)
            self.set_fill_color(*CARD_BG)
            self.rect(x, y, w, 14, "F")
            self.set_xy(x + 2, y + 1)
            self.set_font("Helvetica", "", 6.5)
            self.set_text_color(*MID)
            self.cell(w - 4, 4, _s(label))
            self.set_xy(x + 2, y + 6)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*DARK)
            self.cell(w - 4, 6, _s(str(value)))

        def para(self, text, size=8.5):
            """Body paragraph."""
            self.set_font("Helvetica", "", size)
            self.set_text_color(*DARK)
            self.multi_cell(0, 4.5, _s(text), new_x="LMARGIN", new_y="NEXT")

        def para_bold(self, label, text, size=8.5):
            """Bold label + regular text on same line."""
            self.set_font("Helvetica", "B", size)
            self.set_text_color(*DARK)
            self.multi_cell(0, 4.5, _s(f"{label} {text}"), new_x="LMARGIN", new_y="NEXT")

        def callout(self, text, warn=False):
            """Highlighted callout box."""
            bg = WARN_BG if warn else CARD_BG
            border_color = (200, 160, 0) if warn else ACCENT
            self.set_fill_color(*bg)
            y_start = self.get_y()
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*DARK)
            self.multi_cell(0, 4.5, _s(text), new_x="LMARGIN", new_y="NEXT", fill=True)
            self.set_draw_color(*border_color)
            self.set_line_width(0.8)
            self.line(self.l_margin, y_start, self.l_margin, self.get_y())
            self.set_line_width(0.2)
            self.ln(2)

        def label_row(self, label, value):
            """Compact label: value row."""
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*MID)
            self.cell(40, 4.5, _s(label))
            self.set_font("Helvetica", "", 8.5)
            self.set_text_color(*DARK)
            self.multi_cell(0, 4.5, _s(str(value)), new_x="LMARGIN", new_y="NEXT")

        def thin_rule(self):
            self.set_draw_color(*RULE)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(2)

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pw = pdf.w - pdf.l_margin - pdf.r_margin  # printable width

    # ═══════════════════════  PAGE 1  ═══════════════════════

    # ── Title strip ──
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 22, "F")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*WHITE)
    pdf.set_y(4)
    pdf.cell(0, 8, "Causal Analysis Summary", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(180, 200, 230)
    pdf.cell(0, 5, _s(f"Effect of {treatment} on {outcome}"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*DARK)
    pdf.set_y(25)

    # ── Research question (if any) ──
    if causal_question:
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(*MID)
        pdf.multi_cell(0, 4.5, _s(f'Research Question: "{causal_question}"'), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # ── KPI strip ──
    pdf.section("Key Findings")
    kpi_y = pdf.get_y()
    gap = 3
    kpi_w = (pw - gap * 3) / 4
    pdf.kpi("Average Treatment Effect", f"{ate:.4f}", pdf.l_margin, kpi_y, kpi_w)
    pdf.kpi("Standard Error", f"{se:.4f}", pdf.l_margin + kpi_w + gap, kpi_y, kpi_w)
    pdf.kpi("95% Confidence Interval", f"[{ci_lo:.4f}, {ci_hi:.4f}]", pdf.l_margin + 2 * (kpi_w + gap), kpi_y, kpi_w)
    pdf.kpi("p-value", p_str, pdf.l_margin + 3 * (kpi_w + gap), kpi_y, kpi_w)
    pdf.set_y(kpi_y + 17)

    # Interpretation paragraph
    p_display = f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001"
    if p_val < 0.05:
        sig_sentence = (
            f"This result is statistically significant (p = {p_display}), meaning it is unlikely "
            f"to be due to chance alone."
        )
    else:
        sig_sentence = (
            f"This result is not statistically significant (p = {p_display}), meaning we cannot "
            f"confidently rule out that the observed effect is due to chance."
        )
    ci_sentence = (
        f"We are 95% confident the true effect lies between "
        f"{ci_lo:.4f} and {ci_hi:.4f}."
    )
    pdf.para(
        f"In plain language: On average, increasing {treatment} {direction} {outcome} "
        f"by {abs(ate):.4f} units. {ci_sentence}"
    )
    pdf.ln(1)
    pdf.para(sig_sentence)
    pdf.ln(1)

    # ── Chart (small) + takeaways side-by-side ──
    pdf.section("Treatment Effect Visualization")
    chart_y = pdf.get_y()
    chart_w = 65
    try:
        pdf.image(fig_path, x=pdf.l_margin, y=chart_y, w=chart_w)
    except Exception:
        pass

    # Takeaways to the right of chart
    text_x = pdf.l_margin + chart_w + 5
    text_w = pw - chart_w - 5
    pdf.set_xy(text_x, chart_y)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*NAVY)
    uncond_label = "Unconditional difference (orange line):" if is_binary else "Unconditional association (orange line):"
    pdf.multi_cell(text_w, 4, uncond_label, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(text_x)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*DARK)
    if is_binary:
        uncond_text = (
            f"The raw difference in average {outcome} between treated and untreated groups "
            f"is {raw_diff:+.4f}, without controlling for any confounders. "
            f"This difference may be driven by confounders rather than the treatment itself."
        )
    else:
        uncond_text = (
            f"The raw association between {treatment} and {outcome} is {raw_diff:+.4f} "
            f"per unit increase in {treatment}, without controlling for any confounders. "
            f"This association may be driven by confounders rather than the treatment itself."
        )
    pdf.multi_cell(text_w, 3.8, _s(uncond_text), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_x(text_x)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(text_w, 4, "Causal effect estimate (blue dot with whiskers):", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(text_x)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*DARK)
    if ci_crosses:
        causal_takeaway = (
            f"After controlling for confounders, the estimated causal effect is {ate:.4f}, "
            f"but the confidence interval crosses zero ([{avg_lower:.4f}, {avg_upper:.4f}]), "
            f"meaning we cannot rule out that the true effect is zero."
        )
    else:
        causal_takeaway = (
            f"After controlling for confounders, the estimated causal effect is {ate:.4f} "
            f"with a confidence interval of [{avg_lower:.4f}, {avg_upper:.4f}]. Since the "
            f"interval does not cross zero, the effect is statistically significant."
        )
    pdf.multi_cell(text_w, 3.8, _s(causal_takeaway), new_x="LMARGIN", new_y="NEXT")

    # Move below chart (ensure we clear it)
    chart_bottom = chart_y + chart_w * 0.7  # approximate aspect ratio
    pdf.set_y(max(pdf.get_y() + 2, chart_bottom))

    # Unconditional vs causal comparison callout
    if abs(raw_diff) > 0.001 and abs(ate) > 0.001:
        if abs(ate) < abs(raw_diff):
            comp = (
                f"Unconditional vs. Causal: The unconditional difference ({raw_diff:+.4f}) is larger "
                f"in magnitude than the causal estimate ({ate:+.4f}), suggesting that confounders were "
                f"inflating the apparent effect of {treatment} on {outcome}."
            )
        elif abs(ate) > abs(raw_diff):
            comp = (
                f"Unconditional vs. Causal: The causal estimate ({ate:+.4f}) is larger in magnitude "
                f"than the unconditional difference ({raw_diff:+.4f}), suggesting that confounders were "
                f"masking some of the true effect of {treatment} on {outcome}."
            )
        else:
            comp = (
                f"Unconditional vs. Causal: The unconditional difference ({raw_diff:+.4f}) and the "
                f"causal estimate ({ate:+.4f}) are similar, suggesting confounders had little impact "
                f"on the observed relationship between {treatment} and {outcome}."
            )
    else:
        comp = (
            f"Unconditional vs. Causal: The unconditional difference is {raw_diff:+.4f} and "
            f"the causal estimate is {ate:+.4f}."
        )
    pdf.callout(comp)

    # ═══════════════════════  PAGE 2  ═══════════════════════
    # (auto page break will handle if page 1 is full, but let's try to fit diagnostics + setup)

    # ── Diagnostics (compact) ──
    pred = diagnostics.get("predictability", {})
    overlap = diagnostics.get("overlap", {})
    if pred or overlap:
        pdf.section("Pre-Estimation Diagnostics")
        if pred:
            metric_name = pred.get("metric", "AUC")
            metric_val = pred.get("value", 0)
            status = pred.get("status", "ok")
            msg = pred.get("message", "")
            icon = "!" if status == "high" else ("*" if status == "low" else " ")
            pdf.label_row(f"Treatment Predictability ({metric_name}):", f"{metric_val:.3f}")
            if status in ("high", "low"):
                pdf.callout(msg, warn=(status == "high"))
                top_c = pred.get("top_confounders", "")
                if top_c:
                    pdf.para(f"Most predictive: {top_c}", size=8)
            else:
                pdf.para(msg, size=8)
            pdf.ln(1)

        if overlap:
            mean_tr = overlap.get("mean_treated", 0)
            mean_un = overlap.get("mean_untreated", 0)
            pct = overlap.get("pct_trimmed", 0)
            n_trim = overlap.get("n_trimmed", 0)
            status = overlap.get("status", "good")
            msg = overlap.get("message", "")
            pdf.label_row("Propensity (Treated / Untreated):", f"{mean_tr:.3f} / {mean_un:.3f}")
            pdf.label_row("Trimmed observations:", f"{n_trim:,} ({pct:.1f}%)")
            if status in ("poor", "separation"):
                pdf.callout(msg, warn=True)
            elif status == "moderate":
                pdf.callout(msg)
            else:
                pdf.para(msg, size=8)
            pdf.ln(1)

    # ── Analysis Setup (compact two-column feel) ──
    pdf.section("Analysis Setup")

    # Treatment & outcome
    t_proc = [s for s in processing_log if treatment in s]
    o_proc = [s for s in processing_log if outcome in s]
    pdf.label_row("Treatment:", treatment + ("  (" + "; ".join(t_proc) + ")" if t_proc else ""))
    pdf.label_row("Outcome:", outcome + ("  (" + "; ".join(o_proc) + ")" if o_proc else ""))

    # Confounders
    if confounders:
        conf_strs = []
        for c in confounders:
            cp = [s for s in processing_log if c in s]
            conf_strs.append(c + (f" ({'; '.join(cp)})" if cp else ""))
        pdf.label_row("Confounders:", ", ".join(conf_strs))
    else:
        pdf.label_row("Confounders:", "None selected")

    # Domain knowledge
    if domain_knowledge:
        pdf.ln(1)
        pdf.label_row("Domain context:", "")
        pdf.callout(domain_knowledge)

    pdf.ln(1)

    # ── Estimator ──
    pdf.section("Estimation Method")
    pdf.label_row("Method:", estimator_info["name"])
    pdf.label_row("Complexity:", estimator_info["complexity"])
    pdf.ln(1)
    pdf.para(estimator_info["description"], size=8)

    # ── Output ──
    pdf_bytes = pdf.output()

    import os
    try:
        os.remove(fig_path)
    except OSError:
        pass

    return bytes(pdf_bytes)
