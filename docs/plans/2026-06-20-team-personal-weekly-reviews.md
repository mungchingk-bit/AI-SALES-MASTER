# Team and Personal Weekly Reviews Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split weekly review into an admin-only team branch and a user-isolated personal branch.

**Architecture:** Team reports use a reserved store owner and aggregate every named salesperson, while personal reports retain salesperson ownership. The UI resolves permissions from the authenticated account rather than trusting the visible salesperson selector, and growth context exposes only a salesperson's own team insight.

**Tech Stack:** Python 3.11, Gradio, dataclasses, JSON stores, unittest.

---

### Task 1: Extend weekly report data
- Add scope, salesperson count, and per-person insights with legacy defaults.
- Keep team reports under a reserved non-user owner key.

### Task 2: Add team aggregation
- Refactor personal generation into a shared scoped generator.
- Aggregate all named users for team reports and include owner labels in source context.
- Produce per-person strength, improvement, and next action.

### Task 3: Enforce permissions in the UI
- Pass authenticated username into the weekly tab.
- Add Personal Review and Team Review sub-tabs.
- Auto-resolve a sales account to its own display name; require admin for team access.

### Task 4: Extend the growth loop safely
- Merge only the matching salesperson's team insight into that salesperson's growth context.
- Never expose other salespeople's details.

### Task 5: Verify and publish
- Test team aggregation, unchanged detection, role resolution, and growth isolation.
- Run all tests, syntax/import checks, commit, push, and create a cloud bundle.
