# Lopic

Install and launch local image generators on your PC — with a sleek interface.

Lopic is not an image generator itself, but a **manager**: it shows you available Stable Diffusion tools, explains them, installs them including the matching CUDA/Torch version, and launches them windowless in the background.

## Features

- **Six generators** with descriptions, VRAM requirements, licenses, and installation steps
- **Automatic hardware detection**: GPU, VRAM, free storage, Git/uv/Python
- **VRAM matching**: Cards are highlighted in green/yellow/red depending on whether your GPU is sufficient
- **One-click installation** with live logs and progress bars
- **Dedicated Python environment per generator**, ensuring they don't interfere with each other
- **Windowless launch**: No console windows, no stealing focus

## The Six Generators

| Generator | Purpose | Python | VRAM | Startup |
|---|---|---|---|---|
| **ComfyUI** | Node-based pipeline engine, the most powerful and efficient option | 3.12 | 4 GB | `main.py` |
| **Forge** | Successor to A1111, same interface, faster and resource-light | 3.10 | 4 GB | `launch.py` |
| **Fooocus** | Just enter a prompt, get a finished image — the easiest entry point | 3.10 | 4 GB | `launch.py` |
| **AUTOMATIC1111** | The original with the largest extension ecosystem | 3.10 | 6 GB | `launch.py` |
| **InvokeAI** | Most beautiful UI with Canvas and built-in image editing | 3.12 | 6 GB | `invokeai-web` |
| **SD.Next** | Image, video, and 3D generation in a single tool, very actively maintained | 3.12 | 6 GB | `launch.py` |

All information regarding source code, startup files, `requirements` filenames, **and Python versions** has been verified against the actual repositories, not guessed. This is not purely cosmetic: on Windows, Forge, Fooocus, and A1111 reject any other Python minor release. Forge and A1111 fail with `INCOMPATIBLE PYTHON VERSION`, while Fooocus terminates the installation with `exit(0)`. Therefore, Lopic creates a separate venv for each generator using its pinned version.

## Installation

```bat
git clone https://github.com<your-name>/Lopic.git
cd Lopic
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
start.bat
```

Alternatively, you can use the classic `python -m venv .venv` + `pip install -r requirements.txt` without `uv`.

Prerequisites: Windows 10/11, WebView2 Runtime (included with Windows and Edge), Git, Python 3.11/3.12 for the generators, NVIDIA drivers.

## File Locations

| Path | Contents |
|---|---|
| `%APPDATA%\Lopic\config.json` | Settings and window size |
| `~\LopicEngines\<Generator>` | Source code, dedicated `venv`, models |

The generators download models automatically on demand. For the initial run, plan roughly **10–20 GB** per generator, plus the model files.

## Project Structure

```
lopic/
  app.py        Window + Python <-> JS Bridge
  catalog.py    The six generators with all metadata
  install.py    Installation orchestrator (clone, venv, torch, deps)
  settings.py   Configuration under %APPDATA%
  system.py     GPU / VRAM / Disk detection
ui/
  index.html    Markup
  style.css     Styling
  app.js        Frontend logic
```

## Technical Notes

- **UI**: WebView2 (Edge) via `pywebview`, pure HTML/CSS/JS. This makes the interface look like a web app rather than a classic window.
- **Why no `--listen`**: The generators only bind to `127.0.0.1`. Using `--listen` without arguments would expose the interface to the entire local network.
- **pywebview 6.x**: `create_window(loaded=...)` no longer exists; events are now attached to `window.events.loaded`. The `pywebviewready` DOM event fires *before* inline scripts can register their listeners — which is why the frontend is initialized via a trigger from Python (`_kick_frontend`) instead of a JS listener.

## License

The code in this repository is licensed under the MIT License. The installed generators have their own respective licenses (GPL-3.0, AGPL-3.0, Apache-2.0) — see the individual cards.
