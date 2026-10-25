"""
=====================================================================
 Tagesbrief – Verbindung zur KI (Google Gemini, Gratis-Tarif)
=====================================================================
Der Schlüssel kommt aus der Umgebungsvariable GEMINI_API_KEY oder aus
der Datei news-app/.env (Zeile: GEMINI_API_KEY=...). Er wird nie ausgegeben.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Der Reihe nach: das stärkste zuerst; ist eins überlastet, springt das nächste ein. Flash-Lite nur als letzte Rettung.
MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite"
).split(",") if m.strip()]
LAST_RESORT = MODELS[-1]
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
TIMEOUT = 150  # ein normaler Durchlauf braucht 30–80 Sekunden; wer länger hängt, ist überlastet
ROUNDS = int(os.environ.get("GEMINI_ROUNDS", "3"))  # so oft werden die starken Modelle durchprobiert
ROUND_PAUSE = 60  # Sekunden vor der zweiten Runde, danach jeweils doppelt so lang
# Wie gründlich das Modell vorher „nachdenkt“. Hoch dauert mehrere Minuten, für ein Briefing reicht niedrig.
THINKING_LEVEL = os.environ.get("GEMINI_THINKING", "low")


class AIError(Exception):
    pass


class AIFatal(AIError):
    """Fehler, bei dem weiteres Probieren sinnlos ist (z. B. Schlüssel ungültig)."""


def api_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "GEMINI_API_KEY" and value.strip():
                return value.strip().strip("'\"")
    return None


def _post(model: str, key: str, body: dict) -> dict:
    req = urllib.request.Request(
        API.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return json.loads(res.read())


def generate_json(system: str, prompt: str, schema: dict, start_with: str | None = None) -> tuple[dict, str]:
    """Fragt Gemini nach einer JSON-Antwort im vorgegebenen Format. Gibt (Antwort, verwendetes Modell) zurück.
    start_with: Modell, das gerade funktioniert hat – überspringt die (vermutlich noch überlasteten) davor."""
    models = MODELS[MODELS.index(start_with):] if start_with in MODELS else MODELS
    key = api_key()
    if not key:
        raise AIError("Kein GEMINI_API_KEY gefunden (Datei news-app/.env oder Umgebungsvariable)")

    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "thinkingConfig": {"thinkingLevel": THINKING_LEVEL},
        },
    }
    strong = [m for m in models if m != LAST_RESORT]
    errors = []
    # Erst die starken Modelle, notfalls in mehreren Runden mit wachsender Pause – morgens ist Zeit genug.
    for round_no in range(ROUNDS if strong else 0):
        if round_no:
            pause = ROUND_PAUSE * 2 ** (round_no - 1)
            print(f"  Starke Modelle überlastet, neuer Versuch in {pause} Sekunden …", file=sys.stderr)
            time.sleep(pause)
        for model in strong:
            try:
                return _ask(model, key, body), model
            except AIFatal:
                raise
            except AIError as err:
                errors.append(str(err))
    # Letzte Rettung: das kleine Modell
    if strong:
        print("  Starke Modelle nicht erreichbar:\n    " + "\n    ".join(e[:160] for e in errors), file=sys.stderr)
    try:
        return _ask(LAST_RESORT, key, body), LAST_RESORT
    except AIError as err:
        errors.append(str(err))
    raise AIError(" | ".join(errors))


def _ask(model: str, key: str, body: dict) -> dict:
    """Ein Versuch bei einem Modell. Ein ungültiger Schlüssel bricht sofort alles ab (AIFatal)."""
    try:
        data = _post(model, key, body)
    except urllib.error.HTTPError as err:
        message = f"{model}: HTTP {err.code} {err.read().decode(errors='replace')[:200]}"
        if err.code in (400, 401, 403):
            raise AIFatal(message)
        raise AIError(message)  # 429/5xx = überlastet, 404 = Modell gibt es nicht (mehr)
    except OSError as err:  # Netzwerkfehler und Zeitüberschreitung (socket.timeout ist in Python 3.9 kein TimeoutError)
        raise AIError(f"{model}: {type(err).__name__} {err}")

    candidate = (data.get("candidates") or [{}])[0]
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise AIError(f"{model}: unbrauchbare Antwort (finishReason={candidate.get('finishReason')})")
