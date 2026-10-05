"""runs generator installs on a worker thread and streams progress + log lines.

every generator gets its own venv so they cannot break each other.
all child processes run windowless: no console popup, no focus steal.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# install phases, used for the progress fraction
TOTAL_PHASES = 6


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    installed: bool = False
    message: str = ""
    proc: subprocess.Popen | None = None
    lines: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class Installer:
    """one install at a time keeps the gpu and disk honest."""

    def __init__(self, root: Path, emit: Callable[[str], None],
                 emit_state: Callable[[dict], None]):
        self.root = Path(root)
        self.emit = emit
        self.emit_state = emit_state
        self.jobs: dict[str, Job] = {}
        self.current: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._launched: dict[str, subprocess.Popen] = {}

    # ---------- state plumbing ----------

    def _push(self, job: Job) -> None:
        self.emit_state({
            "id": job.id,
            "status": job.status,
            "progress": round(job.progress, 3),
            "installed": job.installed,
            "message": job.message,
        })

    def log(self, line: str) -> None:
        if self.current and self.current in self.jobs:
            job = self.jobs[self.current]
            with job.lock:
                job.lines.append(line)
        self.emit(line)

    def _phase(self, job: Job, done: int, total: int = TOTAL_PHASES) -> None:
        with job.lock:
            job.progress = min(0.99, done / total)
        self._push(job)

    # ---------- process helpers ----------

    @staticmethod
    def _run_env() -> dict[str, str]:
        """isolated env: never inherit lopic's own PYTHONPATH into the engine."""
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env.pop("PYTHONPATH", None)
        return env

    @staticmethod
    def _flags() -> int:
        """keep every child invisible: no console window, own process group."""
        flags = CREATE_NO_WINDOW
        if os.name == "nt":
            flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return flags

    def _run(self, job: Job, cmd: list[str], cwd: Path, label: str) -> bool:
        """run a command, streaming merged output. True on exit code 0."""
        self.log(f">>> {label}")
        run_env = self._run_env()
        flags = self._flags()

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=run_env,
                creationflags=flags,
                bufsize=1,
            )
        except OSError as exc:
            self.log(f"FEHLER Start fehlgeschlagen: {exc}")
            return False

        with job.lock:
            job.proc = proc

        if proc.stdout is not None:
            for line in proc.stdout:
                text = line.rstrip()
                if text:
                    self.log(text)
                if self._stop.is_set():
                    proc.terminate()
                    return False

        code = proc.wait()
        with job.lock:
            job.proc = None
        if code == 0:
            self.log(f"OK {label} fertig")
            return True
        self.log(f"FEHLER {label} endete mit Code {code}")
        return False

    @staticmethod
    def _python_of(venv_dir: Path) -> str | None:
        for rel in ("Scripts/python.exe", "bin/python"):
            cand = venv_dir / rel
            if cand.exists():
                return str(cand)
        return None

    # ---------- install ----------

    def start(self, gen: dict) -> None:
        with self._lock:
            if self.current is not None:
                self.emit("FEHLER Es laeuft bereits eine Installation. Bitte warte sie ab.")
                return
            self.current = gen["id"]

        job = Job(id=gen["id"], status="running")
        self.jobs[job.id] = job
        self._push(job)
        threading.Thread(target=self._install_worker, args=(gen, job),
                         daemon=True, name=f"lopic-install-{gen['id']}").start()

    def _install_worker(self, gen: dict, job: Job) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            target = self.root / gen["folder"]
            venv_dir = target / "venv"

            # -- phase 1: source --
            if (target / ".git").exists():
                self.log(f"OK Quelle von {gen['name']} ist schon da")
                if not self._run(job, ["git", "pull", "--ff-only"], target,
                                 f"{gen['name']}: git pull"):
                    self.log("HINWEIS Update fehlgeschlagen, vorhandene Version bleibt")
            else:
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
                if not self._run(job, ["git", "clone", "--depth", "1", gen["repo"], str(target)],
                                 self.root, f"{gen['name']}: git clone"):
                    raise RuntimeError("clone fehlgeschlagen")
            self._phase(job, 1)

            # -- phase 2: venv --
            # uv venv does NOT install pip unless --seed is passed, and the rest
            # of the install is pip-driven (`py -m pip ...`). Without pip every
            # generator fails at the "pip aktualisieren" step.
            py = self._python_of(venv_dir)
            if py is None:
                uv = shutil.which("uv")
                if uv:
                    self._run(job, [uv, "venv", "--seed", "--python", gen["python"], str(venv_dir)],
                              target, f"{gen['name']}: venv anlegen")
                else:
                    self._run(job, [sys.executable, "-m", "venv", str(venv_dir)],
                              target, f"{gen['name']}: venv anlegen")
                py = self._python_of(venv_dir)
                if py is None:
                    raise RuntimeError("venv konnte nicht angelegt werden")
            else:
                self.log(f"OK venv von {gen['name']} ist schon da")
            self._phase(job, 2)

            # -- phase 3: torch (before anything else pulls a cpu build) --
            self._run(job, [py, "-m", "pip", "install", "--upgrade", "pip", "wheel"],
                      target, f"{gen['name']}: pip aktualisieren")

            torch_idx = gen.get("torch_index")
            if torch_idx:
                self.log(f">>> torch fuer deine GPU (Index: {torch_idx}) — grosser Download")
                self._run(job, [py, "-m", "pip", "install", "torch", "torchvision",
                                "--index-url", torch_idx],
                          target, f"{gen['name']}: torch installieren")
            self._phase(job, 3)

            # -- phase 4: python deps --
            ok = self._install_deps(job, gen, target, py)
            if not ok:
                raise RuntimeError("Abhaengigkeiten nicht installierbar")
            self._phase(job, 4)

            # -- phase 5: helper repos the generator expects in repositories/ --
            self._phase(job, 5)
            if not self._install_extra_repos(job, gen, target):
                raise RuntimeError("Hilfs-Repos nicht installierbar")

            # -- phase 6: the venv has to import (see _verify_env) --
            self._phase(job, 6)
            if not self._verify_env(job, gen, target, py):
                raise RuntimeError("Installation liess sich nicht importieren")

            with job.lock:
                job.status = "done"
                job.installed = True
                job.progress = 1.0
                job.message = "installation abgeschlossen"
            self.log(f"OK {gen['name']} ist fertig installiert")
            self._push(job)

        except Exception as exc:  # noqa: BLE001
            with job.lock:
                job.status = "error"
                job.message = str(exc)
            self.log(f"FEHLER {gen['name']}: {exc}")
            self._push(job)
        finally:
            with self._lock:
                self.current = None

    def _verify_env(self, job: Job, gen: dict, target: Path, py: str) -> bool:
        """confirm the venv imports, and repair a broken dependency set.

        pip can end a run with a half-uninstalled package: forge pins
        numpy==1.26.2, torchvision pulls numpy 2.x first, and the downgrade
        leaves numpy unable to import. re-running the requirements install
        puts the pinned files back, so one retry repairs the environment.
        """
        probe = ("import numpy, torch; "
                 "print('torch', torch.__version__, '| cuda', torch.version.cuda, "
                 "'| gpu', torch.cuda.is_available())")
        for attempt in (1, 2):
            r = self._capture([py, "-c", probe], target, timeout=600)
            if r.returncode == 0:
                version = (r.stdout or "").strip().splitlines()[-1:]
                self.log(f">>> {gen['name']}: {version[0] if version else '?'}")
                if attempt == 2:
                    self.log(f"OK {gen['name']}: Umgebung repariert")
                return True
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
            self.log(f">>> {gen['name']}: Importpruefung fehlgeschlagen "
                     f"({'; '.join(tail)[:180]})")
            if attempt == 1:
                self.log(f">>> {gen['name']}: Abhaengigkeiten neu installieren")
                self._install_deps(job, gen, target, py)
        self.log(f"FEHLER {gen['name']}: Umgebung bleibt unbrauchbar")
        return False

    def _capture(self, cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
        """run a command and capture output instead of streaming it to the log."""
        try:
            return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                                  timeout=timeout, creationflags=self._flags(),
                                  env=self._run_env())
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, 1, "", "timeout")

    def _install_extra_repos(self, job: Job, gen: dict, target: Path) -> bool:
        """clone the helper repos a generator expects in repositories/.

        forge clones huggingface_guess and BLIP there on first start and adds
        the folder to sys.path itself (modules/paths.py), so they are not pip
        packages: huggingface_guess has no setup.py.
        """
        for spec in gen.get("extra_repos") or []:
            folder = target / spec["folder"]
            name = folder.name
            if folder.exists():
                self.log(f"OK {name} ist schon da")
                continue
            folder.parent.mkdir(parents=True, exist_ok=True)
            # full clone: --depth 1 cannot check out an arbitrary commit after
            self.log(f">>> {gen['name']}: {name} klonen")
            if not self._run(job, ["git", "clone", spec["repo"], str(folder)],
                             target, f"{gen['name']}: {name}"):
                return False
            if spec.get("commit") and not self._run(
                    job, ["git", "checkout", spec["commit"]], folder,
                    f"{gen['name']}: {name} auf Commit"):
                return False
        return True

    def _install_deps(self, job: Job, gen: dict, target: Path, py: str) -> bool:
        """install either a requirements file or a pip package.

        the two are mutually exclusive on purpose: InvokeAI ships no
        requirements.txt at the repo root, it is installed as a pip package.
        """
        req_name = gen.get("requirements") or ""
        package = gen.get("package_install") or ""

        if req_name:
            req = target / req_name
            if req.exists():
                return self._run(job, [py, "-m", "pip", "install", "-r", str(req)],
                                 target, f"{gen['name']}: Abhaengigkeiten")
            self.log(f"FEHLER {req_name} nicht gefunden im Repository")
            return False

        if package:
            self.log(f">>> installiere Pip-Paket '{package}'")
            return self._run(job, [py, "-m", "pip", "install", package],
                             target, f"{gen['name']}: Paket installieren")

        self.log("FEHLER fuer diesen Generator ist keine Installationsart hinterlegt")
        return False

    # ---------- launch / stop ----------

    def launch(self, gen: dict) -> None:
        target = self.root / gen["folder"]
        py = self._python_of(target / "venv")

        package = gen.get("package_install")
        if package:
            self.launch_console_script(gen, target, package)
            return

        entry = gen.get("entry") or ""
        if py is None or not (target / entry).exists():
            self.emit(f"FEHLER {gen['name']} ist nicht (vollstaendig) installiert.")
            return

        # bind localhost only. --listen without an argument would open all
        # interfaces, which we do not want for a local generator.
        cmd = [py, str(target / entry), "--port", str(gen["port"])]
        self._spawn(gen, cmd, target)
        self.emit(f"OK {gen['name']} startet auf http://127.0.0.1:{gen['port']} "
                  f"(fensterlos)")

    def launch_console_script(self, gen: dict, target: Path, package: str) -> None:
        """pip packages expose a console script in the venv's Scripts/ dir."""
        scripts = target / "venv" / "Scripts"
        exe = scripts / f"{package}-web.exe"
        if not exe.exists():
            self.emit(f"FEHLER Startskript von {gen['name']} nicht gefunden "
                      f"({package}-web.exe). Ist die Installation unvollstaendig?")
            return
        # invokeai-web only accepts --root/--config/--web-legacy/--version
        # (invokeai/frontend/cli/arg_parser.py). Passing --port made it abort with
        # an argparse error, so the port is configured via env instead.
        env_extra = {"INVOKEAI_ROOT": str(target / "invokeai_root")}
        self._spawn(gen, [str(exe)], target, env_extra=env_extra)
        self.emit(f"OK {gen['name']} startet auf http://127.0.0.1:{gen['port']} "
                  f"(fensterlos)")

    def _spawn(self, gen: dict, cmd: list[str], cwd: Path,
               env_extra: dict | None = None) -> None:
        env = self._run_env()
        if env_extra:
            env.update(env_extra)

        info = None
        if os.name == "nt":
            info = subprocess.STARTUPINFO()
            info.dwFlags = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            info.wShowWindow = 7  # SW_SHOWMINIMIZED

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                startupinfo=info,
            )
        except OSError as exc:
            self.emit(f"FEHLER Start fehlgeschlagen: {exc}")
            return
        self._launched[gen["id"]] = proc

    def stop(self, gen_id: str) -> None:
        proc = self._launched.pop(gen_id, None)
        if proc and proc.poll() is None:
            proc.terminate()
            self.emit(f"OK {gen_id} gestoppt")
        else:
            self.emit(f"HINWEIS {gen_id} laeuft gerade nicht")

    def is_running(self, gen_id: str) -> bool:
        proc = self._launched.get(gen_id)
        return bool(proc and proc.poll() is None)

    # ---------- uninstall ----------

    def uninstall(self, gen: dict, on_done: Callable[[], None]) -> None:
        self.stop(gen["id"])
        target = self.root / gen["folder"]

        def worker():
            try:
                if target.exists():
                    self.log(f">>> entferne {target}")
                    shutil.rmtree(target, ignore_errors=True)
                    self.log(f"OK {gen['name']} entfernt")
                else:
                    self.log(f"HINWEIS {gen['name']} war nicht installiert")
            except Exception as exc:  # noqa: BLE001
                self.log(f"FEHLER beim Entfernen: {exc}")
            finally:
                on_done()

        threading.Thread(target=worker, daemon=True, name="lopic-uninstall").start()

    def shutdown(self) -> None:
        self._stop.set()
        for proc in list(self._launched.values()):
            if proc.poll() is None:
                proc.terminate()