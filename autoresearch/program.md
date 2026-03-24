# Autoresearch — Autonomous Skill File Improvement

You are an autonomous research agent. Your job is to **iteratively improve a
skill file** by making one change at a time, scoring the result, and keeping
improvements.

Read this file completely before starting.

---

## Phase 1: Setup

If `autoresearch/config.py` does not exist, run the interactive setup:

```bash
python autoresearch/setup.py
```

This asks the user for their skill file, goal, and source files, then
generates the scoring config and establishes a baseline.

If `autoresearch/config.py` already exists, skip to Phase 2. Run the eval
to confirm the baseline:

```bash
python autoresearch/eval.py
```

Read `autoresearch/config.py` to understand:
- `TARGET_FILE` — the file you will edit
- `SOURCE_FILES` — read-only source code for reference
- `GOAL` — what the user wants to improve
- `CHECKS` — every scoring criterion (id, name, points, type, terms)

**You may ONLY edit the file specified in TARGET_FILE. Everything else is
read-only.**

---

## Phase 2: Autonomous Loop

Repeat this cycle. Each cycle is one iteration.

### 2.1 Score

```bash
python autoresearch/eval.py
```

Note the total score and identify **the lowest-scoring checks**.

### 2.2 Hypothesize

Pick ONE failing check. Write a one-line hypothesis:

> "Adding [X] should improve check [ID] from 0 to N points."

**Prioritize:**
- Checks scoring **0** (biggest gain potential)
- Higher-point checks before lower-point checks
- Only ONE change per iteration

### 2.3 Edit

Make a **precise, surgical edit** to the target file.

- Read source files (listed in config.py) for accurate technical details.
- Don't hallucinate — verify against source code before adding.
- Preserve existing content that scores well.
- Maintain the file's style and formatting.

### 2.4 Verify

```bash
python autoresearch/eval.py --log "brief description of change"
```

This scores the file AND logs the result to `autoresearch/results.tsv`.

### 2.5 Keep or Revert

**If score improved:**
```bash
git add -A
git commit -m "autoresearch: [description] (score: OLD → NEW)"
```

**If score stayed the same or decreased:**
```bash
git checkout -- .
```
The result was already logged as a revert — try a different approach.

### 2.6 Continue

Start the next iteration from step 2.1.

---

## Phase 3: Results

Stop the loop when ANY of these are true:
- Score reaches **≥95%**
- You've completed **20 iterations** (or the limit set by the user)
- Last **3 consecutive iterations** were all reverted

Then generate the review document:

```bash
python autoresearch/review.py --save
```

This creates `autoresearch/review.html` and opens it in your browser. It shows:
- **Score banner** — baseline → final with goal
- **Changes Made** — each kept change with its score impact
- **Side-by-side diff** — GitHub-style split view with red/green highlighting

Also print the results summary and final eval:

```bash
python autoresearch/eval.py --results
python autoresearch/eval.py
```

End with a brief summary:
```
AUTORESEARCH COMPLETE
Iterations: N
Baseline:   X/Y (Z%)
Final:      X/Y (Z%)
Kept:       K improvements
Reverted:   R experiments
```

---

## Rules

1. **NEVER edit eval.py, setup.py, config.py, or program.md.**
2. **NEVER edit source files** listed in config.py.
3. **Always run eval before AND after each edit.** No skipping.
4. **Always use git** to commit or revert. Git is memory.
5. **One change per iteration.** Atomic edits — if it fails, you know why.
6. **Read before write.** Understand the source code before adding details.
7. **When stuck, think harder.** Re-read source, try a different approach,
   combine near-misses from previous attempts.
8. **Log everything.** Use `--log` flag so results.tsv tracks all attempts.

---

## Check Type Reference

| Type | What it checks | Key params |
|------|---------------|------------|
| `has_all` | ALL terms present (case-insensitive) | `terms` |
| `has_any` | ANY term present | `terms` |
| `count_of` | Score ∝ matched/total | `terms` |
| `regex` | Regex pattern matches | `pattern` |
| `word_range` | Word count in [min, max] | `min`, `max` |
| `headers` | ≥N headings at level | `min`, `level` |
| `code_blocks` | ≥N code blocks | `min` |
| `ordered` | Terms in sequential order | `terms` |
| `tiered` | First matching tier wins | `tiers` |
