# `aegis.nlq` — the single NLQ engine

One rule-based engine, used by both clients:

- `dictionary.py` — closed vocabulary (525 canonical items / ~1,630 aliases /
  20 rooms) in `data/dictionary.json`, merged over the ontology in
  `aegis.core.vocabulary`. Word-boundary, longest-first lookup.
- `engine.py` — `AnswerEngine.ask(question, memory_view)` returns an
  `AskResult`: a ≤2-sentence grounded answer or an honest abstention with a
  reason. `LOCATE` works; `TEMPORAL`/`ACTIVITY` abstain explicitly until
  implemented (see `TODO.md` P1.1). No LLM on the mandatory path; the engine
  never writes a location it did not read from a state.
- `cli.py` — `aegis-ask`, the terminal client. `--transport local` reads a
  local graph; `--transport http` (default when `AEGIS_MODAL_BASE_URL` is set)
  asks the deployed API.
- `data/` — curated `home_vocabulary.json` and generated `dictionary.json`.

The API entry point is `GET/POST /api/v1/ask` in `aegis.remote.api`; the same
engine is used there. Tests: `tests/test_nlq.py`.
