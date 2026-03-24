# Autoresearch Program — Improve causal.instructions.md

You are an autonomous research agent improving a copilot skill file for causal
inference. Your goal is to **maximize the eval score** by making targeted edits
to the instructions file, one improvement per round.

---

## The Setup

| Role | File | Editable? |
|------|------|-----------|
| **Target** (the thing you improve) | `.github/instructions/causal.instructions.md` | ✅ YES |
| **Eval** (the scoring function) | `autoresearch/eval.py` | ❌ NO |
| **Program** (this file) | `autoresearch/program.md` | ❌ NO |
| **Source code** (ground truth) | `app/main.py`, `app/estimation.py`, `app/data_utils.py` | ❌ NO |

**You may ONLY edit `.github/instructions/causal.instructions.md`.**

---

## The Loop

Repeat the following cycle. Each cycle is one "experiment."

### Step 1: Score the current state

```bash
python autoresearch/eval.py
```

Read the output carefully. Note the **total score** and identify the **lowest-scoring checks** — these are your improvement opportunities.

### Step 2: Form a hypothesis

Pick ONE low-scoring check from the eval output. Write a brief hypothesis:

> "Adding a section about [X] should improve check [Y.Z] from 0 to N."

**Rules for picking what to improve:**
- Target checks that score **0** first — going from 0→full is the biggest gain.
- Target checks worth **3 points** before checks worth **1 point**.
- Only change ONE thing per round. Small, focused edits are safer.
- Do NOT remove content that earns points on other checks.

### Step 3: Edit the target file

Make a **precise, surgical edit** to `.github/instructions/causal.instructions.md`.

- Add content, improve wording, or restructure sections.
- Keep existing content that scores well. Do not regress.
- Reference the actual source code when adding technical details. Read
  `app/estimation.py`, `app/data_utils.py`, or `app/main.py` to get exact
  function signatures, variable names, and code patterns.
- Maintain the file's overall style: markdown, clear sections, code blocks.

### Step 4: Re-score

```bash
python autoresearch/eval.py
```

Compare the new score to the previous score.

### Step 5: Keep or revert

**If the score improved (new > old):**
```bash
git add .github/instructions/causal.instructions.md
git commit -m "autoresearch: [brief description of change] (score: OLD → NEW)"
```
This commit becomes the new baseline.

**If the score stayed the same or decreased (new ≤ old):**
```bash
git checkout -- .github/instructions/causal.instructions.md
```
Discard the change and try a different hypothesis.

### Step 6: Log and continue

After each round, briefly log:
- Round number
- Hypothesis
- Score change (or "reverted")
- Running total

Then start the next round from Step 1.

---

## Strategy Guide

### What the eval checks (read eval.py for full details)

The eval scores 5 categories totaling 127 points:

1. **Structure (21 pts):** Clear title, organized sections, code blocks, tables,
   appropriate length, dividers, guardrails section, error handling guidance.

2. **Workflow completeness (34 pts):** Covers data loading, data dictionary,
   treatment/outcome selection, binary/continuous distinction, confounder selection,
   processing pipeline, diagnostics, results, PDF generation, iteration loop,
   **LLM-assisted suggestions** (treatment/outcome/confounders via OpenAI),
   **session save/load**, variable definition editing, domain knowledge input.

3. **Codebase accuracy (33 pts):** All 3 estimators, correct mapping, EconML fit API,
   GradientBoosting, effect extraction, unconditional difference, variable roles,
   float64 conversion, processing order, fpdf2, missing indicator, **PDF page count
   accuracy** (actual code generates 2-page, not 1-page), random_state=42,
   **OLS via statsmodels** (sm.OLS, sm.add_constant), **ate_inference()** for proper
   p-values/SE, Crump trimming thresholds.

4. **Code examples (15 pts):** LinearDML, LinearDRLearner, OLS, processing,
   result extraction, diagnostics.

5. **Agent usefulness (24 pts):** Non-technical audience, causal vs predictive,
   unmeasured confounders, bias tradeoff, data copies, interpretation template,
   p-values, user questions, **ATE vs heterogeneous effects**, **bias direction
   (inflating vs masking)**, **doubly robust property**, **statistical vs practical
   significance**, reverse causality warning.

### Tips

- **Read the source code** before adding technical details. The eval checks that
  your descriptions match the actual implementation.
- **Don't hallucinate code patterns.** If you're not sure about an API, read the
  source file first.
- **Preserve high-scoring content.** Never delete something that earns points
  unless you're replacing it with something strictly better.
- **Watch the word count.** The eval penalizes files shorter than 1500 words or
  longer than 8000 words.
- **One change per round.** If you try to fix everything at once, you can't tell
  what helped and what hurt.

---

## Stopping Criteria

Stop when:
- The total score reaches **125/127 or higher**, OR
- You have completed **20 rounds**, OR
- The last **3 consecutive rounds** were all reverted (no improvement found).

When you stop, print a final summary:
```
AUTORESEARCH COMPLETE
Rounds: N
Final score: X/100 (Y%)
Improvements kept: K
Improvements reverted: R
```

---

## Important Constraints

1. **NEVER edit eval.py or program.md.** If you do, the experiment is invalid.
2. **NEVER edit the source code** (main.py, estimation.py, data_utils.py).
3. **Always run the eval before AND after each edit.** No skipping.
4. **Always use git to commit or revert.** This creates a clean experiment log.
5. **The instructions file is for AI agents, not humans.** Write for an AI coding
   assistant that will follow these instructions to perform causal analysis for a
   user. Be specific, include code, and state explicit rules.
