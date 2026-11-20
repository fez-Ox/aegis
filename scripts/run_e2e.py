#!/usr/bin/env python3
"""Run the whole Aegis pipeline end to end, waiting for you at human steps.

What it automates
-----------------
setup -> Modal auth/secret -> IP Webcam capture -> Modal pipeline -> deploy
the memory + ask API -> ask from the terminal -> (optionally) run the app.

Some steps cannot be automated. When the script reaches one it prints exactly
what to do, then blocks until you press Enter (or types ``s`` to skip an
optional step). It never pretends a skipped step succeeded.

Usage
-----
    uv run python scripts/run_e2e.py                     # full live run
    uv run python scripts/run_e2e.py --cpu               # no GPU billing
    uv run python scripts/run_e2e.py --skip-capture --dataset-id walk01
    uv run python scripts/run_e2e.py --video put_shoes --dataset-id shoes01
    uv run python scripts/run_e2e.py --dry-run           # print, change nothing

Every phase is checkpointed in ``.aegis/e2e_state.json`` so a rerun can resume.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".aegis"
STATE_FILE = STATE_DIR / "e2e_state.json"

DEFAULT_QUESTIONS = ("where are my keys",)
DEFAULT_STREAM_URL = "http://192.168.1.23:8080/video"
MIRROR_VGGT = "wincentIsMe/VGGT-Omega"  # public mirror of the gated checkpoint
SECRET_NAME = "aegis-secrets"
SERVE_APP = "aegis-memory-api"

_USE_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None


class Runner:
    """Small state machine: each phase records its result for a resume."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.state: dict[str, Any] = self._load_state()
        self.uv = self._find_uv()
        self.env = dict(os.environ)
        self.env.setdefault("PATH", os.environ.get("PATH", ""))
        self._load_dotenv()
        self.phase_no = 0
        self.phase_total = 8 if args.app else 7

    # -- state -------------------------------------------------------------
    @staticmethod
    def _load_state() -> dict[str, Any]:
        if STATE_FILE.is_file():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def save_state(self) -> None:
        if self.args.dry_run:
            return
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8"
        )

    @staticmethod
    def _find_uv() -> str:
        found = shutil.which("uv")
        if found:
            return found
        fallback = Path.home() / ".venvs" / "tools" / "bin" / "uv"
        return str(fallback) if fallback.is_file() else "uv"

    def _load_dotenv(self) -> None:
        """Read .env without requiring python-dotenv to be installed."""
        path = REPO_ROOT / ".env"
        if not path.is_file():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                self.env[key] = value

    # -- output ------------------------------------------------------------
    @staticmethod
    def _paint(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

    def header(self, title: str) -> None:
        self.phase_no += 1
        line = "=" * 78
        print(f"\n{self._paint(line, '36')}")
        print(self._paint(f"  [{self.phase_no}/{self.phase_total}] {title}", "1;36"))
        print(self._paint(line, "36"), flush=True)

    def info(self, message: str) -> None:
        print(f"  {message}", flush=True)

    def ok(self, message: str) -> None:
        print(f"  {self._paint('OK', '32')}   {message}", flush=True)

    def warn(self, message: str) -> None:
        print(f"  {self._paint('WARN', '33')} {message}", flush=True)

    def fail(self, message: str) -> None:
        print(f"  {self._paint('FAIL', '31')} {message}", file=sys.stderr, flush=True)

    def note(self, message: str) -> None:
        print(f"  {self._paint('..', '90')}   {message}", flush=True)

    # -- human interaction -------------------------------------------------
    def pause(
        self,
        title: str,
        instructions: Sequence[str],
        *,
        check: Callable[[], bool] | None = None,
        can_skip: bool = False,
        done_hint: str = "Press Enter when done",
    ) -> bool:
        """Show what a human must do, then block until it is actually done."""
        while True:
            print(f"\n  {self._paint('ACTION NEEDED — ' + title, '1;33')}")
            for line in instructions:
                print(f"    {line}")
            if self.args.dry_run:
                self.note("dry run: not waiting for you here")
                return True
            if can_skip:
                answer = input(f"  {done_hint}, or 's' to skip: ").strip().lower()
                if answer == "s":
                    self.warn(f"skipped: {title}")
                    return False
            else:
                input(f"  {done_hint}: ")
            if check is None:
                self.ok(f"recorded: {title}")
                return True
            if check():
                self.ok(f"verified: {title}")
                return True
            self.fail("that check still fails; the instructions are above.")

    def ask_text(self, question: str, default: str | None = None) -> str:
        if self.args.dry_run:
            return default or ""
        prompt = f"  {question}"
        if default:
            prompt += f" [{default}]"
        answer = input(prompt + ": ").strip()
        return answer or (default or "")

    def confirm(self, question: str, *, assume_yes: bool = False) -> bool:
        if self.args.dry_run or assume_yes or self.args.yes:
            return True
        return input(f"  {question} [Y/n]: ").strip().lower() in {"", "y", "yes"}

    # -- commands ----------------------------------------------------------
    def uv_cmd(self, *args: str) -> list[str]:
        return [self.uv, *args]

    def _print_cmd(self, cmd: Sequence[str]) -> None:
        shown = shlex.join(self._redact(part) for part in cmd)
        self.note(f"$ {shown}")

    @staticmethod
    def _redact(text: str) -> str:
        return re.sub(r"(HF_TOKEN=)\S+", r"\1<redacted>", text)

    def run(
        self,
        cmd: Sequence[str],
        *,
        env: dict[str, str] | None = None,
        capture: bool = False,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self._print_cmd(cmd)
        if self.args.dry_run:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.run(
            list(cmd),
            cwd=cwd or REPO_ROOT,
            env=env or self.env,
            text=True,
            capture_output=capture,
            check=False,
        )

    def stream(
        self,
        cmd: Sequence[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> tuple[int, str]:
        """Run in the foreground, echo output live, and keep the tail."""
        self._print_cmd(cmd)
        if self.args.dry_run:
            return 0, ""
        tail: list[str] = []
        process = subprocess.Popen(
            list(cmd),
            cwd=cwd or REPO_ROOT,
            env=env or self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                tail.append(line.rstrip("\n"))
                if len(tail) > 200:
                    tail.pop(0)
                print(f"    {line.rstrip()}", flush=True)
            code = process.wait()
        except KeyboardInterrupt:
            process.send_signal(signal.SIGINT)
            try:
                code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                code = 130
        return code, "\n".join(tail)

    # -- checks ------------------------------------------------------------
    def modal_authed(self) -> bool:
        result = self.run(
            self.uv_cmd("run", "modal", "profile", "current"), capture=True
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def hf_token(self) -> str | None:
        token = os.getenv("HF_TOKEN") or self.env.get("HF_TOKEN")
        return token.strip() if token else None

    def path(self, *parts: str) -> Path:
        return REPO_ROOT.joinpath(*parts)


def normalise_stream_url(raw: str) -> str:
    """Accept ``192.168.1.23:8080`` and turn it into the actual MJPEG endpoint."""
    url = raw.strip()
    if not url:
        return url
    if "://" not in url:
        url = f"http://{url}"
    parts = urllib.parse.urlsplit(url)
    path = parts.path.rstrip("/")
    if not path:
        path = "/video"
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def probe_stream(url: str, timeout: float = 6.0) -> tuple[bool, str]:
    """Return (reachable video stream, human-readable reason)."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "aegis-e2e"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            body = response.read(64)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, f"cannot reach it ({exc})"
    if not body:
        return False, "the server answered with an empty body"
    if content_type.startswith("text/") or "html" in content_type:
        return (
            False,
            (
                "that is the IP Webcam web page, not the stream "
                f"(Content-Type: {content_type or 'unknown'}); use .../video"
            ),
        )
    return True, content_type or "unknown content type"


def probe_health(base_url: str, dataset_id: str) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}/api/v1/health?dataset_id={dataset_id}"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Phase 1 — preflight
# ---------------------------------------------------------------------------
def phase_preflight(r: Runner) -> None:
    r.header("Preflight: repo, uv, project environment")

    required = [
        "run_pipeline.py",
        "run_server.py",
        "src/aegis/remote/serve.py",
        "src/aegis/nlq/cli.py",
        "config/live.yaml",
    ]
    missing = [name for name in required if not r.path(name).exists()]
    if missing:
        r.fail(f"Not an Aegis checkout? Missing: {', '.join(missing)}")
        raise SystemExit(2)
    r.ok(f"repo root: {REPO_ROOT}")

    if not (Path(r.uv).is_file() or shutil.which(r.uv)):
        r.pause(
            "Install uv",
            [
                "uv was not found on PATH.",
                "Install it with:  curl -LsSf https://astral.sh/uv/install.sh | sh",
                "or point at your uv binary with PATH=$HOME/.venvs/tools/bin:$PATH",
            ],
            check=lambda: bool(shutil.which("uv") or Path(r.uv).is_file()),
        )
    r.ok(f"uv: {r.uv}")

    code, _ = r.stream(r.uv_cmd("sync", "--dev"))
    if code != 0:
        r.fail("`uv sync --dev` failed; fix the environment above and rerun.")
        raise SystemExit(2)
    r.ok("project environment ready")


# ---------------------------------------------------------------------------
# Phase 2 — Modal account, secret, checkpoint choice
# ---------------------------------------------------------------------------
def phase_modal(r: Runner) -> None:
    r.header("Modal account, secret and VGGT checkpoint")

    if not r.modal_authed():
        if r.confirm("No Modal login found. Run `uv run modal setup` now?"):
            r.stream(r.uv_cmd("run", "modal", "setup"))
        if not r.modal_authed():
            r.pause(
                "Sign in to Modal",
                [
                    "Run:  uv run modal setup",
                    "Finish the browser sign-in, then come back here.",
                ],
                check=r.modal_authed,
            )
    if r.args.dry_run:
        r.note("dry run: assuming Modal is authenticated")
    else:
        r.ok("Modal authenticated")

    token = r.hf_token()
    if not token:
        r.warn("No HF_TOKEN in the environment or .env")
        r.pause(
            "Hugging Face token (optional)",
            [
                "facebook/VGGT-Omega is a gated repo and needs a token.",
                "Either add HF_TOKEN=hf_... to .env (it is gitignored) and press",
                "Enter, or type 's' to use the public mirror:",
                f"  {MIRROR_VGGT} (FAIR Noncommercial Research License).",
            ],
            check=lambda: r.hf_token() is not None,
            can_skip=True,
            done_hint="Press Enter after editing .env",
        )
        token = r.hf_token()

    if token:
        r.note("uploading HF_TOKEN into the Modal secret aegis-secrets")
        code, _ = r.stream(
            r.uv_cmd(
                "run",
                "modal",
                "secret",
                "create",
                SECRET_NAME,
                f"HF_TOKEN={token}",
                "--force",
            )
        )
        if code != 0:
            r.warn("Could not publish the secret; the gated model may not download.")
        else:
            r.ok(f"secret {SECRET_NAME} is present")

    model = r.args.vggt_model or (None if token else MIRROR_VGGT)
    r.state["vggt_model"] = model
    r.state["gpu"] = "cpu" if r.args.cpu else "gpu"
    r.save_state()
    r.ok(f"VGGT checkpoint: {model or 'facebook/VGGT-Omega (from config)'}")
    r.ok(
        "compute: "
        + ("CPU (AEGIS_GPU=cpu)" if r.args.cpu else "GPU (L4, Modal default)")
    )


# ---------------------------------------------------------------------------
# Phase 3 — capture
# ---------------------------------------------------------------------------
def choose_capture_target(r: Runner, base: str) -> tuple[str, str]:
    """Return ``(session_id, mode)`` with mode in new/resume/reuse.

    Existing captures are never overwritten.
    """
    if r.args.resume_capture:
        return base, "resume"
    session_dir = r.path("captures", base)
    if not session_dir.exists():
        return base, "new"
    if session_dir.is_dir() and not any(session_dir.iterdir()):
        session_dir.rmdir()
        r.note(f"removed empty leftover session {session_dir}")
        return base, "new"

    frames = 0
    index = session_dir / "index.jsonl"
    if index.is_file():
        frames = sum(1 for line in index.read_text().splitlines() if line.strip())
    r.warn(f"session {base!r} already exists ({frames} frames)")

    if r.args.dry_run:
        return base, "reuse"
    while True:
        answer = (
            input(
                f"  [e] use existing {base} (default)   [n] new session   "
                "[r] resume capture   [a] abort: "
            )
            .strip()
            .lower()
        )
        if answer in {"", "e"}:
            return base, "reuse"
        if answer == "n":
            suffix = 2
            while r.path("captures", f"{base}-{suffix}").exists():
                suffix += 1
            return f"{base}-{suffix}", "new"
        if answer == "r":
            return base, "resume"
        if answer == "a":
            raise SystemExit(0)
        r.warn("type e, n, r or a")


def dataset_for_session(r: Runner, session_id: str) -> str:
    """Keep an explicit dataset id stable across a resumed run."""
    if r.args.dataset_id:
        return r.args.dataset_id
    if r.state.get("session_id") == session_id and r.state.get("dataset_id"):
        return str(r.state["dataset_id"])
    return session_id


def phase_capture(r: Runner) -> None:
    r.header("Capture video")

    if r.args.video:
        r.info(f"batch input: {r.args.video} (skipping live capture)")
        r.state["input"] = "video"
        r.state["dataset_id"] = r.args.dataset_id or "demo01"
        r.save_state()
        return

    base_session = r.args.session_id or r.state.get("session_id") or "walk01"

    if r.args.skip_capture:
        session_id = base_session
        session_dir = r.path("captures", session_id)
        r.state["session_id"] = session_id
        r.state["dataset_id"] = dataset_for_session(r, session_id)
        r.save_state()
        index = session_dir / "index.jsonl"
        if not index.is_file() and not r.args.dry_run:
            r.fail(f"--skip-capture was set but {index} does not exist.")
            raise SystemExit(2)
        r.ok(f"using existing capture {session_dir}")
        return

    session_id, mode = choose_capture_target(r, base_session)
    session_dir = r.path("captures", session_id)
    if mode == "resume" and not session_dir.is_dir():
        r.fail(f"--resume-capture was set but captures/{session_id} does not exist.")
        raise SystemExit(2)
    r.state["session_id"] = session_id
    r.state["dataset_id"] = dataset_for_session(r, session_id)
    r.save_state()
    r.info(f"session: {session_id}" + (f" ({mode})" if mode != "new" else ""))
    r.info(f"dataset: {r.state['dataset_id']}")

    if mode == "reuse":
        index = session_dir / "index.jsonl"
        if not index.is_file():
            r.fail(f"{session_dir} has no index.jsonl; pick a new session.")
            raise SystemExit(2)
        r.ok(f"using existing capture {session_dir}")
        return

    resume = mode == "resume"

    raw_url = r.args.stream_url or r.env.get("AEGIS_STREAM_URL", "")
    if not raw_url and not r.args.dry_run:
        r.info("IP Webcam must be running on the phone (same Wi-Fi as this laptop).")
        raw_url = r.ask_text(
            "Paste the IP Webcam URL (…:8080 or …:8080/video)",
            default="192.168.1.23:8080",
        )
    url = normalise_stream_url(raw_url or DEFAULT_STREAM_URL)
    if raw_url and url != raw_url.strip():
        r.note(f"using {url}")

    while not r.args.dry_run:
        ok, detail = probe_stream(url)
        if ok:
            r.ok(f"stream reachable ({detail})")
            break
        r.fail(f"no video stream at {url}: {detail}")
        r.info("On the phone: open IP Webcam, tap 'Start server', read the URL.")
        r.info("Check the phone and laptop share a network and the IP is current.")
        new_raw = r.ask_text("IP Webcam URL (Enter to retry)", default=url)
        if new_raw:
            url = normalise_stream_url(new_raw)
    r.state["stream_url"] = url
    if r.args.dry_run:
        r.ok(f"stream would be checked at {url}")

    cmd = r.uv_cmd(
        "run",
        "aegis-ingest",
        "--url",
        url,
        "--output-root",
        "captures",
        "--session-id",
        session_id,
        "--config-path",
        "config/live.yaml",
        "--pause-file",
        "captures/.pause",
    )
    if resume:
        cmd.append("--resume")
    if r.args.capture_seconds:
        cmd.extend(["--max-duration", str(r.args.capture_seconds)])
        r.info(f"capturing for ~{r.args.capture_seconds:g}s")
    else:
        r.info("capturing until you press Ctrl+C (the script then continues)")

    code, _ = r.stream(cmd)
    if code not in (0, 130):
        r.fail(f"aegis-ingest exited with {code}.")
        r.info(
            "If the session was already recorded, rerun with --resume-capture "
            "or choose a new session id."
        )
        raise SystemExit(code)

    index = session_dir / "index.jsonl"
    if not r.args.dry_run and (not index.is_file() or index.stat().st_size == 0):
        r.fail(f"capture produced no frames at {index}.")
        raise SystemExit(2)
    r.ok(f"capture saved: {session_dir}")
    r.state["capture_done"] = True
    r.save_state()


# ---------------------------------------------------------------------------
# Phase 4 — Modal pipeline
# ---------------------------------------------------------------------------
CPU_FAILURE_HINTS = (
    "billing",
    "payment",
    "quota",
    "insufficient",
    "no gpu",
    "not entitled",
    "credit",
)


def phase_pipeline(r: Runner) -> None:
    r.header("Run the Modal pipeline")

    if r.args.skip_pipeline:
        r.warn("skipped (--skip-pipeline)")
        return

    dataset_id = r.state.get("dataset_id") or r.args.dataset_id or "demo01"
    is_live = r.state.get("input") != "video"
    stage = r.args.stage or ("live" if is_live else "all")
    config_path = r.args.config_path or (
        "config/live.yaml" if is_live else "config/demo.yaml"
    )

    cmd = r.uv_cmd(
        "run",
        "python",
        "run_pipeline.py",
        "--dataset-id",
        dataset_id,
        "--config-path",
        config_path,
        "--stage",
        stage,
    )
    if is_live:
        cmd.extend(
            ["--live-session", f"captures/{r.state.get('session_id', dataset_id)}"]
        )
    else:
        cmd.extend(["--video", str(r.args.video)])
    if r.state.get("vggt_model"):
        cmd.extend(["--vggt-model", str(r.state["vggt_model"])])
    if r.args.segment_frames is not None:
        cmd.extend(["--segment-frames", str(r.args.segment_frames)])
    if r.args.rerun:
        cmd.append("--rerun")
    if r.args.download:
        cmd.append("--download")
    if r.args.follow:
        cmd.append("--follow")

    env = dict(r.env)
    env["AEGIS_GPU"] = "cpu" if r.args.cpu else "L4"

    compute = "CPU (slow, cheap)" if r.args.cpu else "L4 GPU"
    if not r.confirm(
        f"Run stage '{stage}' for {dataset_id!r} on {compute}? "
        "This spends Modal compute."
    ):
        r.warn("pipeline cancelled; nothing ran")
        raise SystemExit(0)

    code, tail = r.stream(cmd, env=env)

    if code != 0 and not r.args.cpu:
        lowered = tail.lower()
        looks_like_capacity = any(hint in lowered for hint in CPU_FAILURE_HINTS)
        if looks_like_capacity or r.args.yes:
            reason = (
                "Modal rejected the GPU (billing/capacity)."
                if looks_like_capacity
                else "The GPU run failed."
            )
            r.warn(reason)
            r.info("GPU billing cannot be fixed by this script; CPU mode can run now.")
            if r.confirm("Retry the same stage on CPU now?"):
                env["AEGIS_GPU"] = "cpu"
                code, tail = r.stream(cmd, env=env)

    if code != 0:
        r.fail(f"pipeline failed with exit code {code}.")
        if r.args.cpu:
            r.info("CPU mode is slow but honest; check the log above for the cause.")
        raise SystemExit(code)

    r.ok(f"pipeline finished for {dataset_id}")
    r.state["pipeline_done"] = True
    r.save_state()


# ---------------------------------------------------------------------------
# Phase 5 — deploy the memory + ask API
# ---------------------------------------------------------------------------
MODAL_URL = re.compile(r"(https://[A-Za-z0-9._-]+\.modal\.run)")


def phase_deploy(r: Runner) -> None:
    r.header("Deploy the memory + ask API")

    if r.args.skip_deploy or r.args.skip_pipeline:
        r.warn("skipped (--skip-deploy)")
        return

    dataset_id = r.state.get("dataset_id") or r.args.dataset_id or "demo01"
    env = dict(r.env)
    env["AEGIS_DATASET_ID"] = dataset_id
    r.info(f"AEGIS_DATASET_ID={dataset_id}")
    code, output = r.stream(
        r.uv_cmd("run", "modal", "deploy", "src/aegis/remote/serve.py"), env=env
    )
    if code != 0:
        r.fail("deployment failed; see the log above.")
        raise SystemExit(code)

    matches = MODAL_URL.findall(output)
    url = matches[-1] if matches else ""
    if not url and r.args.dry_run:
        url = "https://example--aegis-memory-api-serve-memory-api.modal.run"
    if not url:
        url = r.ask_text("Deployment URL printed above (paste it)")
    if not url.startswith("http"):
        r.fail("No deployment URL. Rerun deploy and copy the URL it prints.")
        raise SystemExit(2)
    r.state["base_url"] = url
    r.save_state()
    r.ok(f"API: {url}")


# ---------------------------------------------------------------------------
# Phase 6 — health check and terminal ask
# ---------------------------------------------------------------------------
def phase_ask(r: Runner) -> None:
    r.header("Ask Aegis memory")

    base_url = r.args.base_url or r.state.get("base_url")
    dataset_id = r.args.dataset_id or r.state.get("dataset_id") or "demo01"
    if not base_url:
        r.fail("No base URL: deploy first, or pass --base-url.")
        raise SystemExit(2)

    health = None
    for attempt in range(1, 13):
        if r.args.dry_run:
            break
        health = probe_health(base_url, dataset_id)
        if health and health.get("scene_graph_ready"):
            break
        r.note(f"waiting for memory to answer ({attempt}/12, cold start is normal)")
        time.sleep(5)

    if not r.args.dry_run and not (health and health.get("scene_graph_ready")):
        r.pause(
            "The API is up but this dataset has no memory yet",
            [
                f"URL: {base_url}",
                f"dataset_id: {dataset_id}",
                "Confirm the pipeline wrote objects/r4d_scene_graph.json for it:",
                f"  uv run modal volume ls aegis-poc-data {dataset_id}/outputs/objects",
            ],
            check=lambda: bool(
                (probe_health(base_url, dataset_id) or {}).get("scene_graph_ready")
            ),
            can_skip=True,
        )
    elif health:
        r.ok(
            "memory ready: "
            f"{health.get('num_anchors', 0)} anchors, "
            f"{health.get('num_rooms', 0)} rooms"
        )

    r.state["base_url"] = base_url
    r.save_state()

    questions = r.args.question or list(DEFAULT_QUESTIONS)
    for question in questions:
        r.info(f"Q: {question}")
        code, _ = r.stream(
            r.uv_cmd(
                "run",
                "aegis-ask",
                question,
                "--dataset-id",
                dataset_id,
                "--transport",
                "http",
                "--base-url",
                base_url,
            )
        )
        if code != 0:
            r.warn("ask failed; the app would show the same error.")


# ---------------------------------------------------------------------------
# Phase 7 — optional app
# ---------------------------------------------------------------------------
def phase_app(r: Runner) -> None:
    if not r.args.app:
        return
    r.header("Run the Flutter app")

    flutter = shutil.which("flutter")
    if not flutter:
        proceeded = r.pause(
            "Install Flutter or connect your phone",
            [
                "Flutter was not found on PATH.",
                "Install it from https://docs.flutter.dev/get-started/install",
                "Then connect the phone over USB and run `adb devices`.",
                "The app talks to the deployed API; capture stays on the laptop.",
            ],
            check=lambda: shutil.which("flutter") is not None,
            can_skip=True,
        )
        if not proceeded:
            r.warn("skipped the app; the terminal client already proved the API.")
            return
        flutter = shutil.which("flutter") or "flutter"

    mobile = r.path("apps", "mobile")
    base_url = r.state.get("base_url", "")
    r.stream([flutter, "pub", "get"], cwd=mobile)
    r.info("launching the app; press q or Ctrl+C to return here")
    r.stream(
        [
            flutter,
            "run",
            f"--dart-define=AEGIS_BASE_URL={base_url}",
        ],
        cwd=mobile,
    )
    r.ok("app session ended")
    r.info(f"APK later:  flutter build apk --dart-define=AEGIS_BASE_URL={base_url}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def phase_summary(r: Runner) -> None:
    r.header("Done")
    dataset_id = r.state.get("dataset_id", r.args.dataset_id or "demo01")
    base_url = r.state.get("base_url", "")
    print(
        f"""
  dataset_id : {dataset_id}
  session    : {r.state.get("session_id", "-")}
  API        : {base_url or "(not deployed)"}

  Ask again any time:
    uv run aegis-ask "where are my shoes" --dataset-id {dataset_id} \\
        --transport http --base-url {base_url or "<modal-url>"}

  Re-run only the asking part:
    uv run python scripts/run_e2e.py --skip-capture --skip-pipeline \\
        --dataset-id {dataset_id} --base-url {base_url or "<modal-url>"}

  Stop the deployed API when finished (it is unauthenticated):
    uv run modal app stop {SERVE_APP}

  State file: {STATE_FILE.relative_to(REPO_ROOT)}
  Architecture: CONTEXT.md    Remaining work: TODO.md
"""
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_e2e.py",
        description="Run the full Aegis pipeline, waiting at human-only steps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dataset-id", help="Dataset id (default: session id)")
    parser.add_argument(
        "--session-id",
        default=None,
        help="Live capture session (default: last used, else walk01)",
    )
    parser.add_argument("--stream-url", help="IP Webcam /video URL")
    parser.add_argument("--video", help="Batch video path or preset; skips capture")
    parser.add_argument(
        "--capture-seconds",
        type=float,
        help="Bound capture length; default: record until Ctrl+C",
    )
    parser.add_argument(
        "--skip-capture", action="store_true", help="Use captures/<session-id>"
    )
    parser.add_argument(
        "--resume-capture",
        action="store_true",
        help="Append to an interrupted captures/<session-id>",
    )
    parser.add_argument("--skip-pipeline", action="store_true", help="Do not run Modal")
    parser.add_argument(
        "--skip-deploy", action="store_true", help="Keep the current deployment"
    )
    parser.add_argument("--base-url", help="Use an already deployed API")
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Set AEGIS_GPU=cpu (no GPU billing required)",
    )
    parser.add_argument(
        "--vggt-model",
        help=f"VGGT checkpoint (default: {MIRROR_VGGT} without HF_TOKEN)",
    )
    parser.add_argument("--segment-frames", type=int, help="Frames per live segment")
    parser.add_argument("--config-path", help="Runtime YAML override")
    parser.add_argument("--stage", help="Pipeline stage override (default: live/all)")
    parser.add_argument("--rerun", action="store_true", help="Also build Rerun files")
    parser.add_argument(
        "--download", action="store_true", help="Download artifacts for local Rerun"
    )
    parser.add_argument("--follow", action="store_true", help="Process while capturing")
    parser.add_argument(
        "--question",
        action="append",
        help="Question for aegis-ask (repeatable; default: where are my keys)",
    )
    parser.add_argument(
        "--app", action="store_true", help="Also launch the Flutter app"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without running them"
    )
    parser.add_argument(
        "--yes", action="store_true", help="Answer yes to optional confirmations"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runner = Runner(args)
    try:
        phase_preflight(runner)
        phase_modal(runner)
        phase_capture(runner)
        phase_pipeline(runner)
        phase_deploy(runner)
        phase_ask(runner)
        phase_app(runner)
        phase_summary(runner)
    except KeyboardInterrupt:
        print("\n  Interrupted. Rerun the same command to resume.", file=sys.stderr)
        return 130
    except EOFError:
        print(
            "\n  No terminal input, but this step needs a human.\n"
            "  Run the script from an interactive terminal (not piped/CI).",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
