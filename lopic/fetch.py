"""downloads model weights from hugging face into the right engine folder.

one model file list can span several paths, so each entry carries its own
target relative to the engine root. diffusers-only repos (tiny-sd) keep
their folder structure; single-file checkpoints land flat.

progress is reported per model, streaming from the http response so a
6 GB file shows a moving percentage instead of a frozen bar.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HF = "https://huggingface.co"
CHUNK = 1024 * 256  # 256 KiB
TIMEOUT = 30


def target_for(gen_id: str, rel_path: str) -> Path:
    """map a hugging face path to the folder the engine actually reads.

    forge / a1111 / fooocus look in models/Stable-diffusion/,
    comfyui uses models/checkpoints/. diffusers repos keep their own
    subfolders under models/.
    """
    parts = Path(rel_path).parts
    if len(parts) > 1 and parts[0] in ("unet", "vae", "text_encoder", "text_encoder_2"):
        # diffusers layout: keep the structure, it is what the code imports
        return Path("models", *parts)
    # comfyui reads checkpoints/, everything else reads Stable-diffusion/
    folder = "checkpoints" if gen_id == "comfyui" else "Stable-diffusion"
    return Path("models") / folder / parts[-1]


@dataclass
class Download:
    model_id: str
    status: str = "queued"      # queued | running | done | error | skipped
    progress: float = 0.0       # 0..1 across the whole model
    received: int = 0
    total: int = 0
    current_file: str = ""
    error: str = ""


class ModelFetcher:
    """one model at a time. no token: the catalog only lists ungated files."""

    def __init__(self, root: Path, emit: Callable[[str], None],
                 emit_state: Callable[[dict], None]):
        self.root = Path(root)
        self.emit = emit
        self.emit_state = emit_state
        self.downloads: dict[str, Download] = {}
        self.current: str | None = None

    def _push(self, dl: Download) -> None:
        self.emit_state({
            "id": dl.model_id,
            "status": dl.status,
            "progress": round(dl.progress, 3),
            "received": dl.received,
            "total": dl.total,
            "current_file": dl.current_file,
            "error": dl.error,
        })

    def installed_models(self) -> dict[str, bool]:
        """a model counts as present when any of its files sits in an engine."""
        from .models import MODELS

        return {m["id"]: bool(m["files"]) and self._any_present(m) for m in MODELS}

    def _any_present(self, model: dict) -> bool:
        """check every engine folder for any of the model's file names."""
        names = {Path(f["name"]).name for f in model["files"]}
        if not names:
            return False
        for models_dir in self.root.glob("*/models"):
            if not models_dir.is_dir():
                continue
            for path in models_dir.rglob("*"):
                if path.is_file() and path.name in names:
                    return True
        return False

    def start(self, model: dict) -> None:
        if self.current is not None:
            self.emit("FEHLER Es laeuft bereits ein Download.")
            return
        if model.get("gated") or not model.get("files"):
            self.emit(f"HINWEIS {model['name']} laesst sich nicht ohne Konto laden.")
            return
        self.current = model["id"]
        dl = Download(model_id=model["id"], status="running",
                      total=sum(f["size"] for f in model["files"]))
        self.downloads[dl.model_id] = dl
        self._push(dl)
        import threading
        threading.Thread(target=self._worker, args=(model, dl), daemon=True,
                         name=f"lopic-model-{model['id']}").start()

    def _worker(self, model: dict, dl: Download) -> None:
        try:
            # progress spans the whole model: dl.total is the sum over every file
            # and dl.received is the bytes of the finished files plus the current
            # one, tracked by accumulating chunk sizes
            dl.total = sum(f["size"] for f in model["files"])
            done = 0
            for spec in model["files"]:
                dl.current_file = spec["name"]
                self.emit(f">>> {model['name']}: {spec['name']}")
                target = self._target_for(model, spec)
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(target.suffix + ".part")

                url = f"{HF}/{spec['repo']}/resolve/main/{spec['name']}"
                req = urllib.request.Request(url, headers={"User-Agent": "Lopic"})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    got = 0
                    with open(tmp, "wb") as fh:
                        while chunk := resp.read(CHUNK):
                            fh.write(chunk)
                            got += len(chunk)
                            dl.received = done + got
                            dl.progress = min(0.999, dl.received / dl.total
                                              if dl.total else 0)
                            self._push(dl)
                tmp.replace(target)
                done += got
                mb = got / (1024 * 1024)
                self.emit(f"OK {mb:.0f} MB -> {target}")

            dl.status = "done"
            dl.progress = 1.0
            self.emit(f"OK {model['name']} ist fertig.")
            self._push(dl)
        except urllib.error.HTTPError as exc:
            dl.status = "error"
            dl.error = f"HTTP {exc.code}"
            self.emit(f"FEHLER Download fehlgeschlagen: HTTP {exc.code} "
                      f"({model['name']})")
            self._push(dl)
        except Exception as exc:  # noqa: BLE001
            dl.status = "error"
            dl.error = str(exc)
            self.emit(f"FEHLER {model['name']}: {exc}")
            self._push(dl)
        finally:
            self.current = None

    def _target_for(self, model: dict, spec: dict) -> Path:
        """first engine that is installed wins; otherwise forge's layout."""
        engines = {"comfyui": "ComfyUI", "forge": "stable-diffusion-webui-forge",
                   "a1111": "stable-diffusion-webui", "fooocus": "Fooocus",
                   "sdnext": "sdnext", "invokeai": "InvokeAI"}
        for gid, folder in engines.items():
            if (self.root / folder / "models").exists():
                return self.root / folder / target_for(gid, spec["name"])
        default = engines["forge"]
        return self.root / default / target_for("forge", spec["name"])
