"""
=====================================================================
 Tagesbrief – Push-Nachrichten verschicken
=====================================================================
Braucht das Zusatzpaket pywebpush und zwei Geheimnisse:
- PUSH_SUBSCRIPTIONS: die Verbindungs-Codes aus der App (TB1.…), einer pro Zeile
- VAPID_PRIVATE_KEY:  der private Push-Schlüssel (PEM)
Am Mac kommen beide aus news-app/.vapid/ (subscriptions.txt, private.pem).

Test-Push:  .venv/bin/python pipeline/push.py "Titel" "Text"
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from pathlib import Path

SITE = "https://hagenbdroyd.github.io/tagesbrief/"
VAPID_DIR = Path(__file__).resolve().parent.parent / ".vapid"
TTL = 6 * 3600  # so lange hebt Apple einen Push auf, falls das iPhone gerade offline ist


def decode(code: str) -> dict:
    """Verbindungs-Code aus der App (TB1.<base64>) → Abo-Daten für den Push-Dienst."""
    code = code.strip().removeprefix("TB1.")
    return json.loads(base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)))


def subscriptions() -> list[dict]:
    raw = os.environ.get("PUSH_SUBSCRIPTIONS", "")
    local = VAPID_DIR / "subscriptions.txt"
    if not raw and local.exists():
        raw = local.read_text(encoding="utf-8")
    return [decode(code) for code in raw.split() if code.strip()]


def key_file() -> str:
    pem = os.environ.get("VAPID_PRIVATE_KEY", "")
    if not pem:
        return str(VAPID_DIR / "private.pem")
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(pem)
    return f.name


def send(title: str, body: str, tag: str | None = None, url: str = SITE, urgent: bool = False) -> int:
    """Schickt einen Push an alle hinterlegten Geräte. Gibt zurück, wie viele ihn angenommen haben."""
    from pywebpush import WebPushException, webpush  # nur hier nötig – der Rest kommt ohne Zusatzpakete aus

    subs = subscriptions()
    if not subs:
        print("  Kein Gerät für Push hinterlegt (PUSH_SUBSCRIPTIONS fehlt)", file=sys.stderr)
        return 0
    payload = json.dumps({"title": title, "body": body, "tag": tag, "url": url}, ensure_ascii=False)
    keyfile = key_file()
    delivered = 0
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=keyfile,
                vapid_claims={"sub": SITE},  # neues dict pro Aufruf, pywebpush ergänzt es
                ttl=TTL,
                headers={"Urgency": "high" if urgent else "normal"},
            )
            delivered += 1
        except WebPushException as err:
            status = getattr(err.response, "status_code", None)
            hint = " – Abo abgelaufen, in der App neu aktivieren" if status in (404, 410) else ""
            print(f"  Push fehlgeschlagen ({status}){hint}: {err}", file=sys.stderr)
    print(f"  Push „{title}: {body}“ an {delivered} von {len(subs)} Geräten", file=sys.stderr)
    return delivered


if __name__ == "__main__":
    args = sys.argv[1:]
    ok = send(args[0] if args else "Tagesbrief", args[1] if len(args) > 1 else "Test: Push funktioniert ✓")
    sys.exit(0 if ok else 1)
