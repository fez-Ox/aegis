# Long-term memory control and persistence

> Feasibility study for bounded memory growth. The compaction prototype lives in the evaluation package; it is not yet the production storage format.

## Why this matters

The current timeline writes one entry per known instance per keyframe, even when an object is occluded. That is what gives object permanence, but it grows as `frames × known instances`. Run-length encoding turns that into `state changes × instances`, while keeping every instance's latest state and every event.

## Measured results

| Dataset | Snapshot every | Frames | Entries | Instances | State runs | Original | Compacted | Ratio | Full retention | Semantic retention | Centre p95 | Latest exact | Query agreement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| demo04 | 0 | 117 | 268 | 5 | 13 | 178.3 KiB | 24.8 KiB | 7.2× | 100.00% | 100.00% | 0.363 | 100.00% | 100.00% |
| demo04 | 1 | 117 | 268 | 5 | 13 | 178.3 KiB | 94.5 KiB | 1.9× | 100.00% | 100.00% | 0.000 | 100.00% | 100.00% |
| demo04 | 10 | 117 | 268 | 5 | 13 | 178.3 KiB | 32.8 KiB | 5.4× | 100.00% | 100.00% | 0.241 | 100.00% | 100.00% |
| demo04 | 30 | 117 | 268 | 5 | 13 | 178.3 KiB | 27.9 KiB | 6.4× | 100.00% | 100.00% | 0.245 | 100.00% | 100.00% |
| demo03 | 0 | 100 | 981 | 16 | 58 | 528.5 KiB | 92.0 KiB | 5.7× | 100.00% | 100.00% | 0.219 | 100.00% | 100.00% |
| demo03 | 1 | 100 | 981 | 16 | 58 | 528.5 KiB | 353.4 KiB | 1.5× | 100.00% | 100.00% | 0.000 | 100.00% | 100.00% |
| demo03 | 10 | 100 | 981 | 16 | 58 | 528.5 KiB | 121.1 KiB | 4.4× | 100.00% | 100.00% | 0.137 | 100.00% | 100.00% |
| demo03 | 30 | 100 | 981 | 16 | 58 | 528.5 KiB | 105.8 KiB | 5.0× | 100.00% | 100.00% | 0.178 | 100.00% | 100.00% |

Query agreement is measured with auto-generated label probes when no `--queries` file is supplied. The same questions are answered from the original latest state and the compacted latest state.

## Projected long-term growth

| Dataset | Original / hour | Compacted / hour | Original 8 h | Compacted 8 h | Original 24 h | Compacted 24 h | State runs / hour |
| --- | --- | --- | --- | --- | --- | --- | --- |
| demo04 | 13.51 MiB | 2.11 MiB | 108.1 MiB | 16.9 MiB | 324.2 MiB | 50.7 MiB | 1008.3 |
| demo03 | 18.76 MiB | 3.27 MiB | 150.1 MiB | 26.1 MiB | 450.3 MiB | 78.4 MiB | 2108.4 |

These are **linear projections** from the observed clip duration, not measured 8-hour or 24-hour sessions. They are labelled as such in the JSON. A real long-term study would replay or record a full day and report the same audit.

## Feasibility verdict

**Feasible in principle.** At least one tested interval preserved full semantic state, every latest state exactly, and exact geometry (centre p95 <= 0.05 scene units).

- Exact geometry: `snapshot_interval=1` on `demo04` — 1.9× smaller, centre p95 0.000 scene units.
- Balanced: `snapshot_interval=30` on `demo04` — 6.4× smaller (84.4% saved), centre p95 0.245 scene units, full retention 100.00%, latest-state exactness 100.00%.

Queries are served from the exact latest state, so answer agreement does not depend on interpolating historical geometry.

## What this does and does not prove

- **Proves:** the representation can preserve every instance's semantic state, latest state, events, anchors, and rooms while storing far fewer per-frame entries.
- **Proves:** query answers on the compacted latest state can be compared with the original; exact semantic retention and query agreement are reported, not assumed.
- **Does not prove:** real-world persistence accuracy over days. That needs a long recording with labelled occlusion/relocation events.
- **Does not prove:** production database performance. The prototype serialises JSON; a real deployment should use SQLite/Parquet with indices.
- The centre error is in **scene units**, not metres, because VGGT-Ω is scale-ambiguous. Use the controlled-room experiment for metric calibration.

## Suggested integration

1. Keep the full-resolution timeline as an append-only archive (or delete it after compaction).
2. Serve queries from the compacted latest state and state runs.
3. Keep a sparse snapshot every 10–30 keyframes for point-in-time reconstruction.
4. Store events, anchors, and rooms unchanged; they are already small.
5. Add a retention policy: keep all state runs, but downsample snapshots for sessions older than N days.
