"""
Data processing utilities for the Causal Analysis App.

Handles data loading, validation, type inference, and suggested transformations.
"""

import pandas as pd
import numpy as np
import json
import io
from typing import Optional
from scipy.stats import mstats


SAMPLE_DATA_URL = (
    "https://raw.githubusercontent.com/py-why/EconML/refs/heads/data/"
    "datasets/Pricing/pricing_sample.csv"
)


def load_sample_data() -> pd.DataFrame:
    """Load the EconML pricing sample dataset."""
    return pd.read_csv(SAMPLE_DATA_URL)


def load_uploaded_data(uploaded_file) -> pd.DataFrame:
    """Load data from an uploaded file (CSV or Excel)."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    elif name.endswith(".xlsx"):
        return pd.read_excel(uploaded_file, engine="openpyxl")
    elif name.endswith(".xls"):
        return pd.read_excel(uploaded_file, engine="xlrd")
    else:
        raise ValueError(f"Unsupported file type: {name}. Use CSV or Excel.")


def load_data_dictionary(uploaded_file) -> dict[str, str]:
    """Load a data dictionary from a CSV or Excel file.

    Expects columns named 'Variable' and 'Definition' (case-insensitive).
    Returns a dict mapping variable names to their definitions.
    """
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        dd = pd.read_csv(uploaded_file)
    elif name.endswith(".xlsx"):
        dd = pd.read_excel(uploaded_file, engine="openpyxl")
    elif name.endswith(".xls"):
        dd = pd.read_excel(uploaded_file, engine="xlrd")
    else:
        raise ValueError(f"Unsupported file type: {name}. Use CSV or Excel.")

    # Normalize column names to find Variable and Definition
    col_map = {c.strip().lower(): c for c in dd.columns}
    var_col = col_map.get("variable") or col_map.get("var") or col_map.get("column") or col_map.get("field") or col_map.get("name")
    def_col = col_map.get("definition") or col_map.get("description") or col_map.get("desc") or col_map.get("meaning") or col_map.get("label")

    if var_col is None or def_col is None:
        # Fall back to first two columns
        if len(dd.columns) >= 2:
            var_col = dd.columns[0]
            def_col = dd.columns[1]
        else:
            raise ValueError(
                "Could not find 'Variable' and 'Definition' columns. "
                "Expected columns named Variable/Column/Field and Definition/Description."
            )

    return {
        str(row[var_col]).strip(): str(row[def_col]).strip()
        for _, row in dd.iterrows()
        if pd.notna(row[var_col]) and pd.notna(row[def_col])
    }


def save_session_data(
    processed_data: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: list[str],
    variable_definitions: dict[str, str],
    processing_accepted: list[str],
) -> bytes:
    """Serialize processed data and metadata to a JSON-based file for later reload."""
    payload = {
        "version": 1,
        "treatment": treatment,
        "outcome": outcome,
        "confounders": confounders,
        "variable_definitions": variable_definitions,
        "processing_accepted": processing_accepted,
        "data_csv": processed_data.to_csv(index=False),
    }
    return json.dumps(payload, indent=2).encode("utf-8")


def load_session_data(uploaded_file) -> dict:
    """Load a previously saved session file. Returns dict with all saved state."""
    content = uploaded_file.read()
    payload = json.loads(content.decode("utf-8"))
    if payload.get("version") != 1:
        raise ValueError("Unsupported save file version.")
    payload["processed_data"] = pd.read_csv(io.StringIO(payload.pop("data_csv")))
    return payload


def get_column_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return a summary of each column: type, nulls, unique values, range."""
    summary = []
    for col in df.columns:
        info = {
            "Column": col,
            "Type": _friendly_dtype(df[col]),
            "Non-Null": df[col].notna().sum(),
            "Nulls": df[col].isna().sum(),
            "Unique": df[col].nunique(),
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            info["Min"] = df[col].min()
            info["Max"] = df[col].max()
            info["Mean"] = round(df[col].mean(), 2)
        else:
            info["Min"] = ""
            info["Max"] = ""
            info["Mean"] = ""
        summary.append(info)
    return pd.DataFrame(summary)


def _friendly_dtype(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return "Integer"
    elif pd.api.types.is_float_dtype(series):
        return "Decimal"
    elif pd.api.types.is_bool_dtype(series):
        return "Yes/No"
    elif pd.api.types.is_categorical_dtype(series) or pd.api.types.is_object_dtype(series):
        return "Category/Text"
    return str(series.dtype)


def infer_variable_definitions(df: pd.DataFrame) -> dict[str, str]:
    """Generate best-guess semantic definitions for each column based on its name."""
    definitions = {}

    # Name-based semantic meanings — prioritize these as the definition
    name_hints = {
        "price": "The price charged for a product or service",
        "cost": "The cost or expense incurred",
        "revenue": "Revenue or total earnings generated",
        "income": "Income or earnings level",
        "salary": "Salary or wage amount",
        "wage": "Hourly or periodic wage",
        "age": "Age of the individual or entity",
        "gender": "Gender of the individual",
        "sex": "Biological sex of the individual",
        "demand": "Demand level or quantity demanded",
        "quantity": "Quantity purchased or produced",
        "sales": "Number of sales or total sales volume",
        "date": "Date or timestamp of the observation",
        "time": "Time or duration of an event",
        "year": "Year of the observation",
        "month": "Month of the observation",
        "day": "Day of the observation",
        "region": "Geographic region or area",
        "country": "Country of the observation",
        "state": "State or province",
        "city": "City or municipality",
        "zip": "Zip or postal code area",
        "id": "Unique identifier (not useful for modeling)",
        "name": "Name or label (not useful for modeling)",
        "email": "Email address (not useful for modeling)",
        "flag": "Binary indicator for a specific condition",
        "indicator": "Binary indicator for a specific condition",
        "count": "Count of occurrences or events",
        "rate": "A rate or ratio measure",
        "pct": "A percentage measure",
        "percent": "A percentage measure",
        "ratio": "A ratio between two quantities",
        "score": "A score, rating, or index value",
        "rank": "A ranking or ordinal position",
        "weight": "A weight, importance, or mass measure",
        "duration": "How long something lasted",
        "frequency": "How often something occurs",
        "discount": "Discount amount or percentage applied",
        "profit": "Profit earned after costs",
        "margin": "Profit margin or markup",
        "conversion": "Whether a conversion event occurred",
        "churn": "Whether the customer churned or left",
        "retention": "Whether the customer was retained",
        "segment": "Customer or market segment grouping",
        "category": "A category or classification grouping",
        "channel": "Marketing, sales, or distribution channel",
        "campaign": "Marketing campaign identifier",
        "treatment": "Whether the treatment/intervention was applied",
        "control": "Whether this is a control group observation",
        "outcome": "The outcome or result being measured",
        "response": "Response to a treatment or stimulus",
        "target": "The target variable or goal metric",
        "education": "Education level attained",
        "experience": "Years of experience or expertise level",
        "tenure": "Length of time as a customer or employee",
        "loyalty": "Customer loyalty measure",
        "satisfaction": "Satisfaction score or rating",
        "engagement": "Level of engagement or activity",
        "spend": "Amount spent",
        "spending": "Total spending amount",
        "budget": "Budget allocated or available",
        "inventory": "Inventory or stock level",
        "shipping": "Shipping cost or method",
        "delivery": "Delivery time or method",
        "return": "Whether a return occurred or return amount",
        "refund": "Refund amount or indicator",
        "subscription": "Subscription status or type",
        "plan": "Service plan or tier",
        "status": "Current status or state",
        "type": "Type or classification",
        "size": "Size measurement",
        "population": "Population count",
        "density": "Density measure",
        "distance": "Distance measurement",
        "location": "Location identifier",
        "source": "Source or origin of the data",
        "platform": "Platform or system used",
        "device": "Device type used",
        "browser": "Web browser used",
        "visits": "Number of visits or sessions",
        "clicks": "Number of clicks",
        "views": "Number of views or impressions",
    }

    for col in df.columns:
        series = df[col]
        name_lower = col.lower().replace("_", " ").replace("-", " ")

        # Try to match a keyword from the column name
        definition = ""
        for keyword, meaning in name_hints.items():
            if keyword in name_lower.split():
                definition = meaning
                break

        # If no name match, fall back to a light structural hint
        if not definition:
            if pd.api.types.is_bool_dtype(series):
                definition = "A yes/no flag"
            elif pd.api.types.is_object_dtype(series) or pd.api.types.is_categorical_dtype(series):
                n = series.nunique()
                if n <= 10:
                    vals = series.dropna().unique()[:10]
                    definition = f"A grouping variable (values: {', '.join(str(v) for v in vals)})"
                else:
                    definition = "A text or categorical variable"
            elif pd.api.types.is_numeric_dtype(series):
                n = series.nunique()
                if n == 2:
                    definition = "A binary indicator (0/1)"
                elif n <= 5:
                    vals = sorted(series.dropna().unique())
                    definition = f"A coded grouping variable (values: {', '.join(str(v) for v in vals)})"

        definitions[col] = definition

    return definitions


def suggest_processing_steps(df: pd.DataFrame, treatment: str, outcome: str) -> list[dict]:
    """
    Suggest data processing steps based on data characteristics.
    Each suggestion is a dict: {id, description, reason, apply_fn_name, columns}.
    """
    suggestions = []

    # Check for missing values
    null_cols = [c for c in df.columns if df[c].isna().any()]
    if null_cols:
        suggestions.append({
            "id": "drop_nulls",
            "title": "Remove rows with missing values",
            "description": (
                f"Columns with missing data: {', '.join(null_cols)}. "
                "Rows with missing values will be removed to avoid estimation errors."
            ),
            "reason": "Causal estimation methods require complete data.",
        })

    # Log transform for positive skewed outcome/treatment
    for col, role in [(outcome, "outcome"), (treatment, "treatment")]:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            if (df[col] > 0).all() and df[col].skew() > 1.0:
                suggestions.append({
                    "id": f"log_{col}",
                    "title": f"Apply log transform to {role} ({col})",
                    "description": (
                        f"'{col}' is right-skewed (skewness={df[col].skew():.2f}) "
                        "and strictly positive. A log transform can improve model fit "
                        "and makes the treatment effect interpretable as an elasticity."
                    ),
                    "reason": "Log-log models estimate percentage effects (elasticities).",
                })
            elif (df[col] > 0).all() and df[col].max() / df[col].median() > 10:
                suggestions.append({
                    "id": f"log_{col}",
                    "title": f"Apply log transform to {role} ({col})",
                    "description": (
                        f"'{col}' has a wide range (max/median = "
                        f"{df[col].max() / df[col].median():.1f}). A log transform "
                        "can stabilize variance and improve estimation."
                    ),
                    "reason": "Wide-range variables often benefit from log scaling.",
                })

    # Winsorize for columns with extreme outliers
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if df[col].nunique() <= 5:
            continue  # skip low-cardinality (likely categorical)
        q01, q99 = df[col].quantile(0.01), df[col].quantile(0.99)
        q25, q75 = df[col].quantile(0.25), df[col].quantile(0.75)
        iqr = q75 - q25
        col_min, col_max = df[col].min(), df[col].max()
        if iqr > 0 and (col_min < q25 - 3.0 * iqr or col_max > q75 + 3.0 * iqr):
            suggestions.append({
                "id": f"winsorize_{col}",
                "title": f"Winsorize outliers in '{col}'",
                "description": (
                    f"'{col}' has extreme values (min={col_min:.2f}, max={col_max:.2f}, "
                    f"1st percentile={q01:.2f}, 99th percentile={q99:.2f}). "
                    "Winsorizing caps extreme values at the 1st/99th percentiles "
                    "to reduce the influence of outliers without removing rows."
                ),
                "reason": "Extreme outliers can distort causal estimates.",
            })

    # Detect low-cardinality numeric columns that might be categorical
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and df[col].nunique() <= 5 and col not in [treatment, outcome]:
            suggestions.append({
                "id": f"dummy_{col}",
                "title": f"Treat '{col}' as categorical",
                "description": (
                    f"'{col}' has only {df[col].nunique()} unique values. "
                    "It may represent categories rather than a continuous measure."
                ),
                "reason": "Categorical variables should be dummy-encoded for estimation.",
            })

    # Detect string/object columns that need encoding
    for col in df.columns:
        if (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_categorical_dtype(df[col])) and col not in [treatment, outcome]:
            suggestions.append({
                "id": f"dummy_{col}",
                "title": f"Encode '{col}' as dummy variables",
                "description": (
                    f"'{col}' is a text/category column with {df[col].nunique()} unique values. "
                    "It must be dummy-encoded for the causal model to use it."
                ),
                "reason": "Causal estimators require numeric inputs; text columns must be encoded.",
            })

    return suggestions


def apply_processing(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    confounders: list[str],
    winsorize_cols: list[str] | None = None,
    winsorize_limits: dict[str, tuple[float, float]] | None = None,
    log_cols: list[str] | None = None,
    dummy_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Apply processing steps and return (processed DataFrame, log of steps applied).

    Processing order:
    1. Drop rows where treatment or outcome is missing.
    2. Missing-indicator imputation for confounders (fill 0 + _missing flag column).
    3. Winsorize continuous variables.
    4. Log-transform selected variables.
    5. Dummy-encode categorical variables.

    Returns (df, steps_log) where steps_log is a list of human-readable descriptions.
    """
    df = df.copy()
    steps_log = []
    if winsorize_limits is None:
        winsorize_limits = {}
    if winsorize_cols is None:
        winsorize_cols = []
    if log_cols is None:
        log_cols = []
    if dummy_cols is None:
        dummy_cols = []

    # 1. Drop rows where treatment or outcome is missing
    t_nulls = df[treatment].isna().sum()
    o_nulls = df[outcome].isna().sum()
    if t_nulls > 0 or o_nulls > 0:
        before = len(df)
        df = df.dropna(subset=[treatment, outcome]).reset_index(drop=True)
        dropped = before - len(df)
        steps_log.append(f"Dropped {dropped} rows with missing treatment/outcome values")

    # 2. Missing-indicator imputation for confounders
    for col in confounders:
        if col in df.columns and df[col].isna().any():
            n_missing = df[col].isna().sum()
            df[f"{col}_missing"] = df[col].isna().astype(int)
            df[col] = df[col].fillna(0)
            steps_log.append(f"Imputed {n_missing} missing values in '{col}' (filled 0, added {col}_missing flag)")

    # 3. Winsorize continuous variables
    for col in winsorize_cols:
        if col in df.columns:
            lo, hi = winsorize_limits.get(col, (0.01, 0.01))
            df[col] = mstats.winsorize(df[col], limits=(lo, hi))
            steps_log.append(f"Winsorized '{col}' at ({lo*100:.1f}%, {hi*100:.1f}%)")

    # 4. Log-transform selected variables
    for col in log_cols:
        if col in df.columns:
            df[col] = np.log(df[col])
            steps_log.append(f"Log-transformed '{col}'")

    # 5. Dummy-encode categorical variables
    if dummy_cols:
        df = pd.get_dummies(df, columns=dummy_cols, drop_first=True)
        steps_log.append(f"Dummy-encoded: {', '.join(dummy_cols)}")

    return df, steps_log


def suggest_confounders(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    corr_threshold: float = 0.1,
    low_variance_pct: float = 0.95,
) -> dict:
    """
    Suggest which remaining columns should be confounders (W).

    Uses heuristics:
    - Correlation with treatment and outcome to categorise into strong / possible / unlikely.
    - Low-variance filter to flag near-constant columns.
    - Warning about non-numeric columns that were excluded.

    Returns dict with keys: strong, possible, unlikely, low_variance,
    non_numeric_excluded, explanation.
    """
    excluded_roles = {treatment, outcome}
    remaining = [c for c in df.columns if c not in excluded_roles]

    # Identify non-numeric columns
    numeric_cols = [c for c in remaining if pd.api.types.is_numeric_dtype(df[c])]
    non_numeric = [c for c in remaining if not pd.api.types.is_numeric_dtype(df[c])]

    # Correlation with treatment & outcome (absolute value)
    corr_with_t = {}
    corr_with_y = {}
    for col in numeric_cols:
        corr_with_t[col] = abs(df[col].corr(df[treatment]))
        corr_with_y[col] = abs(df[col].corr(df[outcome]))

    # Categorise
    strong, possible, unlikely = [], [], []
    for col in numeric_cols:
        ct = corr_with_t.get(col, 0)
        cy = corr_with_y.get(col, 0)
        if np.isnan(ct):
            ct = 0
        if np.isnan(cy):
            cy = 0
        if ct >= corr_threshold and cy >= corr_threshold:
            strong.append(col)
        elif ct >= corr_threshold or cy >= corr_threshold:
            possible.append(col)
        else:
            unlikely.append(col)

    # Low-variance filter: flag columns where a single value dominates
    low_variance = []
    for col in numeric_cols:
        if df[col].value_counts(normalize=True).iloc[0] >= low_variance_pct:
            low_variance.append(col)

    explanation = (
        "**Confounders (W)** are variables that may affect both the treatment and the outcome. "
        "We control for them to get an unbiased estimate of the treatment effect.\n\n"
        "We've grouped variables based on their correlation with the treatment and outcome:"
    )

    return {
        "strong": strong,
        "possible": possible,
        "unlikely": unlikely,
        "low_variance": low_variance,
        "non_numeric_excluded": non_numeric,
        "corr_with_treatment": corr_with_t,
        "corr_with_outcome": corr_with_y,
        "explanation": explanation,
    }


def get_llm_confounder_prompt(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    variable_definitions: dict[str, str] | None = None,
) -> str:
    """Build the default LLM prompt for confounder suggestion."""
    excluded_roles = {treatment, outcome}
    candidates = [c for c in df.columns if c not in excluded_roles]
    if variable_definitions is None:
        variable_definitions = {}

    # Build a compact column summary for the prompt
    col_info_lines = []
    for col in candidates:
        dtype = "numeric" if pd.api.types.is_numeric_dtype(df[col]) else "text/categorical"
        nunique = df[col].nunique()
        sample_vals = df[col].dropna().unique()[:5].tolist()
        defn = variable_definitions.get(col, "")
        defn_str = f' — Definition: "{defn}"' if defn else ""
        col_info_lines.append(
            f"  - {col} ({dtype}, {nunique} unique values, examples: {sample_vals}){defn_str}"
        )
    col_info = "\n".join(col_info_lines)

    # Include treatment/outcome definitions if available
    role_defs = ""
    t_def = variable_definitions.get(treatment, "")
    o_def = variable_definitions.get(outcome, "")
    if t_def or o_def:
        role_defs = "\n**Variable context:**\n"
        if t_def:
            role_defs += f'  - Treatment "{treatment}": {t_def}\n'
        if o_def:
            role_defs += f'  - Outcome "{outcome}": {o_def}\n'

    return f"""You are a causal inference expert. I am running a causal analysis and need help identifying confounders.

**My causal question:**
- Treatment (action): {treatment}
- Outcome (result): {outcome}
{role_defs}
**Candidate variables** (not yet assigned a role):
{col_info}

**Your task:**
For each candidate variable, classify it as one of:
- "strong_confounder": likely influences BOTH the treatment and the outcome (omitting it would bias the estimate)
- "possible_confounder": plausibly influences one of treatment or outcome, worth controlling for
- "unlikely_confounder": unlikely to cause bias; low priority for inclusion

For each variable, provide a brief rationale (1-2 sentences) explaining your reasoning based on domain knowledge.

**Respond in this exact JSON format:**
{{
  "variables": [
    {{"name": "var_name", "category": "strong_confounder", "rationale": "..."}},
    ...
  ]
}}

Only output valid JSON. Do not include markdown formatting or code fences."""


def suggest_confounders_llm(
    api_key: str,
    prompt: str,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Call OpenAI to classify candidate variables as confounders.

    Returns dict with keys: variables (list of dicts), raw_response, error.
    """
    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a causal inference expert. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        parsed = json.loads(raw)
        return {"variables": parsed.get("variables", []), "raw_response": raw, "error": None}
    except json.JSONDecodeError:
        return {"variables": [], "raw_response": raw, "error": f"Could not parse LLM response as JSON."}
    except Exception as e:
        return {"variables": [], "raw_response": "", "error": str(e)}


def suggest_treatment_outcome_llm(
    api_key: str,
    question: str,
    columns: list[str],
    variable_definitions: dict[str, str],
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Use an LLM to suggest treatment and outcome columns based on a causal question.

    Returns dict with keys: treatment, outcome, reasoning, error.
    """
    from openai import OpenAI

    col_info_lines = []
    for col in columns:
        defn = variable_definitions.get(col, "")
        defn_str = f' — {defn}' if defn else ""
        col_info_lines.append(f"  - {col}{defn_str}")
    col_info = "\n".join(col_info_lines)

    prompt = f"""You are a causal inference expert. A user wants to answer a causal question using their dataset.

**User's question:** {question}

**Available columns in the dataset:**
{col_info}

**Your task:**
Identify which column is the most appropriate **treatment** (the action/intervention being studied) and which is the most appropriate **outcome** (the result being measured).

**Respond in this exact JSON format:**
{{
  "treatment": "column_name",
  "outcome": "column_name",
  "reasoning": "Brief explanation of why these columns match the question"
}}

Only output valid JSON. Do not include markdown formatting or code fences."""

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a causal inference expert. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        parsed = json.loads(raw)
        return {
            "treatment": parsed.get("treatment", ""),
            "outcome": parsed.get("outcome", ""),
            "reasoning": parsed.get("reasoning", ""),
            "error": None,
        }
    except json.JSONDecodeError:
        return {"treatment": "", "outcome": "", "reasoning": "", "error": "Could not parse LLM response as JSON."}
    except Exception as e:
        return {"treatment": "", "outcome": "", "reasoning": "", "error": str(e)}


# ---------------------------------------------------------------------------
# LLM Causal Graph — pairwise causal direction approach
# ---------------------------------------------------------------------------

def _build_causal_direction_prompt(
    variable_pairs: list[tuple[str, str]],
    metadata: dict[str, str],
    treatment: str,
    outcome: str,
    domain_knowledge: str = "",
) -> str:
    """Build a prompt that asks the LLM to determine causal direction for each variable pair."""
    return f"""You are a causal inference expert. I am running a causal analysis where the treatment is "{treatment}" and the outcome is "{outcome}". I need to determine which candidate variables are confounders — variables that causally influence BOTH the treatment and the outcome.

For each variable pair below, determine the most plausible causal direction.

**Your Objective:**
For each pair, return a JSON array where each element has:
    - node1: The first variable in the pair.
    - node2: The second variable in the pair.
    - Causal Direction: Must be one of:
        1) "1 Causes 2" – if node1 directly causes node2.
        2) "2 Causes 1" – if node2 directly causes node1.
        3) "No Relationship" – if neither variable causes the other.
    - Reasoning: A concise, one-sentence justification for the assigned direction.

**Rules:**
    - Only record direct causal relationships.
    - Avoid inferring causality from correlation alone.

**Domain Knowledge:**
{domain_knowledge}

**Variable pair list:** {variable_pairs}

**Metadata (variable definitions):** {json.dumps(metadata)}

**Respond with a JSON array only. No markdown code fences or extra text.**"""


def _parse_causal_direction_response(raw: str) -> list[dict]:
    """Parse the LLM response into a list of causal direction dicts."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return json.loads(raw)


def _build_adjacency_from_directions(
    directions: list[dict],
    nodes: list[str],
) -> dict[str, dict[str, int]]:
    """
    Build a directed adjacency dict from causal direction results.
    Returns {source: {target: 1}} for all causal edges.
    """
    adj = {n: {m: 0 for m in nodes} for n in nodes}
    for row in directions:
        n1 = row.get("node1", "")
        n2 = row.get("node2", "")
        d = row.get("Causal Direction", "")
        if d == "1 Causes 2" and n1 in adj and n2 in adj:
            adj[n1][n2] = 1
        elif d == "2 Causes 1" and n1 in adj and n2 in adj:
            adj[n2][n1] = 1
    return adj


def _get_ancestors(adj: dict[str, dict[str, int]], node: str) -> set[str]:
    """Find all ancestors (direct and indirect parents) of a node in the adjacency dict."""
    ancestors = set()
    queue = [node]
    while queue:
        current = queue.pop(0)
        for src, targets in adj.items():
            if targets.get(current, 0) == 1 and src not in ancestors and src != node:
                ancestors.add(src)
                queue.append(src)
    return ancestors


def generate_causal_graph_confounders(
    api_key: str,
    variable_list: list[str],
    treatment: str,
    outcome: str,
    metadata: dict[str, str],
    domain_knowledge: str = "",
    model: str = "gpt-4o-mini",
    chunksize: int = 80,
) -> dict:
    """
    Use the LLM to determine each candidate variable's causal relationship with
    the treatment and outcome, then identify confounders as variables that
    causally influence both.

    Returns dict with keys:
        - confounders: list of suggested confounder names
        - directions: list of pairwise direction dicts (with Reasoning)
        - adjacency: {src: {tgt: 0|1}} adjacency dict
        - error: error string or None
    """
    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key)

        # Only pair each candidate variable with treatment and outcome
        candidates = [v for v in variable_list if v not in (treatment, outcome)]
        all_pairs = []
        for var in candidates:
            all_pairs.append((var, treatment))
            all_pairs.append((var, outcome))

        # Chunk pairs to avoid token limits
        chunks = [all_pairs[i:i + chunksize] for i in range(0, len(all_pairs), chunksize)]
        all_directions = []

        for chunk in chunks:
            prompt = _build_causal_direction_prompt(chunk, metadata, treatment, outcome, domain_knowledge)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a causal inference expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()
            parsed = _parse_causal_direction_response(raw)
            all_directions.extend(parsed)

        # Build adjacency matrix
        adj = _build_adjacency_from_directions(all_directions, variable_list)

        # Find confounders: variables that causally influence both treatment and outcome
        treatment_parents = {src for src in candidates if adj.get(src, {}).get(treatment, 0) == 1}
        outcome_parents = {src for src in candidates if adj.get(src, {}).get(outcome, 0) == 1}

        # Confounders = variables that influence both treatment and outcome
        confounders_set = treatment_parents & outcome_parents

        return {
            "confounders": sorted(confounders_set),
            "directions": all_directions,
            "adjacency": adj,
            "error": None,
        }
    except json.JSONDecodeError:
        return {"confounders": [], "directions": [], "adjacency": {}, "error": "Could not parse LLM response as JSON."}
    except Exception as e:
        return {"confounders": [], "directions": [], "adjacency": {}, "error": str(e)}
