"""Launcher for the local MLX LLM server.

Phase 1 of the local-LLM migration: this does not implement a server, it just
starts `mlx_lm.server` (an OpenAI-compatible HTTP server) with the model and
port this project expects.  The model is loaded once at startup and stays warm,
and mlx-lm reuses the KV cache for requests that share a prompt prefix — which
is what makes the large static system prompt cheap to resend every time.

Run with:
    poetry run python -m llm_server.server

Requires the optional `llm` dependency group:
    poetry install --with llm
"""
import importlib.util
import os
import shutil
import subprocess
import sys

# 4-bit Mistral 7B is ~4.2GB of weights, which leaves comfortable headroom on a
# 16GB machine.  Override with LLM_MODEL to try a different one.
DEFAULT_MODEL = "mlx-community/Mistral-7B-Instruct-v0.3-4bit"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "8080"


def build_command() -> list[str]:
    """Build the mlx_lm.server command line, preferring the console script."""
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    host = os.environ.get("LLM_HOST", DEFAULT_HOST)
    port = os.environ.get("LLM_PORT", DEFAULT_PORT)

    console_script = shutil.which("mlx_lm.server")
    base = [console_script] if console_script else [sys.executable, "-m", "mlx_lm.server"]

    return base + ["--model", model, "--host", host, "--port", port]


def check_install() -> str | None:
    """Return an error message if mlx_lm is missing from this interpreter.

    Poetry can have more than one virtualenv for this project, and it is easy
    to install the `llm` group into one and run from the other, so name the
    interpreter explicitly rather than leaving a bare ModuleNotFoundError.
    """
    if importlib.util.find_spec("mlx_lm") is not None:
        return None

    return (
        f"mlx_lm is not installed in this interpreter:\n"
        f"    {sys.executable}\n\n"
        f"Install the optional dependency group into it with:\n"
        f"    poetry env use {sys.executable}\n"
        f"    poetry install --with llm"
    )


def run() -> int:
    """Start the MLX server in the foreground."""
    error = check_install()
    if error:
        print(error, file=sys.stderr)
        return 1

    command = build_command()
    print(f"Starting MLX server: {' '.join(command)}")
    print("First run downloads the model (~4.2GB) to ~/.cache/huggingface.")

    try:
        return subprocess.call(command)
    except FileNotFoundError:
        print(
            "Could not find mlx_lm. Install the optional dependency group with:\n"
            "    poetry install --with llm",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(run())
