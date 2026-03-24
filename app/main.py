"""
Causal Analysis Companion — A guided causal inference app for domain experts.

Run with: streamlit run app/main.py
"""

import streamlit as st
import pandas as pd
import numpy as np

from data_utils import (
    load_sample_data,
    load_uploaded_data,
    load_data_dictionary,
    get_column_summary,
    apply_processing,
    suggest_treatment_outcome_llm,
    generate_causal_graph_confounders,
    infer_variable_definitions,
    save_session_data,
    load_session_data,
)
from estimation import (
    ESTIMATORS,
    get_estimator_recommendation,
    compute_unconditional_difference,
    fit_model,
    create_effect_plot,
    get_effect_summary,
    get_individual_effects_df,
    generate_results_pdf,
)


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Causal Analysis Companion",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Scroll to top on every rerun + left-align sidebar buttons
st.html("""
<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);</script>
<style>
    section[data-testid="stSidebar"] button {
        text-align: left !important;
        justify-content: flex-start !important;
    }
    section[data-testid="stSidebar"] button p,
    section[data-testid="stSidebar"] button span,
    section[data-testid="stSidebar"] button div {
        text-align: left !important;
        width: 100% !important;
    }
</style>
""")


# ── Session state defaults ───────────────────────────────────────────────────

DEFAULTS = {
    "step": 0,
    "raw_data": None,
    "processed_data": None,
    "treatment": None,
    "outcome": None,
    "confounders": [],
    "estimator": None,
    "results": None,
    "processing_log": [],
    "variable_definitions": {},
    "causal_question": "",
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Sidebar progress tracker ────────────────────────────────────────────────

STEPS = {
    0: "🏠 Overview",
    1: "📂 Choose Data",
    2: "🔍 Review Data",
    3: "🎯 Define Your Question – Treatment & Outcome",
    4: "⚖️ Define Your Question – Confounders",
    5: "🔧 Process Data",
    6: "✅ Final Checks",
    7: "🧪 Choose Estimation Method",
    8: "⚙️ Run Analysis",
    9: "📊 Results & Actions",
}

with st.sidebar:
    st.title("🔬 Analysis Steps")
    st.markdown("---")
    for num, label in STEPS.items():
        if num == 0:
            display = label
        else:
            display = f"Step {num}: {label}"
        if num < st.session_state.step:
            if st.button(f"✅ {display}", key=f"nav_{num}", use_container_width=True):
                st.session_state.step = num
                st.rerun()
        elif num == st.session_state.step:
            st.markdown(f"**▶ {display}**")
        else:
            st.markdown(f"⬜ {display}")
    st.markdown("---")
    if st.session_state.step > 0:
        if st.button("🔄 Start Over"):
            for key, val in DEFAULTS.items():
                st.session_state[key] = val
            st.rerun()
    st.markdown("---")
    st.text_input(
        "🔑 OpenAI API Key",
        type="password",
        key="openai_api_key",
        help="Optional. Used for AI-assisted suggestions in Steps 3 and 4.",
    )
    st.markdown("---")
    st.link_button(
        "📖 View Causal Analysis Skill",
        "https://github.com/msr-new-england/CausalAI/blob/main/.github/instructions/causal.instructions.md",
        use_container_width=True,
    )


if st.session_state.step == 0:
    st.title("🔬 Causal Analysis Companion")
    st.markdown("#### Go beyond correlation — discover what actually *causes* what.")

    st.markdown("---")

    # ── What is Causal Analysis? ─────────────────────────────────────────────
    st.header("What is Causal Analysis?")

    col_corr, col_cause = st.columns(2)
    with col_corr:
        st.markdown(
"### 📊 Correlation\n"
'*"People who receive our email campaign spend more."*\n\n'
"Correlation tells you two things move together — but not **why**. "
"Maybe the campaign drives purchases. Or maybe you're already targeting "
"your best customers, and they'd spend more anyway.\n\n"
"**Correlation ≠ Causation**"
        )
    with col_cause:
        st.markdown(
"### 🔬 Causal Analysis\n"
'*"Sending the email campaign causes customers to spend \\$25 more."*\n\n'
"Causal analysis isolates the **true effect** of an action by accounting "
"for other factors (confounders) that influence both the action and the "
"outcome. It answers: *What would have happened differently?*\n\n"
"**Causation → Actionable decisions**"
        )

    st.markdown("---")

    # ── Illustrated Example ──────────────────────────────────────────────────
    st.header("A Concrete Example")

    st.markdown(
"Imagine you're a marketing manager wondering: **Does our email campaign increase purchases?**"
    )
    st.markdown(
"You look at the data and see that customers who received the email spent **\\$120 on average**, "
"while those who didn't spent **\\$80**. That's a **\\$40 difference** — case closed?"
    )
    st.markdown(
"**Not so fast.** Your targeting system sends emails to your *most engaged* customers — "
"people who visit the website often, have bought before, and have higher incomes. "
"These customers would spend more *regardless* of the email."
    )

    # Visual: confounding diagram
    st.markdown("")
    dc1, dc2, dc3 = st.columns([1, 2, 1])
    with dc2:
        st.code(
"        Confounders\n"
"     (income, past purchases,\n"
"      website visits, etc.)\n"
"           /       \\\n"
"          v         v\n"
"     Treatment --> Outcome\n"
"      (email)     (purchases)\n"
"          ?\n"
"    What is the\n"
"    true effect?",
            language=None,
        )

    st.markdown(
"**Causal analysis separates the true email effect from the confounding factors.** "
"After controlling for income, past purchases, and website activity, the real effect "
"might be **\\$25** — still meaningful, but quite different from the naive \\$40."
    )
    st.markdown("This app walks you through that process step by step.")

    st.markdown("---")

    # ── How This App Works ───────────────────────────────────────────────────
    st.header("How This App Works")
    st.markdown("This app guides you through **9 steps** to run a rigorous causal analysis — no coding required.")

    steps_overview = [
        ("📂", "Choose Data", "Upload your CSV/Excel file or use our sample dataset."),
        ("🔍", "Review Data", "Inspect your data, edit variable definitions, and upload a data dictionary."),
        ("🎯", "Treatment & Outcome", "Define your causal question: what action (treatment) affects what result (outcome)? AI can help suggest these."),
        ("⚖️", "Confounders", "Identify variables that influence both treatment and outcome. Use an LLM-powered causal graph or select manually."),
        ("🔧", "Process Data", "Handle missing values, cap outliers, and encode categorical variables so the model can use them."),
        ("✅", "Final Checks", "Verify treatment predictability and overlap — pre-flight diagnostics before estimation."),
        ("🧪", "Choose Method", "Pick an estimation method: Linear Double ML (simple) or Causal Forest (flexible)."),
        ("⚙️", "Run Analysis", "Fit the causal model using Microsoft's EconML library."),
        ("📊", "Results", "See your treatment effect estimate with visualizations, plain-language interpretation, and downloadable results."),
    ]

    for i, (icon, title, desc) in enumerate(steps_overview, 1):
        st.markdown(f"**Step {i}: {icon} {title}** — {desc}")

    st.markdown("---")

    # ── Key Concepts ─────────────────────────────────────────────────────────
    st.header("Key Concepts")

    conc1, conc2, conc3 = st.columns(3)
    with conc1:
        st.markdown(
"**🎯 Treatment**\n\n"
"The action or intervention you want to measure. "
"Examples: sending an email, offering a discount, changing a price."
        )
    with conc2:
        st.markdown(
"**📈 Outcome**\n\n"
"The result you care about. "
"Examples: purchase amount, click-through rate, customer retention."
        )
    with conc3:
        st.markdown(
"**⚖️ Confounders**\n\n"
"Variables that affect *both* the treatment and outcome. "
"If you don't control for them, your estimate will be biased. "
"Examples: income, past behavior, demographics."
        )

    st.markdown("---")

    if st.button("🚀 Get Started", type="primary", use_container_width=True):
        st.session_state.step = 1
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Choose Data
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 1:
    st.header("Step 1: Choose Your Data")
    st.markdown(
        "Start by selecting the dataset you want to analyze. "
        "You can upload your own CSV/Excel file, or use our built-in sample dataset."
    )

    tab_upload, tab_sample, tab_saved = st.tabs(["📤 Upload My Data", "📦 Use Sample Data", "💾 Load Saved Session"])

    with tab_upload:
        uploaded = st.file_uploader(
            "Upload a CSV or Excel file",
            type=["csv", "xlsx", "xls"],
            help="Your data should have one row per observation with columns for the treatment, outcome, and other variables.",
        )
        if uploaded:
            try:
                data = load_uploaded_data(uploaded)
                st.session_state.raw_data = data
                st.success(f"Loaded **{uploaded.name}** — {len(data):,} rows, {len(data.columns)} columns.")
                st.dataframe(data.head(10), use_container_width=True)
            except Exception as e:
                st.error(f"Could not read file: {e}")

        # Optional data dictionary upload
        st.markdown("---")
        st.markdown("**📖 Data Dictionary (Optional)**")
        st.markdown(
            "Upload a CSV or Excel file with columns `Variable` and `Definition` "
            "to provide descriptions for your variables. If not provided, "
            "definitions will be auto-generated from column names."
        )
        dict_file = st.file_uploader(
            "Upload a data dictionary",
            type=["csv", "xlsx", "xls"],
            key="dict_uploader",
            help="Expected columns: Variable, Definition. Column names are matched flexibly (e.g., 'Column', 'Description' also work).",
        )
        if dict_file and not st.session_state.get("_dict_loaded"):
            try:
                dd = load_data_dictionary(dict_file)
                st.session_state.variable_definitions = dd
                st.session_state["_dict_loaded"] = True
                st.session_state["_def_editor_version"] = st.session_state.get("_def_editor_version", 0) + 1
                st.success(f"Loaded definitions for **{len(dd)}** variables.")
                with st.expander("Preview definitions"):
                    st.dataframe(
                        pd.DataFrame(list(dd.items()), columns=["Variable", "Definition"]),
                        use_container_width=True,
                        hide_index=True,
                    )
            except Exception as e:
                st.error(f"Could not read data dictionary: {e}")
        elif dict_file and st.session_state.get("_dict_loaded"):
            st.success(f"✅ Data dictionary loaded ({len(st.session_state.variable_definitions)} definitions).")

    with tab_sample:
        st.markdown(
            "**Online Media Company Pricing Dataset**\n\n"
            "~10,000 users from an online media platform. The company tested different "
            "price discounts and measured demand (song purchases). "
            "Variables include user demographics, behavior history, and the experimental treatment."
        )
        if st.button("Load Sample Dataset", type="primary"):
            with st.spinner("Downloading sample data..."):
                st.session_state.raw_data = load_sample_data()
            st.success(f"Loaded sample data — {len(st.session_state.raw_data):,} rows, {len(st.session_state.raw_data.columns)} columns.")
            st.dataframe(st.session_state.raw_data.head(10), use_container_width=True)

    with tab_saved:
        st.markdown(
            "Load a previously saved session (`.json` file) to resume where you left off. "
            "This restores your processed data, variable definitions, and all settings."
        )
        saved_file = st.file_uploader(
            "Upload a saved session file",
            type=["json"],
            key="saved_session_uploader",
            help="This is the .json file you downloaded from a previous session.",
        )
        if saved_file and st.button("Load Saved Session", type="primary", key="load_saved_btn"):
            try:
                session = load_session_data(saved_file)
                st.session_state.raw_data = session["processed_data"]
                st.session_state.processed_data = session["processed_data"]
                st.session_state.treatment = session["treatment"]
                st.session_state.outcome = session["outcome"]
                st.session_state.confounders = session.get("confounders", [])
                st.session_state.variable_definitions = session.get("variable_definitions", {})
                st.session_state.processing_log = session.get("processing_accepted", [])
                st.success(
                    f"✅ Session restored — {len(session['processed_data']):,} rows, "
                    f"treatment: `{session['treatment']}`, outcome: `{session['outcome']}`"
                )
                st.dataframe(session["processed_data"].head(10), use_container_width=True)
                st.info("Click **Continue** below to pick up where you left off (Step 7).")
            except Exception as e:
                st.error(f"Could not load session: {e}")

    if st.session_state.raw_data is not None:
        if st.button("Continue →", type="primary", key="step1_next"):
            if st.session_state.processed_data is not None and st.session_state.treatment is not None:
                st.session_state.step = 7
            else:
                st.session_state.step = 2
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Review & Process Data
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 2:
    st.header("Step 2: Review Data")
    df = st.session_state.raw_data

    # Variable definitions — primary focus of this step
    st.subheader("📝 Variable Definitions")
    if st.session_state.variable_definitions:
        # Check how many columns have definitions from the dictionary
        matched = [c for c in df.columns if c in st.session_state.variable_definitions]
        unmatched = [c for c in df.columns if c not in st.session_state.variable_definitions]
        if unmatched:
            # Auto-fill missing definitions
            inferred = infer_variable_definitions(df)
            for col in unmatched:
                if col not in st.session_state.variable_definitions and inferred.get(col):
                    st.session_state.variable_definitions[col] = inferred[col]
            st.warning(
                f"Definitions loaded for **{len(matched)}** of {len(df.columns)} variables from data dictionary. "
                f"Auto-generated definitions for: **{', '.join(unmatched)}**. Review and edit below."
            )
        else:
            st.success(f"Definitions loaded for all **{len(matched)}** variables from data dictionary.")
    else:
        st.markdown(
            "No data dictionary was uploaded. Definitions have been auto-generated from column names. "
            "Review and edit them below — they will be used for **LLM-assisted confounder suggestion** in Step 4."
        )
        st.session_state.variable_definitions = infer_variable_definitions(df)

    # Build editable table with definitions
    # Build the INITIAL base DataFrame only once; let data_editor track edits from there
    editor_version = st.session_state.get("_def_editor_version", 0)
    base_key = f"_def_base_v{editor_version}"
    if base_key not in st.session_state:
        # First time (or after dictionary upload bumps version): build from auto-detected types
        if "variable_types" not in st.session_state:
            st.session_state.variable_types = {
                col: "Numeric" if pd.api.types.is_numeric_dtype(df[col]) else "Categorical"
                for col in df.columns
            }
        for col in df.columns:
            if col not in st.session_state.variable_types:
                st.session_state.variable_types[col] = "Numeric" if pd.api.types.is_numeric_dtype(df[col]) else "Categorical"

        rows = []
        for col in df.columns:
            rows.append({
                "Variable": col,
                "Type": st.session_state.variable_types.get(col, "Numeric"),
                "Definition": st.session_state.variable_definitions.get(col, ""),
            })
        st.session_state[base_key] = pd.DataFrame(rows)

    def_df = st.session_state[base_key]

    st.info(
        "✏️ **This table is editable!** Click any cell in the **Type** or **Definition** columns to make changes.\n\n"
        "- **Type** — Click to switch between *Numeric* and *Categorical*. "
        "If a numeric code (e.g. country code) is actually categorical, change it here so it gets dummy-encoded correctly.\n"
        "- **Definition** — Click to edit the description. Good definitions improve LLM-assisted confounder suggestions in Step 4.",
        icon="✏️",
    )

    edited_def_df = st.data_editor(
        def_df,
        column_config={
            "Variable": st.column_config.TextColumn("Variable", disabled=True),
            "Type": st.column_config.SelectboxColumn("Type", options=["Numeric", "Categorical"], required=True),
            "Definition": st.column_config.TextColumn("Definition", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        key=f"var_definitions_editor_{editor_version}",
    )
    # Save definitions back to session state
    st.session_state.variable_definitions = {
        row["Variable"]: row["Definition"]
        for _, row in edited_def_df.iterrows()
        if row["Definition"]
    }
    # Save type overrides
    st.session_state.variable_types = {
        row["Variable"]: row["Type"]
        for _, row in edited_def_df.iterrows()
    }
    # Apply type corrections to the raw data: convert user-marked Categorical columns to string
    for col in df.columns:
        if st.session_state.variable_types.get(col) == "Categorical" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].astype(str)
        elif st.session_state.variable_types.get(col) == "Numeric" and not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    st.session_state.raw_data = df

    st.markdown("---")
    st.subheader("Data Overview")
    st.dataframe(get_column_summary(df), use_container_width=True, hide_index=True)

    st.subheader("Sample Rows")
    st.dataframe(df.head(10), use_container_width=True)

    # ── Navigation ───────────────────────────────────────────────────────
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 1
            st.rerun()
    with col_next:
        if st.button("Continue →", type="primary", key="step2_next"):
            st.session_state.step = 3
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Select Treatment & Outcome
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 3:
    st.header("Step 3: Define Your Question – Treatment & Outcome")
    df = st.session_state.raw_data

    st.markdown(
        "Causal analysis answers questions like: "
        "*'What is the effect of **[treatment]** on **[outcome]**?'* "
        "For example: *'What is the effect of **price discounts** on **song purchases**?'*"
    )

    # Causal question input + AI suggestion
    st.subheader("💬 Describe Your Question")
    causal_question = st.text_area(
        "What causal question do you want to answer?",
        value=st.session_state.causal_question,
        placeholder="e.g., Does offering a discount increase the number of purchases?",
        key="causal_question_input",
        help="Describe your question in plain language. We'll use AI to suggest the treatment and outcome variables.",
    )
    st.session_state.causal_question = causal_question

    api_key = st.session_state.get("openai_api_key", "")
    can_suggest = bool(causal_question and api_key)
    if st.button("🤖 Suggest Treatment & Outcome", type="secondary", key="suggest_t_o", disabled=not can_suggest):
        with st.spinner("Asking the LLM..."):
            result = suggest_treatment_outcome_llm(
                api_key=api_key,
                question=causal_question,
                columns=list(df.columns),
                variable_definitions=st.session_state.get("variable_definitions", {}),
            )
        if result["error"]:
            st.error(f"Error: {result['error']}")
        else:
            if result["treatment"] in list(df.columns):
                st.session_state.treatment = result["treatment"]
                st.session_state.treatment_select = result["treatment"]
            if result["outcome"] in list(df.columns):
                st.session_state.outcome = result["outcome"]
                st.session_state.outcome_select = result["outcome"]
            if result["reasoning"]:
                st.session_state["_llm_to_reasoning"] = result["reasoning"]
            st.rerun()
    if not api_key:
        st.caption("💡 Enter an OpenAI API key in the sidebar to use AI suggestions, or select treatment and outcome manually below.")

    if st.session_state.get("_llm_to_reasoning"):
        st.info(f"💡 {st.session_state['_llm_to_reasoning']}")

    # Manual treatment/outcome selection
    st.markdown("---")
    st.subheader("Confirm Treatment & Outcome")

    cols = list(df.columns)
    placeholder = "— Select a variable —"
    treatment_options = [placeholder] + cols

    # Initialize widget keys from session state if not already set
    if "treatment_select" not in st.session_state:
        st.session_state.treatment_select = st.session_state.treatment if st.session_state.treatment in cols else placeholder
    if "outcome_select" not in st.session_state:
        st.session_state.outcome_select = st.session_state.outcome if st.session_state.outcome in cols else placeholder

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🎯 Treatment** — The action or intervention whose effect you want to measure.")
        treatment = st.selectbox(
            "Treatment variable",
            treatment_options,
            key="treatment_select",
        )

    with col2:
        st.markdown("**📈 Outcome** — The result you want to measure the effect on.")
        remaining = [placeholder] + [c for c in cols if c != treatment]
        outcome = st.selectbox(
            "Outcome variable",
            remaining,
            key="outcome_select",
        )

    # Only store real column selections
    st.session_state.treatment = treatment if treatment != placeholder else None
    st.session_state.outcome = outcome if outcome != placeholder else None

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 2
            st.rerun()
    with col_next:
        both_selected = treatment != placeholder and outcome != placeholder
        if st.button("Continue →", type="primary", key="step3_next", disabled=not both_selected):
            st.session_state.step = 4
            st.rerun()
        if not both_selected:
            st.caption("Select both a treatment and outcome variable to continue.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Confirm Confounders
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 4:
    st.header("Step 4: Define Your Question – Confounders")
    df = st.session_state.raw_data
    treatment = st.session_state.treatment
    outcome = st.session_state.outcome

    # Callbacks to track which tab the user is actively editing
    def _set_source_llm():
        st.session_state["_confounder_source"] = "llm"

    def _set_source_manual():
        st.session_state["_confounder_source"] = "manual"

    excluded_roles = {treatment, outcome}
    candidate_vars = [c for c in df.columns if c not in excluded_roles]

    tab_llm, tab_manual = st.tabs(["🤖 LLM Causal Graph", "✏️ Manual Selection"])

    # ── Tab 1: LLM Causal Graph (default) ──────────────────────────────────
    with tab_llm:
        st.markdown(
            "Use an LLM to determine each candidate variable's causal relationship with "
            "the **treatment** and **outcome**. Variables that the LLM determines causally "
            "influence **both** are identified as confounders."
        )

        api_key = st.session_state.get("openai_api_key", "")
        if not api_key:
            st.warning("⚠️ Add an OpenAI API key in the sidebar to use LLM-assisted suggestions.")

        llm_model = st.selectbox(
            "Model",
            ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
            index=0,
            key="llm_model",
        )

        # Domain knowledge text area
        domain_knowledge = st.text_area(
            "Domain knowledge (optional)",
            value=st.session_state.get("_llm_domain_knowledge", ""),
            height=150,
            key="llm_domain_knowledge_input",
            help="Provide any domain context to help the LLM understand causal relationships between your variables.",
            placeholder="e.g., This dataset is about e-commerce. Discounts are set by the marketing team and are not based on individual customer behavior...",
        )
        st.session_state["_llm_domain_knowledge"] = domain_knowledge

        # Build metadata from variable definitions
        var_defs = st.session_state.get("variable_definitions", {})
        all_vars = [treatment, outcome] + candidate_vars

        n_pairs = len(candidate_vars) * 2
        st.caption(f"📊 {len(candidate_vars)} candidate variables → {n_pairs} pairs to evaluate (each vs. treatment & outcome)")

        can_run = bool(api_key and len(candidate_vars) > 0)
        if st.button("🤖 Build Causal Graph", type="primary", key="run_llm_causal_graph", disabled=not can_run):
            with st.spinner(f"Asking the LLM to evaluate {n_pairs} variable pairs... This may take a moment."):
                result = generate_causal_graph_confounders(
                    api_key=api_key,
                    variable_list=all_vars,
                    treatment=treatment,
                    outcome=outcome,
                    metadata=var_defs,
                    domain_knowledge=domain_knowledge,
                    model=llm_model,
                )
            if result["error"]:
                st.error(f"Error: {result['error']}")
            else:
                st.session_state["_causal_graph_result"] = result
                st.session_state.confounders = result["confounders"]
                st.session_state["_confounder_source"] = "llm"
                st.rerun()

        # Display results if available
        if "_causal_graph_result" in st.session_state and st.session_state["_causal_graph_result"]:
            cg_result = st.session_state["_causal_graph_result"]

            # Show the causal direction table
            with st.expander("📋 Pairwise Causal Directions (from LLM)", expanded=False):
                dir_df = pd.DataFrame(cg_result["directions"])
                st.dataframe(dir_df, use_container_width=True, hide_index=True)

            # Show identified confounders
            suggested = cg_result["confounders"]
            not_suggested = [v for v in candidate_vars if v not in suggested]

            llm_rows = []
            for v in suggested:
                reasoning = ""
                for d in cg_result["directions"]:
                    if v in (d.get("node1", ""), d.get("node2", "")) and d.get("Causal Direction", "") != "No Relationship":
                        if (d.get("node1") == v or d.get("node2") == v) and (treatment in (d.get("node1", ""), d.get("node2", "")) or outcome in (d.get("node1", ""), d.get("node2", ""))):
                            reasoning = d.get("Reasoning", "")
                            break
                llm_rows.append({"Include": True, "Variable": v, "Role": "🎯 Confounder (causes both T & Y)", "Reasoning": reasoning})
            for v in not_suggested:
                llm_rows.append({"Include": False, "Variable": v, "Role": "⬜ Not identified as confounder", "Reasoning": ""})

            if llm_rows:
                st.subheader("⚖️ Confounders from Causal Graph")
                st.caption(
                    "Variables identified as **confounders** are those the LLM determined to causally influence "
                    "both the treatment and the outcome. Check or uncheck to include/exclude."
                )
                llm_df = pd.DataFrame(llm_rows)
                edited_llm_df = st.data_editor(
                    llm_df,
                    column_config={
                        "Include": st.column_config.CheckboxColumn("Include", default=False),
                        "Variable": st.column_config.TextColumn("Variable", disabled=True),
                        "Role": st.column_config.TextColumn("Role", disabled=True),
                        "Reasoning": st.column_config.TextColumn("Reasoning", disabled=True, width="large"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="llm_confounder_table",
                    on_change=_set_source_llm,
                )
                llm_selected = edited_llm_df.loc[edited_llm_df["Include"], "Variable"].tolist()
                # Only write if the LLM tab is the active source
                if st.session_state.get("_confounder_source") == "llm":
                    st.session_state.confounders = llm_selected
            else:
                st.warning("No candidate variables to evaluate.")

    # ── Tab 2: Manual Selection ────────────────────────────────────────────
    with tab_manual:
        st.markdown(
            "Manually select which variables to include as **confounders** — "
            "variables that may influence both the treatment and the outcome."
        )

        if candidate_vars:
            # Sync checkbox keys to current confounders when source is not manual
            if st.session_state.get("_confounder_source") != "manual":
                current_conf = set(st.session_state.get("confounders", []))
                for v in candidate_vars:
                    st.session_state[f"_manual_conf_{v}"] = v in current_conf

            manual_selected = []
            for v in candidate_vars:
                checked = st.checkbox(
                    v,
                    value=v in set(st.session_state.get("confounders", [])),
                    key=f"_manual_conf_{v}",
                    on_change=_set_source_manual,
                )
                if checked:
                    manual_selected.append(v)

            # Only write if the manual tab is the active source
            if st.session_state.get("_confounder_source") == "manual":
                st.session_state.confounders = manual_selected
        else:
            st.warning("No numeric candidate variables available.")

    confounders = st.session_state.get("confounders", [])

    st.markdown("---")

    # Visual summary
    st.subheader("Your Causal Model")

    summary_md = f"""
| Role | Variable(s) |
|------|-------------|
| **Treatment** (what you're testing) | `{treatment}` |
| **Outcome** (what you're measuring) | `{outcome}` |
| **Confounders** (controlled for) | {', '.join(f'`{w}`' for w in confounders) if confounders else '_None_'} |
"""
    st.markdown(summary_md)

    excluded = [
        c for c in df.columns
        if c not in [treatment, outcome] + confounders
    ]
    if excluded:
        st.caption(f"ℹ️ Columns not used: {', '.join(excluded)}")

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 3
            st.rerun()
    with col_next:
        if st.button("Continue →", type="primary", key="step4_next"):
            st.session_state.step = 5
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Process Data
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 5:
    st.header("Step 5: Process Data")
    df = st.session_state.raw_data
    treatment = st.session_state.treatment
    outcome = st.session_state.outcome
    confounders = st.session_state.get("confounders", [])

    # ── 1. Missing Values ────────────────────────────────────────────────
    st.subheader("1️⃣ Missing Values")
    st.markdown(
        "Missing data can bias causal estimates. If the treatment or outcome is missing for a row, "
        "we cannot use that observation and it is **dropped**. For confounders, we use the "
        "**Missing Indicator Method** — fill missing values with 0 and add a binary flag column — "
        "so we preserve the sample size while letting the model learn whether missingness itself "
        "is informative."
    )

    t_nulls = df[treatment].isna().sum()
    o_nulls = df[outcome].isna().sum()
    conf_nulls = {c: df[c].isna().sum() for c in confounders if c in df.columns and df[c].isna().any()}

    if t_nulls == 0 and o_nulls == 0 and not conf_nulls:
        st.success("✅ No missing values detected.")
    else:
        if t_nulls > 0 or o_nulls > 0:
            st.markdown(
                f"**Treatment** (`{treatment}`): {t_nulls} missing &nbsp;|&nbsp; "
                f"**Outcome** (`{outcome}`): {o_nulls} missing"
            )
            st.caption("Rows with missing treatment or outcome will be **dropped**.")
        if conf_nulls:
            st.markdown("**Confounders with missing values** (will be imputed with 0 + missing indicator flag):")
            for c, n in conf_nulls.items():
                st.caption(f"  • `{c}`: {n} missing values")

    # ── 2. Variation Check ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("2️⃣ Variation Check")
    st.markdown(
        "Causal inference works by comparing what happens when the treatment varies. "
        "If the treatment or outcome has **zero variance** (every value is the same), "
        "there is nothing to compare and no effect can be estimated."
    )

    t_var = df[treatment].var()
    o_var = df[outcome].var()
    variation_ok = True
    if t_var == 0:
        st.error(f"⚠️ Treatment variable `{treatment}` has **zero variance**. The analysis cannot proceed.")
        variation_ok = False
    if o_var == 0:
        st.error(f"⚠️ Outcome variable `{outcome}` has **zero variance**. The analysis cannot proceed.")
        variation_ok = False
    if variation_ok:
        st.success(f"✅ Treatment variance: {t_var:.4f} &nbsp;|&nbsp; Outcome variance: {o_var:.4f}")

    # ── 3. Winsorize Continuous Variables ─────────────────────────────────
    st.markdown("---")
    st.subheader("3️⃣ Winsorize Continuous Variables")
    st.markdown(
        "Extreme outliers can disproportionately influence causal estimates, pulling results "
        "toward a few unusual observations rather than reflecting the typical effect. "
        "**Winsorizing** caps values at chosen percentiles (e.g., the 1st and 99th) so that "
        "outliers are brought in line without being removed entirely."
    )

    # Identify continuous numeric columns (exclude low-cardinality categoricals)
    all_analysis_cols = [treatment, outcome] + confounders
    continuous_cols = [
        c for c in all_analysis_cols
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() > 5
    ]

    # Auto-detect columns with outliers
    outlier_cols = []
    for col in continuous_cols:
        q01, q99 = df[col].quantile(0.01), df[col].quantile(0.99)
        col_min, col_max = df[col].min(), df[col].max()
        if col_min < q01 * 0.5 or col_max > q99 * 2.0:
            outlier_cols.append(col)

    winsorize_limits: dict[str, tuple[float, float]] = {}

    if outlier_cols:
        st.caption(f"Columns with detected outliers: {', '.join(outlier_cols)}")

    winsorize_selected = st.multiselect(
        "Select columns to winsorize",
        continuous_cols,
        default=outlier_cols,
        key="winsorize_cols",
    )
    for col in winsorize_selected:
        wcol1, wcol2 = st.columns(2)
        with wcol1:
            lo = st.number_input(
                f"Lower cap % for '{col}'",
                min_value=0.0, max_value=10.0, value=1.0, step=0.5,
                key=f"wlo_{col}",
            )
        with wcol2:
            hi = st.number_input(
                f"Upper cap % for '{col}'",
                min_value=0.0, max_value=10.0, value=1.0, step=0.5,
                key=f"whi_{col}",
            )
        winsorize_limits[col] = (lo / 100.0, hi / 100.0)

    if not continuous_cols:
        st.caption("No continuous variables to winsorize.")

    # ── 4. Log Transform Variables ───────────────────────────────────────
    st.markdown("---")
    st.subheader("4️⃣ Log Transform Variables")
    st.markdown(
        "Highly skewed variables can violate model assumptions and give outsized influence to extreme values. "
        "A **log transformation** (ln) compresses the scale, making the distribution more symmetric. "
        "This is common for variables like income, prices, or population that span several orders of magnitude."
    )

    # Candidates: continuous numeric columns with all positive values
    log_candidates = [
        c for c in continuous_cols
        if df[c].min() > 0
    ]

    # Auto-detect highly skewed columns (|skewness| > 2)
    skewed_cols = []
    for col in log_candidates:
        skew = df[col].skew()
        if abs(skew) > 2:
            skewed_cols.append(col)

    if skewed_cols:
        st.caption(f"Columns with high skewness: {', '.join(skewed_cols)}")

    log_selected = st.multiselect(
        "Select columns to log-transform",
        log_candidates,
        default=skewed_cols,
        key="log_cols",
        help="Only columns with all positive values are shown. The transform computes ln(x). "
             "Columns with |skewness| > 2 are pre-selected.",
    )

    if not log_candidates:
        st.caption("No eligible columns (must be continuous and all-positive).")

    # ── 5. Encode Categorical Variables ──────────────────────────────────
    st.markdown("---")
    st.subheader("5️⃣ Encode Categorical Variables")
    st.markdown(
        "Machine learning models require numeric inputs. Categorical variables (text labels or "
        "low-cardinality numbers like tiers) are converted into **dummy columns** — one binary "
        "column per category — so the model can properly account for group differences without "
        "imposing a false numeric ordering."
    )

    cat_candidates = [
        c for c in all_analysis_cols
        if c in df.columns and (
            pd.api.types.is_object_dtype(df[c])
            or pd.api.types.is_categorical_dtype(df[c])
            or (pd.api.types.is_numeric_dtype(df[c]) and df[c].nunique() <= 5 and c not in [treatment, outcome])
        )
    ]
    # Auto-select string/object columns
    auto_dummy = [c for c in cat_candidates if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_categorical_dtype(df[c])]

    dummy_selected = st.multiselect(
        "Select columns to dummy-encode",
        cat_candidates,
        default=auto_dummy,
        key="dummy_cols",
    )

    if not cat_candidates:
        st.caption("No categorical variables detected.")

    # ── Navigation ───────────────────────────────────────────────────────
    st.markdown("---")

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 4
            st.rerun()
    with col_next:
        if st.button("Apply & Continue →", type="primary", disabled=not variation_ok):
            processed, steps_log = apply_processing(
                df, treatment, outcome, confounders,
                winsorize_cols=winsorize_selected,
                winsorize_limits=winsorize_limits,
                log_cols=log_selected,
                dummy_cols=dummy_selected,
            )
            st.session_state.processed_data = processed
            st.session_state.processing_log = steps_log
            st.session_state.step = 6
            st.rerun()

    # ── Save processed data for later ────────────────────────────────────
    st.markdown("---")
    st.subheader("💾 Save Processed Data")
    st.markdown("Save your processed data and settings so you can resume this analysis later.")
    if st.button("Prepare Save File", key="prepare_save"):
        processed, steps_log = apply_processing(
            df, treatment, outcome, confounders,
            winsorize_cols=winsorize_selected,
            winsorize_limits=winsorize_limits,
            log_cols=log_selected,
            dummy_cols=dummy_selected,
        )
        save_bytes = save_session_data(
            processed_data=processed,
            treatment=treatment,
            outcome=outcome,
            confounders=st.session_state.get("confounders", []),
            variable_definitions=st.session_state.get("variable_definitions", {}),
            processing_accepted=steps_log,
        )
        st.session_state["_save_bytes"] = save_bytes

    if "_save_bytes" in st.session_state:
        st.download_button(
            label="⬇️ Download Session File",
            data=st.session_state["_save_bytes"],
            file_name="causal_analysis_session.json",
            mime="application/json",
        )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Final Checks
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 6:
    st.header("Step 6: Final Checks")
    df = st.session_state.processed_data
    treatment = st.session_state.treatment
    outcome = st.session_state.outcome
    confounders = st.session_state.get("confounders", [])

    # Only use confounder columns that exist in the processed data
    # Include original columns, _missing flags, and dummy-encoded columns (prefix match)
    W_cols = [c for c in confounders if c in df.columns]
    for c in confounders:
        if c not in df.columns:
            # Look for dummy-encoded columns (e.g., region_South, region_East)
            dummies = [col for col in df.columns if col.startswith(f"{c}_")]
            W_cols.extend(dummies)
    # Also include _missing indicator columns
    missing_flags = [c for c in df.columns if c.endswith("_missing") and c.replace("_missing", "") in confounders]
    W_cols = list(dict.fromkeys(W_cols + missing_flags))  # deduplicate, preserve order

    is_binary_treatment = set(df[treatment].dropna().unique()).issubset({0, 1, 0.0, 1.0})
    all_checks_pass = True

    # Initialize diagnostics storage
    diagnostics = {
        "is_binary_treatment": is_binary_treatment,
        "predictability": {},
        "overlap": {},
    }

    # ── Check 1: Predictive power of confounders on treatment ────────────
    st.subheader("1️⃣ Treatment Predictability")
    st.markdown(
        "This check uses your confounders to **predict the treatment** and measures how well they succeed. "
        "Why does this matter? In causal inference, we need treatment assignment to have some variation "
        "that confounders *don't* fully explain — that unexplained variation is what lets us isolate the "
        "causal effect. If confounders perfectly predict treatment, there's no independent variation left "
        "to learn from. Conversely, if confounders can't predict treatment at all, it may mean treatment "
        "was randomly assigned (an experiment), and you may not need to adjust for confounders."
    )

    if W_cols:
        from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score

        X_check = df[W_cols].values
        T_check = df[treatment].values

        if is_binary_treatment:
            st.markdown(
                f"Treatment `{treatment}` is **binary**. We fit a classifier using confounders to "
                "predict treatment assignment and check how predictable it is."
            )
            clf = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
            scores = cross_val_score(clf, X_check, T_check, cv=5, scoring="roc_auc")
            auc_mean = scores.mean()

            st.metric("Cross-validated AUC", f"{auc_mean:.3f}")
            diagnostics["predictability"]["metric"] = "AUC"
            diagnostics["predictability"]["value"] = auc_mean

            if auc_mean < 0.55:
                diagnostics["predictability"]["status"] = "low"
                diagnostics["predictability"]["message"] = (
                    f"Low predictability (AUC = {auc_mean:.3f}). "
                    "Confounders barely predict treatment assignment. Treatment "
                    "may have been randomly assigned (an experiment)."
                )
                st.warning(
                    f"⚠️ **Low predictability (AUC = {auc_mean:.3f}).** "
                    "Confounders barely predict treatment assignment. This looks like treatment "
                    "may have been **randomly assigned** (an experiment). If so, you may not need "
                    "to control for confounders at all."
                )
            elif auc_mean > 0.95:
                diagnostics["predictability"]["status"] = "high"
                diagnostics["predictability"]["message"] = (
                    f"Near-perfect predictability (AUC = {auc_mean:.3f}). "
                    "Confounders almost perfectly predict treatment. The model may not "
                    "be able to estimate a causal effect reliably."
                )
                st.error(
                    f"🚨 **Near-perfect predictability (AUC = {auc_mean:.3f}).** "
                    "Confounders almost perfectly predict treatment. This means there is very "
                    "little variation in treatment that isn't explained by confounders — "
                    "the model may not be able to estimate a causal effect reliably."
                )
                # Identify which confounders are most predictive
                clf_full = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
                clf_full.fit(X_check, T_check)
                importances = clf_full.feature_importances_
                top_indices = np.argsort(importances)[::-1]
                top_confounders = [(W_cols[i], importances[i]) for i in top_indices if importances[i] > 0.01][:5]
                if top_confounders:
                    culprits_plain = ", ".join([f"{name} ({imp:.1%})" for name, imp in top_confounders])
                    diagnostics["predictability"]["top_confounders"] = culprits_plain
                    culprits = ", ".join([f"**{name}** ({imp:.1%})" for name, imp in top_confounders])
                    st.warning(
                        f"🔍 **Most predictive confounders:** {culprits}. "
                        "Consider removing the top predictor(s) — they may be proxies for the treatment "
                        "rather than true confounders."
                    )
                all_checks_pass = False
            else:
                diagnostics["predictability"]["status"] = "ok"
                diagnostics["predictability"]["message"] = (
                    f"Confounders moderately predict treatment (AUC = {auc_mean:.3f}). "
                    "Observational variation suitable for causal estimation."
                )
                st.success(
                    f"✅ Confounders moderately predict treatment (AUC = {auc_mean:.3f}). "
                    "This suggests observational variation suitable for causal estimation."
                )
        else:
            st.markdown(
                f"Treatment `{treatment}` is **continuous**. We fit a regressor using confounders to "
                "predict treatment and check R² — how much variation they explain."
            )
            reg = GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
            scores = cross_val_score(reg, X_check, T_check, cv=5, scoring="r2")
            r2_mean = scores.mean()

            st.metric("Cross-validated R²", f"{r2_mean:.3f}")
            diagnostics["predictability"]["metric"] = "R2"
            diagnostics["predictability"]["value"] = r2_mean

            if r2_mean < 0.05:
                diagnostics["predictability"]["status"] = "low"
                diagnostics["predictability"]["message"] = (
                    f"Low predictability (R2 = {r2_mean:.3f}). "
                    "Confounders explain almost none of the treatment variation. "
                    "Treatment may have been randomly assigned (an experiment)."
                )
                st.warning(
                    f"⚠️ **Low predictability (R² = {r2_mean:.3f}).** "
                    "Confounders explain almost none of the treatment variation. This looks like "
                    "treatment may have been **randomly assigned** (an experiment)."
                )
            elif r2_mean > 0.95:
                diagnostics["predictability"]["status"] = "high"
                diagnostics["predictability"]["message"] = (
                    f"Near-perfect predictability (R2 = {r2_mean:.3f}). "
                    "Confounders almost perfectly predict treatment. There may not be enough "
                    "residual variation to estimate a causal effect."
                )
                st.error(
                    f"🚨 **Near-perfect predictability (R² = {r2_mean:.3f}).** "
                    "Confounders almost perfectly predict treatment. There may not be enough "
                    "residual variation to estimate a causal effect."
                )
                # Identify which confounders are most predictive
                reg_full = GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
                reg_full.fit(X_check, T_check)
                importances = reg_full.feature_importances_
                top_indices = np.argsort(importances)[::-1]
                top_confounders = [(W_cols[i], importances[i]) for i in top_indices if importances[i] > 0.01][:5]
                if top_confounders:
                    culprits_plain = ", ".join([f"{name} ({imp:.1%})" for name, imp in top_confounders])
                    diagnostics["predictability"]["top_confounders"] = culprits_plain
                    culprits = ", ".join([f"**{name}** ({imp:.1%})" for name, imp in top_confounders])
                    st.warning(
                        f"🔍 **Most predictive confounders:** {culprits}. "
                        "Consider removing the top predictor(s) — they may be proxies for the treatment "
                        "rather than true confounders."
                    )
                all_checks_pass = False
            else:
                diagnostics["predictability"]["status"] = "ok"
                diagnostics["predictability"]["message"] = (
                    f"Confounders moderately predict treatment (R2 = {r2_mean:.3f}). "
                    "Observational variation suitable for causal estimation."
                )
                st.success(
                    f"✅ Confounders moderately predict treatment (R² = {r2_mean:.3f}). "
                    "This suggests observational variation suitable for causal estimation."
                )
    else:
        st.info("No confounders selected — skipping treatment predictability check.")

    # ── Check 2: Propensity score overlap (binary treatment only) ────────
    if is_binary_treatment and W_cols:
        st.markdown("---")
        st.subheader("2️⃣ Overlap Check (Propensity Scores)")
        st.markdown(
            "For causal inference to work, we need **overlap**: for every combination of "
            "confounder values, there should be both treated and untreated observations. "
            "We estimate propensity scores P(T=1|W) and check their distribution."
        )

        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import cross_val_predict
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ps_clf = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
        propensity = cross_val_predict(ps_clf, df[W_cols].values, df[treatment].values, cv=5, method="predict_proba")[:, 1]

        # Trimming rule (Crump et al., 2009): α = 0.1 is a common default
        alpha = 0.1
        in_overlap = (propensity >= alpha) & (propensity <= 1 - alpha)
        n_trimmed = (~in_overlap).sum()
        pct_trimmed = n_trimmed / len(df) * 100

        # Plot propensity score distribution
        fig, ax = plt.subplots(figsize=(8, 4))
        treated_mask = df[treatment] == 1
        ax.hist(propensity[treated_mask], bins=40, alpha=0.6, label="Treated", color="#1f77b4", density=True)
        ax.hist(propensity[~treated_mask], bins=40, alpha=0.6, label="Untreated", color="#ff7f0e", density=True)
        ax.axvline(x=alpha, color="red", linestyle="--", alpha=0.7, label=f"Trim boundary ({alpha})")
        ax.axvline(x=1 - alpha, color="red", linestyle="--", alpha=0.7)
        ax.set_xlabel("Propensity Score P(T=1|W)", fontsize=11)
        ax.set_ylabel("Density", fontsize=11)
        ax.set_title("Propensity Score Distribution", fontsize=13)
        ax.legend(fontsize=10)
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)

        # Summary stats
        col1, col2, col3 = st.columns(3)
        col1.metric("Mean (Treated)", f"{propensity[treated_mask].mean():.3f}")
        col2.metric("Mean (Untreated)", f"{propensity[~treated_mask].mean():.3f}")
        col3.metric("Observations trimmed", f"{n_trimmed:,} ({pct_trimmed:.1f}%)")

        # Store overlap diagnostics
        treated_mask = df[treatment] == 1
        diagnostics["overlap"]["mean_treated"] = float(propensity[treated_mask].mean())
        diagnostics["overlap"]["mean_untreated"] = float(propensity[~treated_mask].mean())
        diagnostics["overlap"]["pct_trimmed"] = pct_trimmed
        diagnostics["overlap"]["n_trimmed"] = int(n_trimmed)

        if pct_trimmed > 20:
            diagnostics["overlap"]["status"] = "poor"
            diagnostics["overlap"]["message"] = (
                f"{pct_trimmed:.1f}% of observations would be trimmed for lack of overlap. "
                "Many observations have propensity scores near 0 or 1, meaning treated and "
                "untreated groups are quite different."
            )
            st.warning(
                f"⚠️ **{pct_trimmed:.1f}% of observations** would be trimmed for lack of overlap. "
                "Many observations have propensity scores near 0 or 1, meaning treated and untreated "
                "groups are quite different. Consider adding more confounders or reviewing your data."
            )
        elif pct_trimmed > 5:
            diagnostics["overlap"]["status"] = "moderate"
            diagnostics["overlap"]["message"] = (
                f"{pct_trimmed:.1f}% of observations have limited overlap. "
                "The analysis will proceed, but results may be less precise for extreme subgroups."
            )
            st.info(
                f"ℹ️ {pct_trimmed:.1f}% of observations have limited overlap. "
                "The analysis will proceed, but results may be less precise for extreme subgroups."
            )
        else:
            diagnostics["overlap"]["status"] = "good"
            diagnostics["overlap"]["message"] = (
                f"Good overlap -- only {pct_trimmed:.1f}% of observations fall outside "
                "the overlap region. Treated and untreated groups are comparable."
            )
            st.success(
                f"✅ Good overlap — only {pct_trimmed:.1f}% of observations fall outside "
                "the overlap region. Treated and untreated groups are comparable."
            )

        # Check for complete separation
        if propensity.min() > 0.99 or propensity.max() < 0.01:
            diagnostics["overlap"]["status"] = "separation"
            diagnostics["overlap"]["message"] = (
                "Complete separation detected. All propensity scores are near 0 or 1. "
                "There is no common support between treated and untreated groups."
            )
            st.error(
                "🚨 **Complete separation detected.** All propensity scores are near 0 or 1. "
                "There is no common support between treated and untreated groups."
            )
            all_checks_pass = False

    elif is_binary_treatment and not W_cols:
        st.markdown("---")
        st.subheader("2️⃣ Overlap Check")
        st.info("No confounders selected — skipping overlap check.")

    # Save diagnostics to session state for PDF
    st.session_state.diagnostics = diagnostics

    # ── Navigation ───────────────────────────────────────────────────────
    st.markdown("---")

    if not all_checks_pass:
        st.error("⚠️ Some checks failed. You can still proceed, but results may be unreliable.")

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 5
            st.rerun()
    with col_next:
        if st.button("Continue →", type="primary", key="step6_next"):
            st.session_state.step = 7
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: Choose Estimation Method
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 7:
    st.header("Step 7: Choose Estimation Method")

    treatment = st.session_state.treatment
    df = st.session_state.processed_data
    is_binary = set(df[treatment].dropna().unique()).issubset({0, 1, 0.0, 1.0})

    if is_binary:
        st.markdown(
            "Your treatment is **binary** (yes/no). We recommend the **Linear Doubly Robust Learner**, "
            "which models both the outcome and the probability of treatment. If either model is correct, "
            "the causal estimate is consistent."
        )
    else:
        st.markdown(
            "Your treatment is **continuous**. We recommend **Linear Double Machine Learning**, "
            "which uses ML to account for confounders, then isolates the true treatment effect."
        )

    recommended = get_estimator_recommendation(df, is_binary)

    # Show recommended first, then others; OLS last
    sorted_keys = sorted(
        ESTIMATORS.keys(),
        key=lambda k: (0 if k == recommended else (2 if k == "OLS" else 1)),
    )

    for key in sorted_keys:
        info = ESTIMATORS[key]
        is_rec = key == recommended
        with st.container(border=True):
            badge = " ⭐ Recommended" if is_rec else ""
            st.subheader(f"{info['name']}{badge}")
            st.markdown(f"**{info['short']}**")
            st.markdown(info["description"])
            st.caption(f"🎯 When to use: {info['when_to_use']}")
            st.caption(f"Complexity: {info['complexity']}")

    estimator_choice = st.radio(
        "Select your method:",
        sorted_keys,
        index=sorted_keys.index(recommended),
        format_func=lambda k: f"{ESTIMATORS[k]['name']} {'⭐' if k == recommended else ''}",
        key="estimator_radio",
    )

    st.session_state.estimator = estimator_choice

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back"):
            st.session_state.step = 6
            st.rerun()
    with col_next:
        if st.button("Run Analysis →", type="primary", key="step7_next"):
            st.session_state.step = 8
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: Run Analysis
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 8:
    st.header("Step 8: Running Your Analysis")

    est_info = ESTIMATORS[st.session_state.estimator]
    st.info(f"**Method:** {est_info['name']}\n\n{est_info['short']}")

    with st.status("Fitting causal model...", expanded=True) as status:
        st.write("🔄 Preparing data...")
        df = st.session_state.processed_data

        # Resolve confounder names to actual columns in processed data
        # (originals may have been dummy-encoded or gained _missing flags)
        raw_confounders = st.session_state.confounders
        resolved_confounders = [c for c in raw_confounders if c in df.columns]
        for c in raw_confounders:
            if c not in df.columns:
                dummies = [col for col in df.columns if col.startswith(f"{c}_")]
                resolved_confounders.extend(dummies)
        missing_flags = [c for c in df.columns if c.endswith("_missing") and c.replace("_missing", "") in raw_confounders]
        resolved_confounders = list(dict.fromkeys(resolved_confounders + missing_flags))

        st.write(f"🔄 Fitting **{est_info['name']}** on {len(df):,} observations...")
        try:
            results = fit_model(
                df=df,
                outcome_col=st.session_state.outcome,
                treatment_col=st.session_state.treatment,
                confounder_cols=resolved_confounders,
                estimator_name=st.session_state.estimator,
            )
            st.session_state.results = results
            st.write("✅ Model fitted successfully!")
            status.update(label="Analysis complete!", state="complete")
        except Exception as e:
            st.error(f"❌ Analysis failed: {e}")
            status.update(label="Analysis failed", state="error")
            st.stop()

    st.success("Your analysis is ready! Click below to see the results.")

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back (change settings)"):
            st.session_state.step = 7
            st.rerun()
    with col_next:
        if st.button("See Results →", type="primary", key="step8_next"):
            st.session_state.step = 9
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: Results & Actions
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.step == 9:
    st.header("Step 9: Your Results")
    results = st.session_state.results
    df = st.session_state.processed_data

    if results is None:
        st.error("No results found. Please go back and run the analysis.")
        st.stop()

    # ── Key Findings ─────────────────────────────────────────────────────────
    summary = get_effect_summary(results)

    st.subheader("📋 Key Findings")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Average Treatment Effect", f"{summary['average_effect']:.4f}")
    col2.metric("Standard Error", f"{summary['standard_error']:.4f}")
    col3.metric("95% Confidence Interval", f"[{summary['avg_lower']:.4f}, {summary['avg_upper']:.4f}]")
    p_val = summary["p_value"]
    col4.metric("p-value", f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001")

    # Plain language interpretation
    avg = summary["average_effect"]
    treatment = results["treatment_col"]
    outcome = results["outcome_col"]

    if avg < 0:
        direction = "decreases"
    elif avg > 0:
        direction = "increases"
    else:
        direction = "has no average effect on"

    if p_val < 0.05:
        significance_text = (
            f"This result is **statistically significant** (p = {p_val:.4f}), meaning it is unlikely "
            f"to be due to chance alone."
        )
    else:
        significance_text = (
            f"This result is **not statistically significant** (p = {p_val:.4f}), meaning we cannot "
            f"confidently rule out that the observed effect is due to chance."
        )

    ci_text = (
        f"We are 95% confident the true effect lies between "
        f"**{summary['avg_lower']:.4f}** and **{summary['avg_upper']:.4f}**."
    )

    st.markdown(
        f"""
**In plain language:** On average, increasing **{treatment}** {direction} **{outcome}**
by **{abs(avg):.4f}** units. {ci_text}

{significance_text}
        """
    )

    # ── Treatment Effect Visualization ──────────────────────────────────────
    st.markdown("---")
    st.subheader("📈 Treatment Effect Visualization")

    fig_effect = create_effect_plot(results)
    st.pyplot(fig_effect, use_container_width=False)

    # Per-chart plain language interpretations
    te_arr = results["te_pred"].flatten()
    Y_arr = results["Y"].flatten()
    T_arr = results["T"].flatten()
    avg_lower = float(np.mean(results["te_lower"].flatten()))
    avg_upper = float(np.mean(results["te_upper"].flatten()))
    raw_diff = compute_unconditional_difference(T_arr, Y_arr)
    is_binary = set(np.unique(T_arr)).issubset({0, 1, 0.0, 1.0})
    ci_crosses_zero = avg_lower <= 0 <= avg_upper

    if is_binary:
        st.markdown(
            f"**Unconditional difference** (orange line): The raw difference in average **{outcome}** "
            f"between treated and untreated groups is **{raw_diff:+.4f}**, without controlling for any confounders. "
            f"This difference may be driven by confounders rather than the treatment itself."
        )
    else:
        st.markdown(
            f"**Unconditional association** (orange line): The raw association between **{treatment}** and "
            f"**{outcome}** is **{raw_diff:+.4f}** per unit increase in **{treatment}**, without controlling "
            f"for any confounders. This association may be driven by confounders rather than the treatment itself."
        )

    if ci_crosses_zero:
        st.markdown(
            f"**Causal effect estimate** (blue dot with whiskers): After controlling for confounders, "
            f"the estimated causal effect is **{avg:.4f}**, but the confidence interval crosses zero "
            f"([{avg_lower:.4f}, {avg_upper:.4f}]), meaning we **cannot rule out** that the true effect is zero."
        )
    else:
        st.markdown(
            f"**Causal effect estimate** (blue dot with whiskers): After controlling for confounders, "
            f"the estimated causal effect is **{avg:.4f}** with a confidence interval of "
            f"[{avg_lower:.4f}, {avg_upper:.4f}]. Since the interval **does not cross zero**, "
            f"the effect is statistically significant."
        )

    # Compare unconditional vs causal effect
    st.markdown("---")
    if abs(raw_diff) > 0.001 and abs(avg) > 0.001:
        if abs(avg) < abs(raw_diff):
            comparison = (
                f"The unconditional difference (**{raw_diff:+.4f}**) is larger in magnitude than the "
                f"causal estimate (**{avg:+.4f}**), suggesting that confounders were inflating the "
                f"apparent effect of **{treatment}** on **{outcome}**."
            )
        elif abs(avg) > abs(raw_diff):
            comparison = (
                f"The causal estimate (**{avg:+.4f}**) is larger in magnitude than the unconditional "
                f"difference (**{raw_diff:+.4f}**), suggesting that confounders were masking some of "
                f"the true effect of **{treatment}** on **{outcome}**."
            )
        else:
            comparison = (
                f"The unconditional difference (**{raw_diff:+.4f}**) and the causal estimate "
                f"(**{avg:+.4f}**) are similar, suggesting confounders had little impact on the "
                f"observed relationship between **{treatment}** and **{outcome}**."
            )
    else:
        comparison = (
            f"The unconditional difference is **{raw_diff:+.4f}** and the causal estimate is "
            f"**{avg:+.4f}**."
        )
    st.markdown(f"📊 **Unconditional vs. Causal:** {comparison}")

    # ── Analysis Inputs (what went into EconML) ──────────────────────────────
    st.markdown("---")
    st.subheader("🔧 Analysis Inputs")
    st.markdown("Here's exactly what was fed into the causal model:")

    est_key = results["estimator_name"]
    est_info = ESTIMATORS[est_key]

    # -- Variable roles table --
    roles_data = {
        "Role": [],
        "EconML Parameter": [],
        "Column(s)": [],
    }

    roles_data["Role"].append("Outcome")
    roles_data["EconML Parameter"].append("Y")
    roles_data["Column(s)"].append(results["outcome_col"])

    roles_data["Role"].append("Treatment")
    roles_data["EconML Parameter"].append("T")
    roles_data["Column(s)"].append(results["treatment_col"])

    if results["W_cols"]:
        roles_data["Role"].append("Confounders")
        roles_data["EconML Parameter"].append("W")
        roles_data["Column(s)"].append(", ".join(results["W_cols"]))
    else:
        roles_data["Role"].append("Confounders")
        roles_data["EconML Parameter"].append("W")
        roles_data["Column(s)"].append("— (none selected)")

    roles_df = pd.DataFrame(roles_data)
    st.dataframe(roles_df, use_container_width=True, hide_index=True)

    # -- Estimator & Data details in tables side by side --
    icol1, icol2 = st.columns(2)
    with icol1:
        st.markdown("**Estimator**")
        est_rows = [
            {"Setting": "Method", "Value": f"{est_info['name']} ({est_key})"},
            {"Setting": "Complexity", "Value": est_info["complexity"]},
        ]
        if est_key == "OLS":
            est_rows.append({"Setting": "Inference", "Value": "statsmodels (analytical SE)"})
        elif est_key == "LinearDML":
            est_rows.append({"Setting": "Nuisance Models", "Value": "GBR (100 trees, depth 3)"})
            est_rows.append({"Setting": "Inference", "Value": "statsmodels"})
        elif est_key == "LinearDRLearner":
            est_rows.append({"Setting": "Outcome Model", "Value": "GBR (100 trees, depth 3)"})
            est_rows.append({"Setting": "Propensity Model", "Value": "GBC (100 trees, depth 3)"})
            est_rows.append({"Setting": "Inference", "Value": "statsmodels"})
        st.dataframe(pd.DataFrame(est_rows), use_container_width=True, hide_index=True)

    with icol2:
        st.markdown("**Data**")
        w_dim = results["W"].shape[1] if results["W"] is not None else 0
        proc_steps = st.session_state.get("processing_log", [])
        data_rows = [
            {"Metric": "Observations", "Value": f"{len(df):,}"},
            {"Metric": "Columns After Processing", "Value": str(df.shape[1])},
            {"Metric": "Confounder Dimensions (W)", "Value": str(w_dim)},
            {"Metric": "Processing Steps", "Value": str(len(proc_steps)) if proc_steps else "None"},
        ]
        st.dataframe(pd.DataFrame(data_rows), use_container_width=True, hide_index=True)
        if proc_steps:
            with st.expander("View processing steps"):
                for step in proc_steps:
                    st.markdown(f"- {step}")

    # Show the equivalent Python code
    with st.expander("🐍 Equivalent Python Code"):
        w_arg = f"W=df[{results['W_cols']}].values" if results["W_cols"] else "W=None"
        if est_key == "OLS":
            w_code = f"W = df[{results['W_cols']}].values\nX = np.column_stack([T, W])" if results["W_cols"] else "X = T.reshape(-1, 1)"
            code_snippet = f"""\
import numpy as np
import statsmodels.api as sm

Y = df["{results['outcome_col']}"].values
T = df["{results['treatment_col']}"].values
{w_code}
X = sm.add_constant(X)

model = sm.OLS(Y, X).fit()

# Treatment effect = coefficient on T (index 1)
ate = model.params[1]
ci = model.conf_int(alpha=0.05)[1]  # 95% CI
print(model.summary())"""
        elif est_key == "LinearDML":
            code_snippet = f"""\
from econml.dml import LinearDML
from sklearn.ensemble import GradientBoostingRegressor

Y = df["{results['outcome_col']}"].values
T = df["{results['treatment_col']}"].values
{w_arg}

est = LinearDML(
    model_y=GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42),
    model_t=GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42),
    random_state=42,
)
est.fit(Y, T, X=None, W=W, inference="statsmodels")

# Average treatment effect
ate = est.effect()
ate_lower, ate_upper = est.effect_interval(alpha=0.05)"""
        elif est_key == "LinearDRLearner":
            code_snippet = f"""\
from econml.dr import LinearDRLearner
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier

Y = df["{results['outcome_col']}"].values
T = df["{results['treatment_col']}"].values
{w_arg}

est = LinearDRLearner(
    model_regression=GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42),
    model_propensity=GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42),
    random_state=42,
)
est.fit(Y, T, X=None, W=W, inference="statsmodels")

# Average treatment effect
ate = est.effect()
ate_lower, ate_upper = est.effect_interval(alpha=0.05)"""
        st.code(code_snippet, language="python")

    # ── Download Results ─────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📥 Download Results")
    st.markdown(
        "Download the analysis results including the estimated treatment effect "
        "and confidence intervals."
    )

    pdf_bytes = generate_results_pdf(
        results=results,
        summary=summary,
        fig=fig_effect,
        estimator_info=est_info,
        processing_log=st.session_state.get("processing_log", []),
        causal_question=st.session_state.get("causal_question", ""),
        domain_knowledge=st.session_state.get("_llm_domain_knowledge", ""),
        confounders=st.session_state.get("confounders", []),
        diagnostics=st.session_state.get("diagnostics", {}),
    )
    pdf_name = st.text_input("File name", value="causal_analysis_summary", key="pdf_filename")
    pdf_name = pdf_name.strip().removesuffix(".pdf") or "causal_analysis_summary"
    st.download_button(
        "⬇ Download Results Summary (PDF)",
        pdf_bytes,
        file_name=f"{pdf_name}.pdf",
        mime="application/pdf",
        type="primary",
        key=f"pdf_dl_{pdf_name}",
    )

    # ── Interpretation Guide ─────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("📖 How to Interpret These Results"):
        st.markdown(f"""
### Understanding Your Treatment Effects

**What is a treatment effect?**
It measures how much the **{outcome}** changes when you change the **{treatment}** for a given individual, holding everything else constant.

**Reading the numbers:**
- **Negative effect** (e.g., -0.5): Increasing {treatment} *decreases* {outcome} by 0.5 units
- **Positive effect** (e.g., +0.3): Increasing {treatment} *increases* {outcome} by 0.3 units
- **Zero effect**: {treatment} has no impact on {outcome} for this individual

**Confidence intervals:**
- Narrow interval → we're confident in the estimate
- Wide interval → more uncertainty; collect more data or add more confounders
- Interval crosses zero → the effect may not be real for this individual

**Using the results:**
Apply the estimated treatment effect to inform your decision-making. A statistically significant negative effect suggests the treatment reduces the outcome.

**Limitations:**
- Results are only as good as the confounders you've included. Unmeasured confounders can bias estimates.
- The model assumes no reverse causality ({outcome} doesn't cause {treatment}).
        """)

    # Restart option
    st.markdown("---")
    if st.button("🔄 Start a New Analysis"):
        for key, val in DEFAULTS.items():
            st.session_state[key] = val
        st.rerun()
