# Archived documents — history only

These files are snapshots from earlier phases of Aegis. They are kept for
traceability, **not** as instructions. The authoritative sources are
[`CONTEXT.md`](../CONTEXT.md) (facts/architecture) and
[`TODO.md`](../TODO.md) (work), plus the three active design docs
`docs/running_aegis.md`, `docs/artifact_contracts.md`, and
`docs/evaluation_suite.md`.

Do not follow a checklist or test count from a file in this directory.

| File | What it was | Why archived / what is still useful |
|---|---|---|
| `AGENT-DOC_context.md` | 2026-11-07 model-sync context | Pre-dates the M1/M2 build-out. Claims `home_registry` unwired, `outputs/` absent, constant `confidence=0.96`. Useful only for the historical NLQ design discussion (§7, §12). |
| `AGENT-DOC_ToDos.md` | 2026-11-06 milestone baseline | Old 84-test baseline and M1–M4 gaps; most items are now done. Superseded by `TODO.md`. |
| `LEGACY_AEGIS_MIGRATION_NOTES.md` | 2026-10-11 notes on an older repo | Migration candidates that were subsequently implemented (live source, session writer, CLI). Historical. |
| `ProposalDefenseResult.md` | Proposal panel feedback | Original scope/UX/resource comments; useful background only. |
| `fyp1_mid_defense_dossier.md` | FYP-1 mid-term dossier | Contains wrong claims: 55 tests, `S=5.0×`, Z-up frame. Do not quote as current state. |
| `plan.md` | WP01–WP35 implementation plan (2026-11-14/16) | Excellent engineering rationale and detailed design; WP01–WP15 landed, WP16–WP35 remain unimplemented. Mine for *why*, use `TODO.md` for *what*. |
| `todo.md` | Master TODO at 2026-11-15 | Reports 326 tests (now 356+49); useful traceability of WP01–WP15 evidence. Superseded by `TODO.md`. |
| `implementation_log.md` | WP01–WP15 commit log | Useful commit-by-commit record of what changed and what was left unmeasured. |
| `answer.md` | Retention/elevation/vocabulary design notes | Background reasoning behind compaction, gravity frame and the ontology. |
| `evaluation_plan.md` | Superseded evaluation protocol | Replaced by `docs/evaluation_suite.md`; retained for the persistence diagnosis (§7) and script index (§8). |
| `NLQ_MODAL_HANDOFF.md` | 2026-11-09 NLQ/Modal handoff | Operational snapshot of the deployed CPU API and blockers. Some URLs/facts are stale. |
| `NLQ_README.md` | Old `NL Querying/README.md` | Describes the pre-fold standalone NLQ folder; superseded by `src/aegis/nlq/README.md`. |
| `NL-Querying/` | The entire pre-fold standalone NLQ subsystem (code, tests, scripts, sample video) | Preserved verbatim, including uncommitted work. The single replacement lives in `src/aegis/nlq/` and is served by `src/aegis/remote/serve.py`. |
