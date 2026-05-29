"""
Quick-start helper — run this file directly for local development
without Docker.  It checks prerequisites and launches uvicorn.

Usage:
    python starting.py
"""

import subprocess
import sys
from pathlib import Path


# ── llama-cpp-python install config ───────────────────────────────────────────
# CPU-only index — no CUDA, no compiler, no MSVC required.
LLAMA_CPU_INDEX = "https://abetlen.github.io/llama-cpp-python/whl/cpu"
LLAMA_VERSION   = "llama-cpp-python==0.2.77"

# Direct fallback wheel for Python 3.10 Windows x64
LLAMA_FALLBACK_WHEEL = (
    "https://github.com/abetlen/llama-cpp-python/releases/download/"
    "v0.2.77/llama_cpp_python-0.2.77-cp310-cp310-win_amd64.whl"
)


def ensure_llama():
    """Install llama-cpp-python CPU wheel if not already present."""
    try:
        import llama_cpp  # noqa: F401
        print("✓  llama-cpp-python already installed.")
        return
    except FileNotFoundError as e:
        # CUDA build installed but CUDA toolkit missing — must reinstall CPU build
        print(f"\n⚠  Detected broken CUDA build of llama-cpp-python: {e}")
        print("   Uninstalling and replacing with CPU-only build …\n")
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "llama-cpp-python", "-y"],
            check=False,
        )
    except ImportError:
        pass

    print("\n📦  llama-cpp-python not found — installing CPU-only wheel …")
    print("    (no CUDA or compiler required)\n")

    # First attempt: CPU index
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--prefer-binary",
            "--extra-index-url", LLAMA_CPU_INDEX,
            LLAMA_VERSION,
        ],
        check=False,
    )

    if result.returncode != 0:
        print("    Primary install failed, trying direct wheel …")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", LLAMA_FALLBACK_WHEEL],
            check=False,
        )

    if result.returncode != 0:
        print(
            "\n⚠  Could not install llama-cpp-python.\n"
            "   The app will still run using the regex NLP fallback.\n"
            "   Manual install command:\n"
            f"     pip install --prefer-binary --extra-index-url {LLAMA_CPU_INDEX} {LLAMA_VERSION}\n"
        )
    else:
        print("✓  llama-cpp-python installed successfully.")


def check_model():
    from config import MODEL_PATH, MODELS_DIR
    if not Path(MODEL_PATH).exists():
        print(
            f"\n⚠  Model file not found at:\n   {MODEL_PATH}\n\n"
            "   The app will still run but NLP will use the regex fallback.\n"
            "   To enable full AI parsing, download:\n"
            "     Phi-3.5-mini-instruct-Q4_K_M.gguf  (~2.4 GB)\n"
            "   from:\n"
            "     https://huggingface.co/microsoft/Phi-3.5-mini-instruct-gguf\n"
            f"   and place it in:  {MODELS_DIR}\n"
        )
    else:
        print(f"✓  Model found: {MODEL_PATH}")


def check_prowlarr():
    import os
    key = os.getenv("PROWLARR_API_KEY", "")
    url = os.getenv("PROWLARR_URL", "http://localhost:9696")
    if not key:
        print(
            "\n⚠  PROWLARR_API_KEY is not set.\n"
            "   Set it before searching:\n"
            "     set PROWLARR_API_KEY=your-key-here   (CMD)\n"
            "     $env:PROWLARR_API_KEY='your-key'     (PowerShell)\n"
        )
    else:
        print(f"✓  Prowlarr: {url}")


if __name__ == "__main__":
    print("=" * 55)
    print("  Searcherr — local dev launcher")
    print("=" * 55)

    ensure_llama()
    check_model()
    check_prowlarr()

    print("\nStarting server at http://localhost:8000 …\n")
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
        cwd=Path(__file__).parent,
    )
