# Weekly Growth Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an incremental Monday-to-current review of training evaluations and face-to-face reports, then feed its lessons into later training and evaluation.

**Architecture:** `WeeklyReviewer` gathers user-isolated sources, hashes their content, and creates or updates one report per natural week only when data changes. `WeeklyReviewStore` exposes the latest report as compact growth context for `TrainingManager` and `Evaluator`.

**Tech Stack:** Python 3.11, dataclasses, JSON file stores, Gradio, unittest.

---

### Task 1: Extend the weekly review model and store
- Add face-to-face count, strengths, source signature, and update timestamp with backward-compatible defaults.
- Add latest-review and growth-context helpers.

### Task 2: Build incremental multi-source reviews
- Filter Monday-to-current sessions, evaluations, and face-to-face reports by user.
- Hash sources; skip unchanged data and update the same report when data changes.
- Send bounded source details to the LLM.

### Task 3: Surface source coverage and status
- Show both source counts and whether a report was created, updated, or unchanged.

### Task 4: Close the growth loop
- Inject the latest focus into later simulations and evaluations without exposing coaching instructions.

### Task 5: Verify and publish
- Run unit tests, syntax checks, and diff checks; then commit, push, and build an offline cloud bundle.
