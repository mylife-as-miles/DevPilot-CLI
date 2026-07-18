---
name: karpathy-coding
description: Careful, simple, surgical, verification-driven coding discipline for DevPilot runs.
when_to_apply: Whenever DevPilot edits source code, fixes bugs, refactors, adds tests, implements a hypothesis, prepares a minimal patch, or runs executor worktrees.
---

# Karpathy Coding Guidelines for DevPilot

Behavioral guidelines for reducing common coding-agent mistakes during DevPilot runs.

Adapted for DevPilot from the MIT-licensed Karpathy-inspired Claude Code guidelines by multica-ai.

## When to use this skill

Use this skill whenever DevPilot is:
- editing source code
- fixing bugs
- refactoring
- adding tests
- implementing a hypothesis
- preparing a minimal patch
- running executor worktrees

## Principles

### 1. Think Before Coding
- State assumptions explicitly.
- Surface ambiguity before implementation.
- Present tradeoffs when multiple approaches exist.
- Push back if a simpler or safer approach exists.

### 2. Simplicity First
- Write the minimum code that solves the task.
- Do not add speculative features.
- Do not create abstractions for one-off logic.
- If a shorter clear solution exists, prefer it.

### 3. Surgical Changes
- Touch only files required for the task.
- Do not refactor unrelated code.
- Match existing code style.
- Remove only unused code introduced by the current change.
- Mention unrelated dead code instead of deleting it.

### 4. Goal-Driven Execution
- Convert tasks into verifiable success criteria.
- Prefer tests that reproduce the issue before fixing.
- Verify before and after refactors.
- Loop until the stated check passes.

## Executor checklist

Before editing:
- What exactly is the goal?
- What files must change?
- What assumptions am I making?
- What check will prove success?

During editing:
- Keep the patch minimal.
- Avoid drive-by cleanup.
- Preserve unrelated comments and formatting.
- Prefer existing patterns.

After editing:
- Run the narrowest relevant test.
- Remove only artifacts introduced by the change.
- Summarize changed files and verification.
