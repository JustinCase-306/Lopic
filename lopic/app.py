"""Lopic app host: webview2 window + the python<->js bridge."""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
from pathlib import Path

import webview

from .catalog import CATALOG, PY_PIN_NOTE, by_id
from .models import MODELS, by_id as model_by_id, license_text
from .fetch import ModelFetcher
from .install import Installer
from .settings import load_config, save_config
from .system import system_report

UI_DIR = Path(__file__).resolve().parent.parent / "ui"


def _js(value) -> str:
    """json is valid javascript, so this is the safe way to inline a payload.

    window.evaluate_js has no argument passing (see LopicApi._push).
    """
    return json.dumps(value)


class LopicApi:
    """everything the html may call. keep return values json-friendly."""

    def __init__(self) -> None:
        self.cfg = load_config()
        self.sys = system_report()
        self.selected: str | None = None
        self.selected_model: str | None = None
        self.window = None
        self.root = Path(self.cfg["install_root"])
        self.installer = Installer(self.root, self._emit_log, self._emit_gen)
        self.fetcher = ModelFetcher(self.root, self._emit_log, self._emit_model)
        self._push_queue: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._drain_push, daemon=True,
                         name="lopic-push").start()

    # ---------- pushes from python into the ui ----------

    def _push(self, script: str) -> None:
        """hand one script to the ui thread through a queue.

        two traps live here. first, window.evaluate_js takes (script, callback)
        and has no argument passing: handing the payload in as a second
        positional argument made pywebview treat it as a callback (a non-empty
        string is truthy), call it, raise, and the exception was swallowed --
        so every push to the ui vanished and the buttons did their work without
        reporting anything. the payload is inlined into the script instead.
        second, evaluate_js called synchronously from inside a js->python call
        blocks: the ui waits on the js that is waiting on python. queueing
        keeps every push off that thread and in order.
        """
        if self.window is None:
            return
        self._push_queue.put(script)

    def _drain_push(self) -> None:
        while True:
            script = self._push_queue.get()
            window = self.window
            if window is None:
                continue
            try:
                window.evaluate_js(script)
            except Exception:  # noqa: BLE001 - the window may be closing
                pass

    def _emit_log(self, line: str) -> None:
        self._push(f"window.onPy && window.onPy.log({_js(line)})")

    def _emit_gen(self, state: dict) -> None:
        self._push(f"window.onPy && window.onPy.genState({_js(state)})")

    def _emit_model(self, state: dict) -> None:
        self._push(f"window.onPy && window.onPy.modelState({_js(state)})")

    def _emit_state(self) -> None:
        payload = {"sys": self.sys, "gens": self.gens_payload(), "jobs": self.jobs_payload(),
                   "models": self.models_payload(), "modelJobs": self.model_jobs_payload()}
        self._push(f"window.onPy && window.onPy.state({_js(payload)})")

    # ---------- data for the ui ----------

    def gens_payload(self) -> list[dict]:
        installed = self._installed_map()
        out = []
        for gen in CATALOG:
            row = {k: v for k, v in gen.items() if k != "torch_index"}
            row["installed"] = installed.get(gen["id"], False)
            row["py_note"] = PY_PIN_NOTE.get(gen["python"], "")
            out.append(row)
        return out

    def jobs_payload(self) -> dict:
        return {
            jid: {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "installed": job.installed,
                "message": job.message,
            }
            for jid, job in self.installer.jobs.items()
        }

    def models_payload(self) -> list[dict]:
        installed = self.fetcher.installed_models()
        out = []
        for m in MODELS:
            row = dict(m)
            row["license_text"] = license_text(m["license"])
            row["installed"] = installed.get(m["id"], False)
            row["size_total"] = sum(f["size"] for f in m["files"])
            out.append(row)
        return out

    def model_jobs_payload(self) -> dict:
        return {
            mid: {"id": d.model_id, "status": d.status, "progress": d.progress,
                  "received": d.received, "total": d.total}
            for mid, d in self.fetcher.downloads.items()
        }

    def on_select_model(self, model_id: str) -> None:
        self.selected_model = model_id

    def download_model(self, model_id: str) -> dict:
        m = model_by_id(model_id)
        if m is None:
            return {"ok": False, "error": "unbekanntes Modell"}
        self.fetcher.start(m)
        return {"ok": True}

    def model_folder(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.root))
        return {"ok": True}

    def _installed_map(self) -> dict[str, bool]:
        """true only when the engine could actually start (see _engine_ready)."""
        return {gen["id"]: self._engine_ready(gen) for gen in CATALOG}

    def _engine_ready(self, gen: dict) -> bool:
        """the launcher's own requirements, checked on disk."""
        target = self.root / gen["folder"] / "venv"
        py = target / "Scripts" / "python.exe"
        if not py.is_file():
            return False
        package = gen.get("package_install")
        if package and not (target / "Scripts" / f"{package}-web.exe").is_file():
            return False
        entry = gen.get("entry")
        if entry and not (target.parent / entry).is_file():
            return False
        # the hand-cloned helper repos are on sys.path, not in site-packages:
        # without them the engine imports fine and dies at startup
        for spec in gen.get("extra_repos") or []:
            if not (target.parent / spec["folder"]).is_dir():
                return False
        # torch is what every one of these imports first; its absence is the
        # difference between "installed" and "half of phase 3"
        site = target / "Lib" / "site-packages"
        return any(site.glob("torch*")) if site.is_dir() else False

    # ---------- api surface used by the ui ----------

    def bootstrap(self) -> dict:
        return {
            "sys": self.sys,
            "gens": self.gens_payload(),
            "jobs": self.jobs_payload(),
            "models": self.models_payload(),
            "modelJobs": self.model_jobs_payload(),
        }

    def on_select(self, gen_id: str) -> None:
        self.selected = gen_id

    def install(self, gen_id: str) -> dict:
        gen = by_id(gen_id)
        if gen is None:
            return {"ok": False, "error": "unbekannter generator"}
        self.installer.start(gen)
        return {"ok": True}

    def reinstall(self, gen_id: str) -> dict:
        """rebuild a generator: fresh source tree, damaged packages repaired."""
        gen = by_id(gen_id)
        if gen is None:
            return {"ok": False, "error": "unbekannter generator"}
        self.installer.start(gen, force=True)
        return {"ok": True}

    def launch(self, gen_id: str) -> dict:
        gen = by_id(gen_id)
        if gen is None:
            return {"ok": False, "error": "unbekannter generator"}
        self.installer.launch(gen)
        return {"ok": True}

    def stop(self, gen_id: str) -> dict:
        self.installer.stop(gen_id)
        return {"ok": True}

    def uninstall(self, gen_id: str) -> dict:
        gen = by_id(gen_id)
        if gen is None:
            return {"ok": False, "error": "unbekannter generator"}
        self.installer.uninstall(gen, self._emit_state)
        return {"ok": True}

    def open_folder(self, gen_id: str) -> dict:
        gen = by_id(gen_id)
        if gen is None:
            return {"ok": False}
        path = self.root / gen["folder"]
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(path))
        return {"ok": True}

    def rescan(self) -> dict:
        self.sys = system_report()
        self._emit_state()
        return {"ok": True}


def run() -> int:
    cfg = load_config()
    win_cfg = cfg.get("window", {})
    index = UI_DIR / "index.html"
    if not index.exists():
        print(f"FEHLER UI fehlt: {index}", file=sys.stderr)
        return 1

    api = LopicApi()
    win = webview.create_window(
        "Lopic — lokale Bildgeneratoren",
        url=str(index),
        js_api=api,
        width=int(win_cfg.get("width", 1280)),
        height=int(win_cfg.get("height", 840)),
        min_size=(1040, 680),
        background_color="#070a13",
        text_select=True,
    )
    api.window = win
    # the frontend boots itself (see ui/app.js); only the push drain thread
    # touches the bridge from python

    def on_closing():
        api.installer.shutdown()
        try:
            cfg["window"] = {"width": win.width, "height": win.height}
            save_config(cfg)
        except Exception:  # noqa: BLE001
            pass

    win.events.closing += on_closing

    try:
        webview.start(debug=False)
    except Exception as exc:  # noqa: BLE001
        print(f"FEHLER beim Start des Fensters: {exc}", file=sys.stderr)
        return 1
    return 0