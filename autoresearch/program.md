# Autoresearch Program — Iteratively Improve a Skill File

You are an autonomous research agent improving a skill / instruction file.
Your goal is to **maximize the eval score** by making targeted edits to the
target file, one improvement per round.

---

## The Setup

| Role | File | Editable? |
|------|------|-----------|
| **Target** (the file you improve) | Defined in `autoresearch/config.py → TARGET_FILE` | ✅ YES |
| **Config** (scoring criteria) | `autoresearch/config.py` | ❌ NO |
| **Eval engine** (scoring logic) | `autoresearch/eval.py` | ❌ NO |
| **Program** (this file) | `autoresearch/program.md` | ❌ NO |
| **Source code** (ground truth) | Listed in `autoresearch/config.py → SOURCE_FILES` | ❌ NO |

**You may ONLY edit the target file specified in config.py.**

Before starting, run this to see the target file path and current score:
```bash
python autoresearch/eval.py
```

---

## The Loop

Repeat the following cycle. Each cycle is one "experiment."

### Step 1: Score the current state

```bash
python autoresearch/eval.py
```

Read the output carefully. Note the **total score** and identify the **lowest-scoring checks** — these are your improvement opportunities.

### Step 2: Read the config

Open `autoresearch/config.py` to understand the full scoring rubric. Each check
has an `id`, `name`, `pts` (max points), and `type` (matching rule). This tells
you exactly what the eval is looking for.

### Step 3: Form a hypothesis

Pick ONE low-scoring check from the eval output. Write a brief hypothesis:

**Rules for picking what to improve:**
- Target checks that score **0** first — going from 0→full is the biggest gain.
- Target checks worth **3 points** before checks worth **1 point**.
- Only change ONE thing per round. Small, focused edits are safer.
- Do NOT remove content that earns points on other checks.

### Step 4: Edit the target file

Make a **precise, surgical edit** to the target file (see config.py for its path).

- Add content, improve wording, or restructure sections.
- Keep existing content that scores well. Do not regress.
- Reference the actual source code when adding technical details. Read the
  source files listed in config.py to get exact function signatures, variable
  names, and code patterns.
- Maintain the file's overall style: markdown, clear sections, code blocks.

### Step 5: Re-score

```bash
python autoresearch/eval.py
```

Compare the new score to the previous score.

### Step 6: Keep or revert

**If the score improved (new > old):**
```bash
git add -A
git commit -m "autoresearch: [brief description] (score: OLD → NEW)"
```
This commit becomes the new baseline.

**If the score stayed the same or decreased (new ≤ old):**
```bash
git checkout -- .
```
Discard the change and try a different hypothesis.

### Step 7: Log and continue

After each round, briefly log:
- Round number
- Hypothesis
- Score change (or "reverted")
- Running total

Then start the next round from Step 1.

---

## Strategy Guide

### Understanding the eval

Run `python autoresearch/eval.py` to see all checks and their scores. The
checks are defined in `autoresearch/config.py` — read it to understand exactly
what terms, patterns, or structures the eval looks for.

Check types:
- **has_all** — every term must appear in the target file
- **has_any** — at least one term must appear
- **count_of** — score proportional to how many terms match
- **tiered** — first matching tier (top-down) determines score
- **regex** — a regex pattern must match somewhere in the file
- **ordered** — terms must appear in sequential order
- **word_range** — file word count must be in the specified range
- **headers** / **code_blocks** — minimum count of headings or code blocks

### Tips

- **Read the source code** before adding technical details. The eval may check
  that your descriptions match the actual implementation.
- **Don't hallucinate.** If you're not sure about an API or pattern, read the
  source file first.
- **Preserve high-scoring content.** Never delete something that earns points
  unless you're replacing it with something strictly better.
- **Watch the word count.** The config may penalize files that are too short or
  too long. Check the `word_range` check if one exists.
- **One change per round.** If you try to fix everything at once, you can't tell
  what helped and what hurt.
- **Read the check type.** A `has_all` check requires EVERY term — missing one
  means zero points. A `has_any` check just needs one term.
- **Tiered checks:** These evaluate top-down — the first matching tier wins.
  Aim for the highest tier.

---

## Stopping Criteria

Stop when:
- The total score reaches **≥98%**, OR
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

1. **NEVER edit eval.py, config.py, or program.md.** If you do, the experiment is invalid.
2. **NEVER edit source code files** listed in config.py SOURCE_FILES.
3. **Always run the eval before AND after each edit.** No skipping.
4. **Always use git to commit or revert.** This creates a clean experiment log.
5. **The target file is for AI agents, not humans.** Write for an AI coding
   assistant that will follow the instructions. Be specific, include code, and
   state explicit rules.
