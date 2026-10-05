"""model catalog for local image generation.

every size below was measured with a HEAD request against
huggingface.co/<repo>/resolve/main/<file> (HTTP 206 = downloadable
anonymously, 401 = needs an account + token).

VRAM numbers are ENGINEERING ESTIMATES derived from those file sizes, not
vendor-quoted minima: no hub card publishes one. The hard, verifiable number
is the download size, so that is what the ui filters on.

`gated` marks the models whose original repo requires a login. All of those
have an ungated mirror listed, and the mirror is what lopic downloads, so the
user never needs a token.
"""

from __future__ import annotations

from typing import Any

# hugging face base for downloads
HF = "https://huggingface.co"

# license shorthand -> one line the user can actually read
LICENSES = {
    "apache-2.0": "Apache 2.0 — frei verwendbar",
    "mit": "MIT — frei verwendbar",
    "creativeml-openrail-m": "OpenRAIL-M — frei, mit Nutzungsbedingungen",
    "openrail++": "OpenRAIL++ — frei, mit Nutzungsbedingungen",
    "flux-noncommercial": "Flux Nicht-kommerziell — nicht zum Verkauf",
}


def _files(repo: str, entries: list[tuple[str, int]]) -> list[dict[str, Any]]:
    """build the per-file download list from (name, size_bytes) pairs."""
    return [{"repo": repo, "name": n, "size": s} for n, s in entries]


MODELS: list[dict[str, Any]] = [
    # ---- tiny / fast: the ones that really fit a weak gpu
    {
        "id": "tiny-sd",
        "name": "Tiny SD",
        "family": "SD 1.5",
        "tagline": "Kleinstes brauchbares Modell",
        "color": "#34d399",
        "vram_gb": 3,
        "license": "creativeml-openrail-m",
        "kind": "destilliert",
        "note": "Aus Realistic Vision destilliert, laut Anbieter bis zu 80 % schneller als SD1.5. "
                "Braucht nur drei Komponenten statt einer großen Datei.",
        "gated": False,
        "home": "https://huggingface.co/segmind/tiny-sd",
        "files": _files("segmind/tiny-sd", [
            ("unet/diffusion_pytorch_model.bin", 646_923_637),
            ("text_encoder/pytorch_model.bin", 246_187_869),
            ("vae/diffusion_pytorch_model.bin", 167_407_857),
        ]),
    },
    {
        "id": "rv51-fp16",
        "name": "Realistic Vision 5.1",
        "family": "SD 1.5",
        "tagline": "Fotorealistisch, fp16",
        "color": "#f59e0b",
        "vram_gb": 4,
        "license": "creativeml-openrail-m",
        "kind": "Fotorealistisch",
        "note": "Echte Fotos statt Malerei. Die fp16-Datei ist halb so groß wie die "
                "fp32-Version. Braucht eine separate VAE (siehe sd-vae).",
        "gated": False,
        "home": "https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE",
        "files": _files("SG161222/Realistic_Vision_V5.1_noVAE", [
            ("Realistic_Vision_V5.1_fp16-no-ema.safetensors", 2_132_625_894),
        ]),
    },
    # ---- sd 1.5
    {
        "id": "sd15",
        "name": "Stable Diffusion 1.5",
        "family": "SD 1.5",
        "tagline": "Das Standardmodell",
        "color": "#7c5cff",
        "vram_gb": 4,
        "license": "creativeml-openrail-m",
        "kind": "Basis",
        "note": "Das Ur-Modell. Klein, schnell, und die mit Ab meisten LoRAs und "
                "ControlNets. Gute Wahl als Startmodell.",
        "gated": False,
        "home": "https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5",
        "files": _files("stable-diffusion-v1-5/stable-diffusion-v1-5", [
            ("v1-5-pruned-emaonly.safetensors", 4_265_146_304),
        ]),
    },
    {
        "id": "sd-vae",
        "name": "SD VAE (ft-mse)",
        "family": "Zubehör",
        "tagline": "Repariert dunkle SD1.5-Bilder",
        "color": "#22d3ee",
        "vram_gb": 0,
        "license": "mit",
        "kind": "VAE",
        "note": "Pflicht für Modelle ohne eigene VAE. Repariert dunkle, flache "
                "Farben bei SD1.5. Nur 0,3 GB.",
        "gated": False,
        "home": "https://huggingface.co/stabilityai/sd-vae-ft-mse",
        "files": _files("stabilityai/sd-vae-ft-mse", [
            ("diffusion_pytorch_model.safetensors", 334_643_276),
        ]),
    },
    # ---- sdxl
    {
        "id": "ssd-1b",
        "name": "SSD-1B",
        "family": "SDXL",
        "tagline": "SDXL, halb so groß",
        "color": "#a78bfa",
        "vram_gb": 6,
        "license": "apache-2.0",
        "kind": "destilliert",
        "note": "Destillierte SDXL-Version: rund halb so groß und deutlich schneller. "
                "Apache-Lizenz, also auch kommerziell nutzbar.",
        "gated": False,
        "home": "https://huggingface.co/segmind/SSD-1B",
        "files": _files("segmind/SSD-1B", [
            ("SSD-1B.safetensors", 4_465_671_506),
        ]),
    },
    {
        "id": "sdxl-base",
        "name": "SDXL Base 1.0",
        "family": "SDXL",
        "tagline": "Hohe Qualität, 4K-fähig",
        "color": "#ec4899",
        "vram_gb": 8,
        "license": "openrail++",
        "kind": "Basis",
        "note": "Stabilitys SDXL-Grundmodell. Deutlich bessere Komposition als SD1.5, "
                "braucht dafür bei 8 GB den Low-VRAM-Modus.",
        "gated": False,
        "home": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
        "files": _files("stabilityai/stable-diffusion-xl-base-1.0", [
            ("sd_xl_base_1.0.safetensors", 6_938_078_334),
        ]),
    },
    # ---- flux: the only ones that need an account at the original repo
    {
        "id": "flux-schnell-fp8",
        "name": "Flux schnell (fp8)",
        "family": "Flux",
        "tagline": "Bestes Prompt-Verständnis",
        "color": "#f87171",
        "vram_gb": 12,
        "license": "apache-2.0",
        "kind": "destilliert (4 Schritte)",
        "note": "Flux in fp8. Versteht lange, genaue Beschreibungen besser als alles "
                "andere hier. Lädt von einem Spiegel ohne Konto; das Original von "
                "Black Forest Labs ist hinter einer Anmeldung.",
        "gated": False,
        "mirror_of": "black-forest-labs/FLUX.1-schnell",
        "home": "https://huggingface.co/Comfy-Org/flux1-schnell",
        "files": _files("Comfy-Org/flux1-schnell", [
            ("flux1-schnell-fp8.safetensors", 17_236_328_572),
        ]),
    },
    {
        "id": "sd35-medium",
        "name": "SD 3.5 Medium",
        "family": "SD 3.5",
        "tagline": "Modernste Textur",
        "color": "#f97316",
        "vram_gb": 12,
        "license": "flux-noncommercial",
        "kind": "Basis",
        "note": "Stabilitys neueste Architektur. Das Original liegt hinter einer "
                "Anmeldung mit Formular (Name, Land, Verwendungszweck) — deshalb "
                "steht hier kein direkter Download. 12 GB VRAM nötig.",
        "gated": True,
        "home": "https://huggingface.co/stabilityai/stable-diffusion-3.5-medium",
        "files": [],
    },
]


def total_size(model: dict[str, Any]) -> int:
    return sum(f["size"] for f in model["files"])


def by_id(model_id: str) -> dict[str, Any] | None:
    for m in MODELS:
        if m["id"] == model_id:
            return m
    return None


def license_text(key: str) -> str:
    return LICENSES.get(key, key)
