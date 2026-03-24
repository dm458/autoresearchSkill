# autoresearchSkill

**Autonomously improve any skill / instruction file.**

Based on [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) pattern
and inspired by [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch).
Set a goal → the agent runs the loop → you review the results.

## The 3-Step Flow

```
 YOU                          AGENT                         YOU
  │                             │                             │
  │  1. Point to skill file     │                             │
  │  2. Define your goal        │                             │
  │         │                   │                             │
  │         └──────────────────▶│                             │
  │                             │  Setup: scan source code,   │
  │                             │  generate scoring config,   │
  │                             │  establish baseline          │
  │                             │                             │
  │                             │  Loop (autonomous):         │
  │                             │   ┌─ score                  │
  │                             │   ├─ hypothesize            │
  │                             │   ├─ edit skill file        │
  │                             │   ├─ re-score               │
  │                             │   ├─ keep or revert         │
  │                             │   └─ repeat                 │
  │                             │                             │
  │                             └────────────────────────────▶│
  │                                                           │
  │                              3. Review results            │
  │                                 (scores, git log,         │
  │                                  results.tsv)             │
```

## Quick Start

### 1. Point to your skill file

```bash
python autoresearch/setup.py
```

The wizard asks for:
- **Skill file** — auto-detects `.instructions.md`, `CLAUDE.md`, etc.
- **Goal** — what to improve, in plain language
- **Source files** — your code (auto-detected, used for accuracy checks)

It generates a scoring config, runs a baseline eval, and you're ready.

### 2. Launch the autonomous loop

Open the repo in a coding agent and say:

```
Read autoresearch/program.md and follow the instructions.
```

The agent loops: **score → hypothesize → edit → verify → commit/revert → repeat**.
Each improvement gets a git commit. Each failure auto-reverts. Everything is logged.

### 3. Review results

```bash
python autoresearch/eval.py --results
```

```
  AUTORESEARCH RESULTS
  ════════════════════

    #  Score      Δ  Status    Description
  ───  ───────  ──────  ────────  ──────────────────
    0  22/35    +0.0  📊 baseline  initial state
    1  25/35    +3.0  ✅ keep     added error handling section
    2  25/35    +0.0  ↩️ revert   tried restructuring (no gain)
    3  28/35    +3.0  ✅ keep     added code examples for auth flow
    4  31/35    +3.0  ✅ keep     mentioned all key functions

  Baseline:  22/35 (62.9%)
  Current:   31/35 (88.6%)
  Kept:      3 improvements
  Reverted:  1 experiments
```

Or review the git log: `git log --oneline`

## How Setup Works

`setup.py` auto-generates scoring checks in three categories:

| Category | How it's generated | What it checks |
|----------|--------------------|---------------|
| **Structure** | Universal (always included) | Title, sections, code blocks, formatting, length |
| **Coverage** | Scans your source files | Mentions key functions, classes, constants, libraries |
| **Goal** | Parses your improvement goal | Checks for terms related to your stated goal |

The generated config is saved to `autoresearch/config.py`. You can edit it
to add, remove, or adjust checks before running the loop.

## CLI Reference

```bash
# Interactive setup wizard
python autoresearch/setup.py

# Setup with flags (skip prompts)
python autoresearch/setup.py --skill path/to/skill.md --goal "improve accuracy"

# Run eval (score the skill file)
python autoresearch/eval.py

# Score + log to results.tsv
python autoresearch/eval.py --log "description of change"

# View results summary
python autoresearch/eval.py --results

# JSON output (for scripting)
python autoresearch/eval.py --json
```

## File Structure

```
autoresearch/
├── setup.py       ← Interactive setup wizard (generates config)
├── eval.py        ← Scoring engine (reads config, scores target)
├── config.py      ← Generated scoring config (or manually edited)
├── program.md     ← Agent loop instructions (read by coding agent)
└── results.tsv    ← Iteration log (created by eval --log)
```

## Check Types

| Type | What it checks | Key params |
|------|---------------|------------|
| `has_all` | ALL terms present (case-insensitive) | `terms` |
| `has_any` | ANY term present | `terms` |
| `count_of` | Score ∝ matched/total terms | `terms` |
| `regex` | Regex pattern matches | `pattern` |
| `word_range` | Word count in [min, max] | `min`, `max` |
| `headers` | ≥N headings at given level | `min`, `level` |
| `code_blocks` | ≥N code blocks | `min` |
| `ordered` | Terms in sequential order | `terms` |
| `tiered` | First matching tier wins (top-down) | `tiers` |

## Requirements

- Python 3.10+
- No pip dependencies (stdlib only)
- A coding agent to run the loop (Claude Code, Copilot CLI, Cursor, etc.)

## Included Example

The repo includes a causal analysis skill file (`.github/instructions/causal.instructions.md`)
and source code (`app/*.py`) as a working example. Run `python autoresearch/setup.py` and
point it at the causal instructions to see it in action.
