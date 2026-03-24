# Causal Analysis — Agent Instructions

When a user asks you to help with causal analysis, causal inference, or estimating a treatment effect, follow these instructions. The workflow is designed to give the user a complete answer fast, then refine it based on their feedback.

**Core philosophy: Results first, questions after.** After collecting the data and causal question, run the entire analysis end-to-end using best-practice defaults. Present the full results, then explain every assumption you made and ask the user whether any should be changed. If the user requests changes, rerun the analysis with the updated assumptions.

---

## Part A: Gather Inputs (Interactive)

Only two things require user input before the first run: the data and the causal question.

### A1. Load the Data

1. Load the data file (CSV, Excel, or DataFrame) into a pandas DataFrame.
2. Ask the user: *"Do you have a data dictionary (a file or description mapping column names to their meanings)? This helps me make better assumptions."*
3. If they provide one, load it and map definitions to columns.
4. Print a brief summary: shape, column names with dtypes, first 5 rows, missing-value counts.
5. If any column names are ambiguous and no data dictionary was provided, ask the user what they represent. **Do not ask about obvious columns** — use common sense (e.g., `age`, `income`, `gender` are self-explanatory).

### A2. Frame the Causal Question

1. Ask: *"What action or intervention do you want to study (treatment), and what result do you want to measure (outcome)?"*
2. Map the user's answer to specific columns:
   - **Treatment (T):** The variable representing the action, intervention, or exposure.
   - **Outcome (Y):** The variable representing the result to measure.
3. Confirm: *"Got it — I'll estimate the effect of [treatment] on [outcome]."*
4. Determine the treatment type automatically:
   - **Binary:** Only two distinct values (e.g., 0/1, yes/no).
   - **Continuous:** Many distinct numeric values (e.g., price, dosage, hours).

**Guardrails:**
- Treatment and outcome must be different variables with non-zero variance.
- If either has >5% missing values, note this but proceed — it will be handled in processing.

**Once you have the data and the causal question, do NOT ask any more questions. Proceed directly to Part B.**

---

## Part B: Automated Analysis (No User Interaction)

Run all of the following steps silently using best-practice defaults. Show the code and output for each step, but do NOT stop to ask for confirmation. The goal is to deliver a complete answer as quickly as possible.

### B1. Select Confounders (Best-Practice Defaults)

Use all available information — data dictionary definitions, column names, data patterns, and general domain knowledge — to automatically classify every remaining variable (excluding treatment and outcome):

- **Confounder (W):** Variables that plausibly cause BOTH the treatment and the outcome. **Default: include as confounder.** When in doubt about a variable's role, it is safer to include it as a confounder than to omit it (omission causes bias; unnecessary inclusion only costs efficiency).
- **Exclude:** Variables that are clearly consequences of the treatment (mediators), consequences of the outcome (colliders), or pure identifiers (row IDs, timestamps that are just indices).

**Default rules when uncertain:**
- Demographic variables (age, gender, income, education, location) → **include as confounders** (they almost always influence both treatment and outcome).
- Pre-treatment measurements and baseline characteristics → **include as confounders**.
- Variables measured after treatment that could be on the causal path → **exclude** (likely mediators).
- ID columns, row indices, dates used only for ordering → **exclude**.

Record which variables you selected and which you excluded, with a one-line reason for each. You will present this to the user in Part C.

### B2. Process the Data

Apply all processing steps automatically to a **copy** of the data:

**Missing values:**
- Treatment or outcome missing → drop those rows. Record count dropped.
- Confounders missing → use the **missing indicator method**: fill with median for numeric (0 for binary), add `<col>_missing` binary indicator.

**Variation check:**
- Verify treatment and outcome have non-zero variance after missing-value handling.
- If either is constant, **stop and report** — the analysis cannot proceed.

**Winsorize outliers:**
- For each continuous variable (treatment, outcome, confounders), check 1st and 99th percentiles.
- If the ratio of the 99th-to-1st percentile range vs the IQR exceeds 5, **winsorize** at [1%, 99%].

```python
from scipy.stats import mstats
data[col] = mstats.winsorize(data[col], limits=[0.01, 0.01])
```

**Log transform skewed variables:**
- For each continuous variable with all-positive values, compute skewness.
- If |skewness| > 2, apply log transform: `data[col] = np.log(data[col])`.
- Rename to `log_<col>`.

**Encode categorical variables:**
- Identify string/object columns and low-cardinality numeric columns (≤ 5 unique values) among confounders.
- Dummy-encode with `drop_first=True`.

```python
data = pd.get_dummies(data, columns=cat_cols, drop_first=True)
```

Record every processing step applied. You will present these to the user in Part C.

### B3. Run Diagnostics

**Treatment predictability:**
```python
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.model_selection import cross_val_score

if treatment_is_binary:
    model = GradientBoostingClassifier(n_estimators=100, max_depth=3)
    scores = cross_val_score(model, W, T, cv=5, scoring="roc_auc")
    metric_name, metric_value = "AUC", scores.mean()
else:
    model = GradientBoostingRegressor(n_estimators=100, max_depth=3)
    scores = cross_val_score(model, W, T, cv=5, scoring="r2")
    metric_name, metric_value = "R²", scores.mean()
```

**Overlap check (binary treatment only):**
```python
from sklearn.ensemble import GradientBoostingClassifier
ps_model = GradientBoostingClassifier(n_estimators=100, max_depth=3)
ps_model.fit(W, T)
propensity_scores = ps_model.predict_proba(W)[:, 1]
```
- Compute Crump et al. (2009) trimming: count observations with propensity scores outside [0.1, 0.9].

Record diagnostic results and any warnings. You will present these in Part C.

### B4. Choose and Fit the Estimator

Select the estimator automatically based on treatment type:

| Treatment Type | Default Estimator | Why |
|---|---|---|
| **Binary** | Linear Doubly Robust Learner | Models both outcome and propensity score; consistent if either is correct |
| **Continuous** | Linear Double Machine Learning | Removes confounder effects via ML, then fits linear treatment model |

**Linear DML (continuous treatment):**
```python
from econml.dml import LinearDML
from sklearn.ensemble import GradientBoostingRegressor

est = LinearDML(
    model_y=GradientBoostingRegressor(n_estimators=100, max_depth=3),
    model_t=GradientBoostingRegressor(n_estimators=100, max_depth=3),
    random_state=42
)
est.fit(Y, T, X=None, W=W, inference="statsmodels")
```

**Linear DR Learner (binary treatment):**
```python
from econml.dr import LinearDRLearner
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier

est = LinearDRLearner(
    model_regression=GradientBoostingRegressor(n_estimators=100, max_depth=3),
    model_propensity=GradientBoostingClassifier(n_estimators=100, max_depth=3),
    random_state=42
)
est.fit(Y, T, X=None, W=W, inference="statsmodels")
```

**Guardrails:**
- All inputs (Y, T, W) must be converted to `float64` with `pd.to_numeric(errors="coerce")` before fitting.
- Always use `X=None` (estimates the Average Treatment Effect). Only use X if the user explicitly asks for heterogeneous effects.
- Always use `inference="statsmodels"` for confidence intervals.

### B5. Extract Results

For EconML estimators:
```python
ate = est.effect(X=None).mean()
ci = est.effect_interval(X=None, alpha=0.05)
ci_lower, ci_upper = ci[0].mean(), ci[1].mean()
se = (ci_upper - ci_lower) / (2 * 1.96)
z = ate / se
p_value = 2 * (1 - scipy.stats.norm.cdf(abs(z)))
```

Also compute the **unconditional difference** (no confounder adjustment):
- Binary treatment: `Y[T==1].mean() - Y[T==0].mean()`
- Continuous treatment: OLS of Y on T only.

---

## Part C: Present Results and Assumptions (Interactive)

Now present everything to the user in a single, structured response with three sections.

### Section 1: The Answer

Present the causal estimate in plain language:

> **Result:** A one-unit increase in [treatment] causes [outcome] to [increase/decrease] by [ATE] units, on average.
> **95% confidence interval:** [CI_lower, CI_upper]
> **Statistical significance:** [significant at the 5% level / not significant] (p = [p_value])

Then compare with the unconditional (unadjusted) estimate:
- If the unconditional estimate is larger → confounders were **inflating** the apparent effect.
- If smaller → confounders were **masking** part of the effect.
- If similar → confounders had little impact.

Include the standard caveat: *"This estimate assumes all relevant confounders have been included. Unmeasured confounders could bias the result."*

If the CI includes zero and p > 0.05: *"We cannot rule out that the true effect is zero."*

If diagnostics raised warnings, state them clearly here.

### Section 2: Assumptions I Made

Present a numbered list of **every assumption** made during the automated analysis. For each assumption, explain:
- **What was decided** (one sentence)
- **Why this is the default** (one sentence explaining the best-practice reasoning)

Organize assumptions into these categories:

**Confounder selection:**
- For each variable included as a confounder: why it was included.
- For each variable excluded: why it was excluded and what role it was assigned (mediator, collider, identifier, etc.).

**Data processing:**
- Which rows were dropped and why.
- Which variables were winsorized and the thresholds used.
- Which variables were log-transformed and the skewness values.
- Which categorical variables were dummy-encoded.
- How missing values in confounders were handled.

**Estimator choice:**
- Which estimator was used and why it was selected for this treatment type.
- That the analysis estimates the Average Treatment Effect (ATE), not individual-level effects.

**Diagnostic findings:**
- Treatment predictability score and what it means.
- Overlap check results (binary treatment only).

### Section 3: Questions for You

Ask the user **targeted, intelligent questions** about the assumptions most likely to need adjustment. Do not ask about every assumption — focus on the ones where domain knowledge could change the answer. Frame questions as specific choices, not open-ended.

**Always ask these:**

1. **Confounder review:** *"I included [list] as confounders and excluded [list]. The most important question is whether I missed anything or included something I shouldn't have. Specifically:*
   - *[Variable X] — I included this because [reason]. Could this actually be a consequence of [treatment] rather than a cause? If so, it should be excluded.*
   - *[Variable Y] — I excluded this because [reason]. Should it actually be controlled for?"*

2. **Any excluded variables that are borderline:** For variables where the confounder/mediator/collider classification was uncertain, ask directly: *"Was [variable] measured before or after the treatment was assigned? This determines whether it's appropriate to control for."*

**Ask these only if relevant:**

3. **Outlier handling:** Only ask if winsorization was applied to treatment or outcome: *"I capped extreme values in [variables] at the 1st/99th percentiles. Should I use the original values instead?"*

4. **Log transforms:** Only ask if a log transform was applied to treatment or outcome: *"I log-transformed [variable] because it was highly skewed. Do you prefer to use the original scale? (This changes the interpretation of the effect size.)"*

5. **Estimator choice:** Only ask if diagnostics raised concerns: *"The diagnostics suggest [issue]. Would you like to try a different estimation approach?"*

6. **Missing data:** Only ask if >5% of rows were dropped: *"I dropped [N] rows ([X]%) due to missing treatment or outcome values. Is there a reason these might be missing (e.g., certain groups are less likely to have data)? This could affect the results."*

**Do NOT ask:**
- Questions about obvious choices (e.g., "Should I use ATE?" when they didn't mention heterogeneity).
- Questions about processing steps that didn't materially change the data.
- Open-ended questions like "Any other thoughts?" — be specific.

### Section 4: PDF Report Offer

After presenting Sections 1–3, ask the user: *"Would you like me to generate a one-page PDF summary of these findings?"*

If the user says yes, proceed to **Part E**.

---

## Part D: Iterate (If Requested)

If the user asks to change any assumptions:

1. Acknowledge the changes clearly: *"Got it — I'll make these changes: [list changes]."*
2. Rerun the analysis from Part B with the updated assumptions. Only rerun the steps affected by the change:
   - Confounder change → rerun from B1 (reprocess, re-diagnose, re-estimate).
   - Processing change (e.g., remove winsorization) → rerun from B2.
   - Estimator change → rerun from B4.
3. Present updated results using the same Part C format, but **highlight what changed:**
   - *"With [change], the estimated effect moved from [old ATE] to [new ATE]."*
   - *"The confidence interval [widened/narrowed] from [old CI] to [new CI]."*
   - If the significance changed, call it out explicitly.
4. After presenting updated results, ask if the user wants to make further adjustments or is satisfied.

**The user can iterate as many times as they want.** Each iteration follows the same pattern: make changes → rerun → present updated results → ask if more changes are needed.

---

## Implementation Reference — Key Functions

The codebase is split across three modules. Map each analysis step to the correct function:

| Step | Function | Module | Purpose |
|------|----------|--------|---------|
| A1 | `get_column_summary` | `data_utils` | Summarize columns (type, nulls, unique, range, mean) |
| B1 | `generate_causal_graph_confounders` | `data_utils` | LLM-powered pairwise causal reasoning to identify confounders |
| B2 | `apply_processing` | `data_utils` | Missing values, winsorization, log transforms, dummy encoding |
| B4 | `fit_model` | `estimation` | Fit OLS, LinearDML, or LinearDRLearner and return results dict |
| B5 | `compute_unconditional_difference` | `estimation` | Raw association (mean diff for binary, OLS slope for continuous) |
| B5 | `get_effect_summary` | `estimation` | Plain-language summary: ATE, CI, p-value, significance % |
| E  | `generate_results_pdf` | `estimation` | Two-page consulting-style PDF with charts and diagnostics |
| E  | `create_effect_plot` | `estimation` | Matplotlib bar chart comparing unadjusted vs causal estimate |
| E  | `callout` | `estimation` | Renders highlighted callout boxes in PDF |
| E  | `footer` | `estimation` | PDF footer with page number and timestamp |

---

## General Rules

These rules apply across all parts:

1. **Audience is non-technical.** Use plain language. Avoid jargon like "CATE", "DGP", "nuisance model", "heteroskedasticity". When technical terms are unavoidable, define them.
2. **Speed over perfection on the first pass.** The goal is to give the user a complete answer quickly, then refine. Do not let the perfect be the enemy of the good.
3. **When in doubt, include as a confounder.** Omitting a true confounder causes bias. Including an unnecessary confounder only reduces statistical power slightly.
4. **Show your work.** Show the code you ran and the output for every step. The user should be able to reproduce the analysis.
5. **Do not confuse prediction with causal inference.** EconML estimates treatment effects, not predictions. If the user asks for a prediction model, clarify the distinction.
6. **Report limitations.** Always state: no reverse causality assumed, unmeasured confounders are possible, results depend on confounder selection.
7. **Preserve data integrity.** Always work on copies. Never mutate the user's original data.
8. **Never skip confounders.** Causal inference without confounder adjustment is just correlation. If the user's data has no plausible confounders, explain why the result is unreliable.

---

## Part E: One-Page PDF Report

Generate a single-page PDF that a non-technical stakeholder can read in under two minutes. Use `fpdf2` (`from fpdf import FPDF`) and `matplotlib` for any charts.

### Layout (all on one page, portrait, Letter size)

The report must fit on **exactly one page**. Use compact spacing, small fonts, and a dense but readable layout. Structure the page into these zones from top to bottom:

**Title bar (top ~15mm):**
- Report title (bold, 14pt): "Causal Analysis: Effect of [Treatment] on [Outcome]"
- Subtitle line (9pt, gray): method name, observation count, date

**Key finding box (~20mm):**
- A shaded highlight box with the headline result in one sentence: *"A one-unit increase in [treatment] causes [outcome] to [increase/decrease] by [ATE] [units]."*
- Below that, in the same box: 95% CI, p-value, and significance statement.

**Two-column middle section (~100mm):**

*Left column (~55% width) — Chart:*
- A single horizontal bar chart comparing the unadjusted (OLS) estimate and the causal (DML) estimate, with the DML bar showing 95% CI error bars. Use `matplotlib` to generate this as a PNG, then embed it with `pdf.image()`.

*Right column (~45% width) — Summary statistics table:*
- A compact table with rows for: ATE, 95% CI, Standard Error, p-value, Unadjusted estimate, Confounder bias %. Use alternating row shading for readability. Font size 8–9pt.

**Assumptions & confounders strip (~30mm):**
- Two side-by-side mini-sections:
  - *Confounders controlled for:* Bulleted list of included confounders (short names only).
  - *Key assumptions:* 3–4 bullet points (estimator used, log-transform if applied, winsorization if applied, ATE not heterogeneous effects).

**Footer strip (~15mm):**
- Limitations one-liner: *"Assumes all relevant confounders included. Unmeasured confounders could bias results."*
- Technical details one-liner: estimator name, library, inference method.

### Implementation guidelines

1. **Save the chart to a temp file**, embed with `pdf.image()`, then delete the temp file.
2. **Use font sizes 8–10pt** for body content, 14pt for title only. Line heights of 4–5mm to stay compact.
3. **Test that nothing overflows** the page. If content is too tall, reduce font sizes or trim assumption bullets before generating.
4. **Save the PDF** to the same directory as the user's data file, with a descriptive name like `Causal_Analysis_[Treatment]_[Outcome].pdf`.
5. **Clean up** any temporary image files after embedding them.

### Example code skeleton

```python
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os, tempfile

class OnePager(FPDF):
    pass  # No header/footer — single page, no pagination needed

pdf = OnePager('P', 'mm', 'Letter')
pdf.set_auto_page_break(auto=False)  # Must not spill to page 2
pdf.add_page()

# ... title bar, highlight box, two-column layout, assumptions, footer ...

# Chart generation
fig, ax = plt.subplots(figsize=(4, 2))
# ... bar chart code ...
tmp_chart = os.path.join(tempfile.gettempdir(), '_causal_chart.png')
fig.savefig(tmp_chart, dpi=150, bbox_inches='tight')
plt.close(fig)
pdf.image(tmp_chart, x=..., y=..., w=...)
os.remove(tmp_chart)

pdf.output('Causal_Analysis_Treatment_Outcome.pdf')
```
