"""the generator catalog.

every field here was verified against the actual repos / docs (see README):
repo url, requirements filename, launch entry point, python version, license.
do not guess a filename -- check the repo listing first.
"""

from __future__ import annotations

from typing import Any

# torch wheel index per CUDA generation. verified to resolve cp312 win_amd64 wheels.
TORCH_CU121 = "https://download.pytorch.org/whl/cu121"
TORCH_CU124 = "https://download.pytorch.org/whl/cu124"
TORCH_CU128 = "https://download.pytorch.org/whl/cu128"
TORCH_CU130 = "https://download.pytorch.org/whl/cu130"

CATALOG: list[dict[str, Any]] = [
    {
        "id": "comfyui",
        "name": "ComfyUI",
        "tagline": "Node-basierte Pipeline-Engine",
        "color": "#22d3ee",
        "repo": "https://github.com/Comfy-Org/ComfyUI.git",
        "branch": "master",
        "folder": "ComfyUI",
        "requirements": "requirements.txt",
        "entry": "main.py",
        "entry_module": "main",
        "python": "3.12",
        "port": 8188,
        "vram_min_gb": 4,
        "size_gb": 8,
        "license": "GPL-3.0",
        "easy": False,
        "torch_index": TORCH_CU128,
        "description": (
            "ComfyUI baut Bildgenerierung als Knoten-Graph: du verbindest Bausteine wie "
            "Checkpoint, Prompt, Sampler und Upscaler zu einem Ablauf. Das ist mächtiger als "
            "klassische Web-UIs, weil sich exakt reproduzierbare Pipelines speichern und "
            "frei kombinieren lassen. Braucht mehr Einarbeitung, dafür ist es die "
            "leistungsfähigste und speichersparsamste Option."
        ),
        "features": [
            "Node-Graph statt Formular: Pipelines speichern und teilen",
            "Sehr sparsam mit VRAM, läuft auch auf schwachen GPUs",
            "Riesige Erweiterungs-Auswahl (ComfyUI-Manager)",
            "Volle Kontrolle ueber jeden Pipeline-Schritt",
        ],
        "steps": [
            "<b>Quelle holen</b> — Git-Repo wird nach <code>LopicEngines/ComfyUI</code> geklont.",
            "<b>Eigene Umgebung</b> — eigenes venv, damit Forge & Co. unbeeinflusst bleiben.",
            "<b>CUDA-Torch</b> — Torch + torchvision für deine RTX 4060 (NVIDIA-Index).",
            "<b>Abhaengigkeiten</b> — <code>requirements.txt</code> wird installiert.",
        ],
    },
    {
        "id": "forge",
        "name": "Forge",
        "tagline": "Der Klassiker, schneller gemacht",
        "color": "#7c5cff",
        "repo": "https://github.com/lllyasviel/stable-diffusion-webui-forge.git",
        "branch": "main",
        "folder": "stable-diffusion-webui-forge",
        "requirements": "requirements_versions.txt",
        "entry": "launch.py",
        "entry_module": "launch",
        "python": "3.11",
        "port": 7860,
        "vram_min_gb": 4,
        "size_gb": 9,
        "license": "GPL-3.0",
        "easy": True,
        "torch_index": TORCH_CU124,
        "description": (
            "Forge ist der Nachfolger von AUTOMATIC1111s WebUI: gleiche Oberflaeche und "
            "gleiche Erweiterungen, aber mit optimiertem Speichermanagement. Bilder werden "
            "schneller und mit weniger VRAM erzeugt. Wenn du die klassische WebUI-Oberflaeche "
            "willst, ist Forge die beste Wahl."
        ),
        "features": [
            "Drop-in-Ersatz fuer A1111: bekannte Oberflaeche und Erweiterungen",
            "Schnelleres Rendern durch besseres VRAM-Management",
            "Sehr grosses Erweiterungs-Okosystem (ControlNet, LoRA, …)",
            "Guter Kompromiss aus Leistung und Bedienbarkeit",
        ],
        "steps": [
            "<b>Quelle holen</b> — Git-Repo wird nach <code>LopicEngines/stable-diffusion-webui-forge</code> geklont.",
            "<b>Eigene Umgebung</b> — eigenes venv mit Python 3.11 (Forge pinnt 3.11).",
            "<b>CUDA-Torch</b> — Torch + torchvision für deine RTX 4060.",
            "<b>Abhaengigkeiten</b> — <code>requirements_versions.txt</code> wird installiert.",
        ],
    },
    {
        "id": "fooocus",
        "name": "Fooocus",
        "tagline": "Ein Prompt, fertiges Bild",
        "color": "#ec4899",
        "repo": "https://github.com/lllyasviel/Fooocus.git",
        "branch": "main",
        "folder": "Fooocus",
        "requirements": "requirements_versions.txt",
        "entry": "launch.py",
        "entry_module": "launch",
        "python": "3.11",
        "port": 7861,
        "vram_min_gb": 4,
        "size_gb": 12,
        "license": "Apache-2.0",
        "easy": True,
        "torch_index": TORCH_CU124,
        "description": (
            "Fooocus versteckt die komplexe Technik: du schreibst einen Prompt, Fooocus waehlt "
            "Modell, Aufloesung und Optimierungen selbst. Die Ergebnisse sind ueberraschend "
            "gut, ohne dass du Parameter feilt. Der beste Einstieg, wenn du schnell Bilder "
            "willst und nicht konfigurieren moechtest."
        ),
        "features": [
            "Nur Prompt noetig — alles andere wird automatisch gewaehlt",
            "Sehr gute Bildqualitaet mit minimalem Aufwand",
            "Inpaint/outpaint direkt im UI",
            "Gut geeignet fuer Gelegenheits- und schnelle Arbeitsbilder",
        ],
        "steps": [
            "<b>Quelle holen</b> — Git-Repo wird nach <code>LopicEngines/Fooocus</code> geklont.",
            "<b>Eigene Umgebung</b> — eigenes venv mit Python 3.11.",
            "<b>CUDA-Torch</b> — Torch + torchvision für deine RTX 4060.",
            "<b>Abhaengigkeiten + Modelle</b> — Pakete und ca. 6 GB Startmodelle werden geladen.",
        ],
    },
    {
        "id": "a1111",
        "name": "AUTOMATIC1111",
        "tagline": "Der Ursprung mit riesiger Erweiterbarkeit",
        "color": "#f59e0b",
        "repo": "https://github.com/AUTOMATIC1111/stable-diffusion-webui.git",
        "branch": "master",
        "folder": "stable-diffusion-webui",
        "requirements": "requirements_versions.txt",
        "entry": "launch.py",
        "entry_module": "launch",
        "python": "3.11",
        "port": 7862,
        "vram_min_gb": 6,
        "size_gb": 10,
        "license": "AGPL-3.0",
        "easy": False,
        "torch_index": TORCH_CU121,
        "description": (
            "Das Original: hoeherwertige Optionen, aber langsamer und speicherintensiver als "
            "Forge, und das Projekt pflegt sich nur noch im Unterhaltungsmodus. Lohnt sich vor "
            "allem, wenn du Erweiterungen brauchst, die es nur hier gibt."
        ),
        "features": [
            "Groesste und aelteste Erweiterungs-Welt",
            "Viele Spezialfunktionen fuer Training und Video",
            "Gut fuer Nischenerweiterungen und Reproduction exakter Setups",
            "Wartungsmodus: Sicherheitsupdates, kaum neue Features",
        ],
        "steps": [
            "<b>Quelle holen</b> — Git-Repo wird nach <code>LopicEngines/stable-diffusion-webui</code> geklont.",
            "<b>Eigene Umgebung</b> — eigenes venv mit Python 3.11.",
            "<b>CUDA-Torch</b> — Torch + torchvision (aelteres CUDA-Index fuer Kompatibilitaet).",
            "<b>Abhaengigkeiten</b> — <code>requirements_versions.txt</code> wird installiert.",
        ],
    },
    {
        "id": "invokeai",
        "name": "InvokeAI",
        "tagline": "Schonste Oberflaeche, starke Bildbearbeitung",
        "color": "#34d399",
        "repo": "https://github.com/invoke-ai/InvokeAI.git",
        "branch": "main",
        "folder": "InvokeAI",
        "requirements": "",
        "entry": "",
        "entry_module": "",
        "python": "3.12",
        "port": 9090,
        "vram_min_gb": 6,
        "size_gb": 14,
        "license": "Apache-2.0",
        "easy": True,
        "torch_index": TORCH_CU128,
        "package_install": "invokeai",
        "description": (
            "InvokeAI ist die einsteigerfreundlichste vollwertige Oberflaeche: Canvas zum "
            "Malen, Auswahl-Werkzeug, grosses Modell-Archiv. Stark bei Bildbearbeitung und "
            "Inpainting. Achtung: es ist ein pip-Paket, kein simples Repo-Skript."
        ),
        "features": [
            "Canvas-Werkzeug mit Pinsel und Auswahl-Werkzeug",
            "Integriertes Modell-Archiv mit Suche",
            "Sehr aufgeräumte Oberflaeche, gute Doku",
            "Wird als pip-Paket installiert, nicht aus dem Repo gestartet",
        ],
        "steps": [
            "<b>Quelle holen</b> — Git-Repo wird nach <code>LopicEngines/InvokeAI</code> geklont (Doku + Quellcode).",
            "<b>Eigene Umgebung</b> — eigenes venv mit Python 3.12.",
            "<b>CUDA-Torch</b> — Torch + torchvision fuer deine RTX 4060.",
            "<b>Paket installieren</b> — <code>pip install invokeai</code>; gestartet wird ueber das Console-Script <code>invokeai-web</code>.",
        ],
    },
    {
        "id": "sdnext",
        "name": "SD.Next",
        "tagline": "Viele Bildarten in einem Tool",
        "color": "#f87171",
        "repo": "https://github.com/vladmandic/sdnext.git",
        "branch": "master",
        "folder": "sdnext",
        "requirements": "requirements.txt",
        "entry": "launch.py",
        "entry_module": "launch",
        "python": "3.12",
        "port": 7863,
        "vram_min_gb": 6,
        "size_gb": 15,
        "license": "AGPL-3.0",
        "easy": False,
        "torch_index": TORCH_CU130,
        "description": (
            "SD.Next vereint Bild-, Video- und 3D-Generierung in einer Oberflaeche und ist "
            "eines der aktivsten Projekte im Umfeld. Der Starter des Projekts nutzt eine "
            "Vorgaengerversion von Torch. Es gibt keine offizielle Windows-Portable-Version, "
            "also muss der Quellcode selbst eingerichtet werden."
        ),
        "features": [
            "Text-, Bild- und Videoausgabe in einer Oberflaeche",
            "Sehr aktiv gepflegt, schnell neue Modelle und Funktionen",
            "Viele Backend-Optionen (TensorRT, Diffusers, …)",
            "Keine offizielle Windows-Portable-Version verfuegbar",
        ],
        "steps": [
            "<b>Quelle holen</b> — Git-Repo wird nach <code>LopicEngines/sdnext</code> geklont.",
            "<b>Eigene Umgebung</b> — eigenes venv mit Python 3.12.",
            "<b>CUDA-Torch</b> — Torch + torchvision fuer deine RTX 4060.",
            "<b>Abhaengigkeiten</b> — <code>requirements.txt</code> wird installiert.",
        ],
    },
]


def by_id(gen_id: str) -> dict[str, Any] | None:
    for gen in CATALOG:
        if gen["id"] == gen_id:
            return gen
    return None