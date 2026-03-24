# autoresearchSkill

A **generic framework** for iteratively improving any skill / instruction file using
[Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch): an
automated loop where an AI agent edits a target file, scores the result, and keeps
improvements via git commits.

Ships with a **causal analysis skill** as a working example — swap in your own
skill file and scoring config to optimize anything.

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌───────────┐
│ program.md  │────▶│ Agent edits │────▶│  eval.py  │
│ (loop rules)│     │ target file │     │ (scores)  │
└─────────────┘     └──────┬──────┘     └─────┬─────┘
                           │                   │
                    ┌──────▼──────┐     ┌──────▼──────┐
                    │ Improved?   │ YES │ git commit  │
                    │ score > old │────▶│ new baseline│
                    └──────┬──────┘     └─────────────┘
                       NO  │
                    ┌──────▼──────┐
                    │ git revert  │
                    │ try again   │
                    └─────────────┘
```

| File | Role | Agent can edit? |
|------|------|-----------------|
| `autoresearch/config.py` | **Your scoring criteria** — define what to check | ❌ No (you edit before running) |
| `autoresearch/eval.py` | **Scoring engine** — reads config, scores target | ❌ No |
| `autoresearch/program.md` | **Agent instructions** — drives the loop | ❌ No |
| Your target file | **The file being improved** | ✅ Yes |

## Quick Start

### 1. Clone and set your target

```bash
git clone https://github.com/dm458/autoresearchSkill.git
cd autoresearchSkill
```

### 2. Edit `autoresearch/config.py`

Set your target file and scoring checks:

```python
# The file the agent will improve
TARGET_FILE = "path/to/your/skill.md"

# Source code files for accuracy reference (optional)
SOURCE_FILES = ["src/main.py", "src/utils.py"]

# Scoring checks — see config.py for all check types
CHECKS = [
    {"id": "s1", "cat": "structure", "name": "Has clear title",  "pts": 2, "type": "regex",   "pattern": r"^#\s+.+"},
    {"id": "w1", "cat": "workflow",  "name": "Covers auth flow",  "pts": 3, "type": "has_all", "terms": ["login", "token", "refresh"]},
    {"id": "a1", "cat": "accuracy",  "name": "Uses correct API",  "pts": 2, "type": "has_any", "terms": ["fetchUser(", "getUser("]},
    # ... add your checks
]
```

### 3. Verify the eval works

```bash
python autoresearch/eval.py
```

### 4. Launch the autoresearch loop

Open the repo in a coding agent (Claude Code, Copilot CLI, Cursor, etc.) and say:

```
Read autoresearch/program.md and follow the instructions.
Start by running: python autoresearch/eval.py
```

The agent loops: **score → hypothesize → edit → re-score → commit or revert → repeat**.

Review the experiment log with `git log --oneline`.

## Check Types Reference

| Type | What it does | Key params |
|------|-------------|------------|
| `has_all` | All terms must appear (case-insensitive) | `terms` |
| `has_any` | Any term must appear | `terms` |
| `count_of` | Score ∝ matched/total terms | `terms` |
| `regex` | Regex pattern must match (multiline) | `pattern` |
| `word_range` | Word count in [min, max] | `min`, `max` |
| `headers` | ≥N headings at given level | `min`, `level` (default 2) |
| `code_blocks` | ≥N ``` code blocks | `min` |
| `ordered` | Terms appear in sequential order | `terms` |
| `tiered` | First matching tier wins (top-down) | `tiers: [{score, condition, terms}]` |

## Included Example: Causal Analysis Skill

The repo ships with a working config for a causal analysis skill file
(`.github/instructions/causal.instructions.md`) that scores **117/127 (92.1%)**
with 10 points of improvement potential. Run it as-is to see the pattern in action.

## Requirements

- Python 3.10+
- No pip dependencies (eval uses only stdlib)
- A coding agent to run the loop (Claude Code, Copilot CLI, Cursor, etc.)
