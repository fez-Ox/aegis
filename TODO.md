# TODO.md — Aegis single task list

> **Rule:** This is the only task list. Facts and architecture live in
> `CONTEXT.md`. Do not mark an item done without a passing test, a measured
> result, or a recorded artifact. Updated 2026-11-18 (branch `feat/NLQ`).

Legend: `[x]` done and evidenced · `[~]` partly done · `[ ]` open.
Priority: **P0** blocks the single pipeline · **P1** required before final
delivery · **P2** measurement/documentation.

Measured verification today: `uv run pytest -q` → **365 passed** (one suite;
the old standalone NLQ tests were archived with the old folder).

---

## P0 — one strong pipeline (current focus)

- [x] **P0.1 One authoritative context/task pair.** `CONTEXT.md` + `TODO.md`;
      all older docs and the old NLQ folder moved to `docs/archive/` with an
      index; active files now point at the new sources. Every substructure has
      a `README.md`.
- [x] **P0.2 NLQ engine lives in `src/aegis/nlq/`.** Dictionary, closed
      vocabulary and engine folded into the package; the old `NL Querying/`
      folder is archived. One implementation serves the API and the CLI.
- [x] **P0.3 `/api/v1/ask` on Modal CPU.** GET/POST endpoint in `remote/api.py`
      reads the graph from the Modal volume via the repository and returns a
      grounded answer or honest abstention. `remote/serve.py` deploys it
      without GPU/LLM dependencies.
- [x] **P0.4 No local artifact download on the normal path.** `run_pipeline.py`
      keeps artifacts on the volume by default; `--download` opts into local
      Rerun/home-store demos. The app and `aegis-ask` use HTTPS.
- [x] **P0.5 Thin Flutter app.** Single ask screen + answer card (evidence,
      place, time); all dataset/simulator/capture/caregiver/mutation UI removed.
      Flutter SDK is absent locally; CI remains the Dart check.
- [x] **P0.6 Terminal ask script.** `aegis-ask` with local/http transports.
- [x] **P0.7 One CI-covered suite.** `tests/test_nlq.py` covers dictionary,
      engine, abstentions, GET/POST `/ask` and the CLI; all 365 tests run under
      the standard `pytest` command. Ruff check/format clean on touched code.

## P1 — required before final delivery

- [ ] **P1.1 Temporal answers.** "When did I last see X?", "what did I do this
      morning?", relative-time parsing against wall-clock, hot + summarised
      tiers, summarised labelling.
- [ ] **P1.2 Calibrated confidence + abstention.** Replace passthrough
      confidence with detection × identity × support × recency; configurable
      threshold; distinguish never-observed / stale / low-confidence.
- [ ] **P1.3 Freshness.** 6-hour window; real "time ago" from
      `last_seen_timestamp`; stale answers say when last seen.
- [ ] **P1.4 Evidence references on every non-abstaining answer.** Observation
      id, timestamp, anchor/room, crop URL or text fallback; 100% coverage.
- [ ] **P1.5 Multi-instance clarification** and a persistent query log.
- [ ] **P1.6 Speech input** (on-device ASR preferred) + confirm/correct step;
      typed queries stay equivalent.
- [ ] **P1.7 Auth, grants, consent, audit, CORS.** No unprotected mutating
      endpoints; caregiver scopes enforced on every request.
- [ ] **P1.8 Encryption at rest + TLS**, raw-frame purge, verified full history
      deletion, privacy limitations statement.
- [ ] **P1.9 Optional LLM planner** (parser only; never writes answer text),
      off by default, behind the validated closed vocabulary.

## P2 — measurement and records

- [ ] **P2.1 Physical one-hour soak** (AC-01), 10 s disconnect recovery
      (AC-03), scripted keyframe clip (AC-02), real backlog run (AC-29).
- [ ] **P2.2 Object placement accuracy** (AC-04) and activity order (AC-05)
      with recorded ground truth.
- [ ] **P2.3 Room metrics** (AC-22/SC9) on an annotated multi-room clip.
- [ ] **P2.4 Controlled-room experiment** (Option D) with measured grid and
      scale-aligned error.
- [ ] **P2.5 Held-out `demo05` annotations** so Option A can be scored;
      no tuning after freeze.
- [ ] **P2.6 Ego4D** remains **NO-GO / 0%**; report as future work unless
      access, data, adapter, and official scorer all exist.
- [ ] **P2.7 7/30-day longitudinal study** for long-term persistence.
- [ ] **P2.8 Latency benchmark** (p50/p95/max over ≥100 warm requests) and
      before/after-compaction accuracy.
- [ ] **P2.9 Supervisor decision #9:** evidence crops are kept past the 24-hour
      raw-frame rule; `memory.evidence.enabled` reverses it.

## Explicitly not doing

- No dense point-cloud memory; no manual VGGT scale/axis transforms.
- No client-side tracking, simulation, or memory mutation in the mobile app.
- No Ego4D leaderboard claim without official splits and scorer.
- No clinical/usability claim without ethics approval.

---

## Verification and tooling notes

- Core tests: `uv run pytest -q` → 356 passed. NLQ tests: 49 passed.
- CI (`.github/workflows/ci.yml`) runs ruff check/format, pytest with
  `--cov=aegis --cov-fail-under=75`, and Flutter analyze/test, on
  `main`/`develop` only.
- `uv` is at `~/.venvs/tools/bin/uv`; system Python is 3.14, project requires
  3.12. Modal GPU needs a payment method; `facebook/VGGT-Omega` is gated (use
  `HF_TOKEN` or the public `wincentIsMe/VGGT-Omega` mirror for research).
