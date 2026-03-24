# autoresearchSkill

Autoresearch loop to iteratively improve the **causal analysis copilot instructions** (`causal.instructions.md`) — a skill file that tells AI coding agents how to perform causal inference using EconML.

Based on [Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch): an automated loop where an AI agent edits a target file, scores the result, and keeps improvements via git commits.

## How It Works

| File | Role | Agent can edit? |
|------|------|-----------------|
| `.github/instructions/causal.instructions.md` | **Target** — the skill file to improve | ✅ Yes |
| `autoresearch/eval.py` | **Eval** — scores the target (127 pts) | ❌ No |
| `autoresearch/program.md` | **Program** — drives the agent loop | ❌ No |
| `app/*.py` | **Source code** — ground truth for accuracy checks | ❌ No |

The eval checks 5 categories:
1. **Structure** (21 pts) — formatting, sections, code blocks
2. **Workflow completeness** (34 pts) — all analysis steps covered
3. **Codebase accuracy** (33 pts) — matches actual source code
4. **Code examples** (15 pts) — working code snippets
5. **Agent usefulness** (24 pts) — actionable guidance

## Baseline

Current score: **117/127 (92.1%)**

## Quick Start

1. Clone this repo
2. Open it in a coding agent (Claude Code, Copilot CLI, Cursor, etc.)
3. Tell the agent:

```
Read autoresearch/program.md and follow the instructions.
Start by running: python autoresearch/eval.py
```

The agent will loop: **score → hypothesize → edit → re-score → commit/revert → repeat**.

Review the experiment log with `git log --oneline`.

## Requirements

- Python 3.10+
- No pip dependencies needed (eval uses only stdlib)
