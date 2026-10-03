"""One short completion from local Ollama. Timing is measured around the call."""

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:1b"
# A short reply is about five seconds on an idle CPU. This host was busy
# enough that the same note took over a minute, so the cutoff sits higher
# than the twenty-second sketch and the page still gets a real answer.
TIMEOUT_SECONDS = 300
NUM_PREDICT = 90


def settings():
    url = os.environ.get("OLLAMA_URL", DEFAULT_URL).rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    return url, model


def model_label(model):
    if model == "gemma3:1b":
        return "Gemma 3 1B"
    return model


def generate(prompt, stop_when=None, timeout_seconds=None):
    """Return (text, elapsed_ms, error). elapsed_ms is the real call duration.

    Tokens are read as they arrive. stop_when(text) ends the call once the
    note is already usable, which matters when the CPU is busy. timeout_seconds
    caps this call; the default is the overall five-minute budget.
    """
    url, model = settings()
    limit = TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    if limit <= 0:
        return "", 0, "timed out"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "keep_alive": "10m",
        "options": {"temperature": 0.2, "num_predict": NUM_PREDICT},
    }
    request = urllib.request.Request(
        f"{url}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    text = ""
    error = None
    try:
        socket_timeout = 30 if limit > 30 else limit
        with urllib.request.urlopen(request, timeout=socket_timeout) as response:
            while True:
                if time.perf_counter() - started > limit:
                    error = "timed out"
                    break
                line = response.readline()
                if not line:
                    break
                if not line.strip():
                    continue
                piece = json.loads(line.decode())
                text += piece.get("response") or ""
                if stop_when and stop_when(text):
                    break
                if piece.get("done"):
                    break
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        error = str(exc)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return text, elapsed_ms, error
