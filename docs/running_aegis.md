# Running Aegis

This guide is for running the project on a machine that has never run it before. Part A runs it step by step. Part B is a checklist of what to confirm yourself before trusting the results.

Commands run from the repository root unless a step says otherwise. Use the `feat/memory-plan` branch: everything below describes that code.

---

# Part A — Step by step

## 0. What you need

| Need | Why | Where to get it |
|---|---|---|
| Linux or macOS laptop, ~10 GB free disk | Code, downloaded outputs, live captures | — |
| [`uv`](https://docs.astral.sh/uv/) | Installs Python 3.12 and every dependency | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| A Modal account | GPU stages (VGGT-Ω, YOLOE, SAM 2) run on Modal L4 GPUs | <https://modal.com> |
| A Hugging Face account with access to `facebook/VGGT-Omega` | The VGGT-Ω weights are gated | <https://huggingface.co/facebook/VGGT-Omega>: request access, then create a read token |
| Flutter SDK + an Android phone (USB debugging on) | Only for the mobile app | <https://docs.flutter.dev/get-started/install> |
| Android phone with the **IP Webcam** app | Only for live capture | Google Play |

GPU stages cost Modal credits. A short demo video takes a few minutes of L4 time.

## 1. Get the code

```bash
git clone git@github.com:fez-Ox/aegis.git
cd aegis
git checkout feat/memory-plan
git pull
```

## 2. Install and run the local tests

```bash
uv sync --dev
uv run pytest -q
uvx ruff check src tests run_pipeline.py run_server.py
```

**Expected:** `326 passed` (or more) and `All checks passed!`. If this fails, stop here; nothing later will work.

To use the Rerun viewer, also install it:

```bash
uv sync --dev --group viewer
```

## 3. Connect to Modal

```bash
uv run modal setup            # opens a browser to log in, writes ~/.modal.toml
uv run modal profile current  # shows which workspace you are using
```

**Decide which Modal workspace to use.**

- **Teammate's workspace:** the data volume (`aegis-poc-data`), the model cache (`aegis-model-cache`) and the secret (`aegis-secrets`) already exist there, with any datasets your teammate uploaded. Ask them to invite you to the workspace, then switch to it with `uv run modal profile activate <workspace>`.
- **Your own workspace:** the volumes are created automatically on the first run, empty. You must create the secret yourself (next step). The first run also downloads all model weights into the cache, so it is slower.

Create the secret (only if it does not exist in the workspace you use):

```bash
uv run modal secret create aegis-secrets HF_TOKEN=hf_xxxxxxxxxxxxxxxx
uv run modal secret list      # must list aegis-secrets
```

Also put the token in a local `.env` file. `run_pipeline.py` reads it and passes it to the GPU stages:

```bash
echo 'HF_TOKEN=hf_xxxxxxxxxxxxxxxx' > .env   # .env is git-ignored; never commit it
```

## 4. Run the pipeline on a sample video

The pipeline downloads a preset egocentric video, uploads it to Modal and runs four stages: preprocess, VGGT-Ω reconstruction, detection + 3D lifting + memory graph, and the Rerun recording. It then downloads the results and ingests them into the home memory store.

Presets: `put_shoes`, `fridge_food`, `empty_trash`, `arrange_pots`, `make_coffee`, `sort_clothes`, `set_table`, `pick_place_table`.

```bash
uv run python run_pipeline.py \
  --video put_shoes \
  --dataset-id shoes01 \
  --config-path config/demo01.yaml \
  --recorded-at 2026-11-15T10:00:00+05:00 \
  --stage all
```

- Always give `--dataset-id`. With the default (`demo01`), a preset run is renamed to `demo_<preset>`.
- `--recorded-at` is the real start time of the video. Without it the store labels the session with the time of ingest.
- `config/demo01.yaml` uses shoe-scene prompts. `config/demo.yaml` prompts for the whole vocabulary (`config/vocabulary.yaml`).

**Expected at the end:**

- A benchmark summary (stage times, keyframes, detections).
- `✓ Downloaded ...` lines.
- `✓ Ingested shoes01 into home home01: {...}`.

Files appear under `outputs/shoes01/`:

```text
outputs/shoes01/objects/r4d_scene_graph.json   memory graph (schema 2)
outputs/shoes01/objects/events.json            events
outputs/shoes01/objects/evidence/*.jpg         object crops
outputs/shoes01/geometry/poses.json            camera poses
outputs/shoes01/viewer/demo.rrd                Rerun recording
outputs/_homes/home01/memory.db                durable home memory
outputs/_homes/home01/home_map.json            room names
```

To rerun a single stage on an already uploaded dataset, use `--stage preprocess|vggt|detect|rerun`. VGGT pointmaps are deleted after `detect`, so re-running `detect` alone needs `vggt` again, unless `vggt.keep_pointmaps: true` is set in the config.

## 5. Look at the result

```bash
uv run --group viewer rerun outputs/shoes01/viewer/demo.rrd   # video + 3D memory
uv run aegis-memory show --home-id home01                     # rooms, furniture, objects
uv run aegis-memory size --home-id home01                     # store size and row counts
```

## 6. Start the memory server

```bash
uv run python run_server.py --dataset-id shoes01 --enable-simulator
```

Leave out `--enable-simulator` to hide the demo simulation buttons.

The server prints its LAN URL. Open `http://localhost:8000/docs` for the interactive API. Quick checks:

```bash
curl 'http://localhost:8000/api/v1/health?dataset_id=shoes01'
curl 'http://localhost:8000/api/v1/query?item=shoes&dataset_id=shoes01'   # one video's graph
curl 'http://localhost:8000/api/v1/query?item=shoes&home_id=home01'       # durable home memory
curl 'http://localhost:8000/api/v1/timeline?home_id=home01'
curl 'http://localhost:8000/api/v1/activities?home_id=home01'
```

The mobile app always sends `dataset_id`, so it reads one video's graph. The `home_id` endpoints read the long-term store.

## 7. Run the mobile app

```bash
cd apps/mobile
flutter pub get
flutter run            # with the phone connected over USB
```

- **Over USB:** `run_server.py` sets up `adb reverse` automatically when it finds a device, so the app's default `http://127.0.0.1:8000` works.
- **Over Wi-Fi:** open the app's server settings and enter the laptop's LAN IP (printed by `run_server.py`); port 8000 is added automatically.

If the app cannot reach the server it shows *"Can't reach Aegis memory…"*. It no longer shows invented answers.

## 8. Live capture from a phone

1. Phone and laptop on the same Wi-Fi. In **IP Webcam**, tap *Start server* and note the address, e.g. `http://192.168.1.23:8080`.
2. Record:

   ```bash
   uv run aegis-ingest \
     --url 'http://192.168.1.23:8080/video' \
     --output-root ./captures \
     --config-path config/live.yaml \
     --session-id walk01 \
     --pause-file captures/.pause
   ```

   Stop with `Ctrl+C`. Pause with `touch captures/.pause`, resume with `rm captures/.pause`.

3. Process it in segments (default 120 frames each): promote, upload, run the GPU stages, download and ingest, one segment at a time.

   ```bash
   uv run python run_pipeline.py \
     --config-path config/live.yaml \
     --live-session captures/walk01 \
     --dataset-id walk01 \
     --stage live
   ```

   - Add `--follow` to process while the capture is still running.
   - Add `--rerun` to also make a Rerun recording per segment.
   - Re-running the same command resumes after the last finished segment.

4. **Optional:** pause and resume from the app. Start the server with the capture locations:

   ```bash
   AEGIS_CAPTURE_DIR=./captures AEGIS_CAPTURE_PAUSE_FILE=captures/.pause \
     uv run python run_server.py --dataset-id walk01_seg0001
   ```

   A *Recording / Paused* switch then appears at the top of the app.

## 9. Retention and measurements

- Compaction (history older than 3 days becomes text summaries) runs after every ingest. To run it by hand:

  ```bash
  uv run aegis-memory compact --home-id home01
  ```

- The measurement scripts are listed in `docs/evaluation_plan.md` §8. They need `--laptop` and `--phone`, and they warn when the working tree has uncommitted changes.

---

# Part B — What to confirm yourself

Work through these in order. Tick a box only when you have seen the expected result yourself.

## B1. Machine and accounts

- [ ] `uv --version` works, and `uv run python --version` prints 3.12.x.
- [ ] `git branch --show-current` prints `feat/memory-plan`, and `git log -1 --oneline` matches GitHub.
- [ ] `uv run pytest -q` shows `326 passed` or more, with no failures.
- [ ] `uvx ruff check src tests run_pipeline.py run_server.py` prints `All checks passed!`.
- [ ] `uv run modal profile current` shows the workspace you intend to use (yours or your teammate's).
- [ ] `uv run modal secret list` lists `aegis-secrets`.
- [ ] Your Hugging Face account has been **granted** access to `facebook/VGGT-Omega` (the model page no longer asks you to request access).
- [ ] `.env` contains `HF_TOKEN=hf_...`, and `git status` does not show `.env`.
- [ ] You know the Modal billing limit on the workspace, so a long run cannot surprise you.

## B2. First pipeline run (checks the GPU code, which was never run after the latest changes)

These code paths were changed but have only been tested locally with fakes. Your first Modal run is their real test.

- [ ] **Container images build.** The first run builds `VGGT_IMAGE` and `PERCEPTION_IMAGE`; there are no `pip` errors (the perception image now also installs `transformers`).
- [ ] **Preprocess finishes** with a frame count and `preprocess_source: source_video`.
- [ ] **VGGT stage finishes.** It loads the model through the new `load_model`, runs under autocast (`bfloat16`) and writes per-keyframe pointmaps. Check for *no* `max_keyframes` error. If there is one, the video has more than 120 keyframes after the stride: raise `vggt.keyframe_stride` or lower `video.sample_fps`.
- [ ] **`gravity.json` looks sane.** Download it with `uv run modal volume get aegis-poc-data shoes01/outputs/geometry/gravity.json /tmp/g.json`. Expect `source: floor_plane`, `confidence` ≥ 0.5 and `camera_height` roughly 1.0–2.0. If you see `camera_prior` or `assumed`, the floor was not found, and "under / on the floor" answers become "near".
- [ ] **Detect stage finishes.** This checks batched YOLOE prediction with `retina_masks=True`, SAM 2 in `fallback` mode and the new duplicate suppression. The stage result shows a non-zero `detections_2d`, `boxes_3d` and `evidence_crops`.
- [ ] **Rerun stage finishes,** and `demo.rrd` opens. Boxes sit on the furniture and are not rolled sideways. Room pillars point upward.
- [ ] **Warm containers are reused.** In the Modal dashboard, a second run within 5 minutes reuses the GPU containers, and models are not reloaded.
- [ ] The run ends with `✓ Ingested shoes01 into home home01`.

## B3. Memory correctness (compare with the video)

- [ ] `uv run aegis-memory show --home-id home01` lists only real furniture as anchors. There is no `Storage Cabinet #1` unless a cabinet is actually in the video.
- [ ] Each object's relation matches the video: `inside`, `on_surface`, `under`, `on_floor`, `next_to` or `carried_by_user`.
- [ ] Doors, windows and stairs never appear as objects.
- [ ] `outputs/shoes01/objects/evidence/` crops show the object, not a full frame or the background.
- [ ] The query answer is at most two sentences, says "last seen" for objects out of view, and has `confidence` set to the stored value or `null` (never 0.96).
- [ ] Re-run the three demos your teammate used (`put_shoes`, `fridge_food`, `empty_trash`, plus Demo06 if you have that video) and note any answer that changed. The demo-specific rules were removed, so changes are expected. Each should be either correct for the video or written down as a regression.

## B4. Home store and rooms

- [ ] Ingesting a second video into the same home keeps object IDs stable when the same object reappears (`aegis-memory show`).
- [ ] Rename a room: `curl -X POST 'http://localhost:8000/api/v1/rooms/rename?home_id=home01&room_id=1&label=Hallway'`. Then `outputs/_homes/home01/home_map.json` shows `Hallway` with `label_source: caregiver`.
- [ ] Restart `run_server.py` and query again: the room is still called `Hallway`.
- [ ] `curl 'http://localhost:8000/api/v1/health?home_id=home01'` shows `compaction_ok: true` (or `null`).

## B5. Server and app

- [ ] `http://localhost:8000/docs` loads.
- [ ] Without `--enable-simulator`, `/api/v1/simulate/floor` returns 404 and the app has no simulator button.
- [ ] **The app builds on your machine.** Run `flutter analyze` (no errors) and `flutter test` (all pass) in `apps/mobile`. These Dart changes were never compiled locally; CI is their only check so far.
- [ ] The app on the phone answers a query from the running server (`LOCATED` card with the server's sentence).
- [ ] Stopping the server and querying again shows *"Can't reach Aegis memory…"*, and no location appears.
- [ ] **The GitHub Actions run for `feat/memory-plan` is green** (Python and Flutter jobs). The Python job now fails below 75% coverage.

## B6. Live capture

- [ ] `aegis-ingest` receives frames from IP Webcam: the console counts frames, and `captures/walk01/` fills with `frame_*.jpg`.
- [ ] `touch captures/.pause` pauses capture and `rm` resumes it. `session.json` lists the pause.
- [ ] Turning phone Wi-Fi off for about 10 s and back on resumes the stream, and a `disconnect` gap is recorded.
- [ ] `--stage live` processes segments `walk01_seg0001`, `_seg0002`, … and ingests each one. `captures/walk01/pipeline_state.json` lists them.
- [ ] Interrupting with `Ctrl+C` and re-running the same command continues from the next segment instead of starting again.
- [ ] With `AEGIS_CAPTURE_DIR` and `AEGIS_CAPTURE_PAUSE_FILE` set, the app's Recording switch pauses and resumes the capture.

## B7. Decisions and limits to keep in mind

- [ ] **Evidence crops** are kept past the 24-hour raw-frame rule by default. Confirm this with your supervisor (decision #9), or set `memory.evidence.enabled: false`.
- [ ] **The 120-keyframe segment size is a guess.** Run `uv run modal run scripts/measure_vggt_window.py --dataset-id <a long dataset>` and set `vggt.max_keyframes` and `live.segment_frames` from its `recommended_max_keyframes`.
- [ ] **The storage-growth figures in `context/todo.md` come from a synthetic stream.** Replace them with real measurements before they go into the report.
- [ ] **The capture-control and rename endpoints have no authentication yet** (Milestone 4). Do not expose the server outside your own network.
- [ ] **Teammates who pulled `develop` before 15 November** need `git fetch origin && git reset --hard origin/develop`, because `develop` history was rewritten to remove a co-author line.
