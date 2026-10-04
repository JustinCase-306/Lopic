"""Lopic app host: webview2 window + the python<->js bridge."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import webview

from .catalog import CATALOG, by_id
from .install import Installer
from .settings import load_config, save_config
from .system import system_report

UI_DIR = Path(__file__).resolve().parent.parent / "ui"


class LopicApi:
    """everything the html may call. keep return values json-friendly."""

    def __init__(self) -> None:
        self.cfg = load_config()
        self.sys = system_report()
        self.selected: str | None = None
        self.window = None
        self.root = Path(self.cfg["install_root"])
        self.installer = Installer(self.root, self._emit_log, self._emit_gen)

    # ---------- pushes from python into the ui ----------

    def _push(self, js: str, *args) -> None:
        if self.window is None:
            return
        try:
            self.window.evaluate_js(js, *args)
        except Exception:  # noqa: BLE001 - the window may be closing
            pass

    def _emit_log(self, line: str) -> None:
        self._push("window.onPy && window.onPy.log(arguments[0])", line)

    def _emit_gen(self, state: dict) -> None:
        self._push("window.onPy && window.onPy.genState(arguments[0])", state)

    def _emit_state(self) -> None:
        self._push(
            "window.onPy && window.onPy.state(arguments[0])",
            {"sys": self.sys, "gens": self.gens_payload(), "jobs": self.jobs_payload()},
        )

    # ---------- data for the ui ----------

    def gens_payload(self) -> list[dict]:
        installed = self._installed_map()
        out = []
        for gen in CATALOG:
            row = {k: v for k, v in gen.items() if k != "torch_index"}
            row["installed"] = installed.get(gen["id"], False)
            out.append(row)
        return out

    def jobs_payload(self) -> dict:
        return {
            jid: {
                "id": j.id,
                "status": j.status,
                "progress": job.progress,
                "installed": job.installed,
                "message": job.message,
            }
            for jid, job in self.installer.jobs.items()
        }

    def _installed_map(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for gen in CATALOG:
            venv = self.root / gen["folder"] / "venv"
            ok = (venv / "Scripts" / "python.exe").exists()
            if ok and gen.get("package_install"):
                ok = (venv / "Scripts" / f"{gen['package_install']}-web.exe").exists()
            result[gen["id"]] = ok
        return result

    # ---------- api surface used by the ui ----------

    def bootstrap(self) -> dict:
        return {
            "sys": self.sys,
            "gens": self.gens_payload(),
            "jobs": self.jobs_payload(),
        }

    def on_select(self, gen_id: str) -> None:
        self.selected = gen_id

    def install(self, gen_id: str) -> dict:
        gen = by_id(gen_id)
        if gen is None:
            return {"ok": False, "error": "unbekannter generator"}
        self.installer.start(gen)
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


def _kick_frontend(window, tries: int = 40) -> None:
    """start the frontend from python.

    pywebview 6 injects api.js on `before_load`, so the DOM `pywebviewready`
    event fires BEFORE any inline script can register a listener for it.
    kicking from python avoids that race entirely.

    the `loaded` event is not a reliable "the dom is ready" signal here, and a
    single evaluate_js can land while the document is still parsing, so kick
    repeatedly until the frontend reports that it is running.
    """
    def kick(left: int) -> None:
        try:
            already = window.evaluate_js("window.__lopicBooted === true")
        except Exception:  # noqa: BLE001
            already = False
        if already:
            return
        try:
            window.evaluate_js(
                "if (typeof window.lopicBoot === 'function') {"
                "  window.__lopicBooted = true;"
                "  window.lopicBoot();"
                "}")
        except Exception:  # noqa: BLE001
            pass
        if left > 1:
            threading.Timer(0.15, kick, args=(left - 1,)).start()

    threading.Timer(0.2, kick, args=(tries,)).start()


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
    win.events.loaded += lambda: _kick_frontend(win)

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