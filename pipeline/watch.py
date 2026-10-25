"""
=====================================================================
 Tagesbrief – Wächter (läuft etwa alle 15 Minuten auf GitHub)
=====================================================================
1. Morgen-Push: ab 7 Uhr einmal am Tag, sobald das heutige Briefing fertig ist.
2. Eilmeldungen: Passiert gerade etwas, das nach deinen Regeln eine Eilmeldung
   ist und das mindestens zwei Medien melden? Dann Push.
Gemerkt wird alles in data/state.json – die App zeigt die Eilmeldungen daraus oben an.

Aufruf:  python pipeline/watch.py          normaler Durchlauf
         python pipeline/watch.py --test   nur einen Test-Push schicken
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ai import AIError, generate_json
from build import keywords, same_story
from collect import collect
from prompt import BREAKING_SCHEMA, BREAKING_SYSTEM
from push import send
from summarize import build_prompt, check_story, final_checks

ROOT = Path(__file__).resolve().parent.parent
BRIEFING = ROOT / "data" / "briefing.json"
STATE = ROOT / "data" / "state.json"
TZ = ZoneInfo("Europe/Berlin")

MORNING_HOUR = 7  # ab dann kommt der Morgen-Push
MORNING_LATEST = 12  # ist bis dahin kein Briefing da, fällt der Morgen-Push aus
WINDOW_HOURS = 3  # so weit zurück schaut der Wächter in die Feeds
FRESH_MINUTES = 45  # die KI wird nur gefragt, wenn in dieser Zeit eine Geschichte bei zwei Medien neu auftaucht
KEEP_HOURS = 48  # so lange merkt er sich verschickte Eilmeldungen


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"updatedAt": None, "morningPush": None, "breaking": []}


def save_state(state: dict, now: datetime) -> None:
    cutoff = now - timedelta(hours=KEEP_HOURS)
    state["breaking"] = [b for b in state["breaking"] if datetime.fromisoformat(b["pushedAt"]) >= cutoff]
    state["updatedAt"] = now.isoformat(timespec="seconds")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------- 1. Morgen-Push
def morning_push(state: dict, now: datetime) -> bool:
    today = now.date().isoformat()
    if not MORNING_HOUR <= now.hour < MORNING_LATEST or state.get("morningPush") == today:
        return False
    briefing = json.loads(BRIEFING.read_text(encoding="utf-8"))
    if briefing["date"] != today:
        print("Morgen-Push wartet: das heutige Briefing ist noch nicht fertig", file=sys.stderr)
        return False
    stories = [i for s in briefing["sections"] for i in s["items"]]
    top = briefing.get("push") or (stories[0]["headline"] if stories else "Die neuesten Schlagzeilen sind da")
    body = f"{top} · und {len(stories) - 1} weitere Themen" if len(stories) > 1 else top
    send("Dein Tagesbrief", body, tag=f"morgen-{today}")
    state["morningPush"] = today  # auch wenn kein Gerät erreichbar war: nicht alle 15 Minuten nochmal
    return True


# ---------- 2. Eilmeldungen
def fresh_story_in_two_outlets(items: list[dict], now: datetime) -> bool:
    """Günstige Vorprüfung ohne KI: Ist eine Geschichte frisch aufgetaucht, über die schon zwei Medien berichten?"""
    fresh = now - timedelta(minutes=FRESH_MINUTES)
    words = [(item, keywords(item["title"])) for item in items]
    for item, kw in words:
        if datetime.fromisoformat(item["published"]) < fresh:
            continue
        if any(other["source"] != item["source"] and same_story(kw, okw) for other, okw in words):
            return True
    return False


def already_sent(story: dict, state: dict) -> bool:
    urls = {s["url"] for s in story["sources"]}
    kw = keywords(story["headline"])
    for sent in state["breaking"]:
        if urls & {s["url"] for s in sent["sources"]} or same_story(kw, keywords(sent["headline"])):
            return True
    return False


def check_breaking(state: dict, items: list[dict], now: datetime) -> list[dict]:
    prompt, by_ref = build_prompt(items, now)
    sent = [f"- {datetime.fromisoformat(b['pushedAt']).astimezone(TZ):%d.%m. %H:%M}: {b['headline']}" for b in state["breaking"]]
    prompt += "\n\nSchon verschickte Eilmeldungen:\n" + ("\n".join(sent) if sent else "keine")

    # nur die starken Modelle: lieber eine Viertelstunde später als ein falscher Alarm
    answer, model = generate_json(BREAKING_SYSTEM, prompt, BREAKING_SCHEMA, last_resort=False)
    found, used = [], set()
    for raw in answer.get("breaking") or []:
        story = check_story(raw, by_ref, used)
        if not story or len(story["sources"]) < 2:
            continue  # Regel: mindestens zwei verschiedene Medien
        final_checks(story)
        if already_sent(story, state):
            print(f"Schon verschickt: {story['headline']}", file=sys.stderr)
            continue
        found.append({
            "id": f"e{now:%Y%m%d%H%M}{len(found)}",
            "time": min(i["published"] for i in story["_items"]),
            "pushedAt": now.isoformat(timespec="seconds"),
            "headline": story["headline"],
            "summary": story["summary"],
            "reason": (raw.get("reason") or "").strip(),
            "sources": story["sources"],
            "image": story["image"],
            "model": model,
        })
    return found


def main() -> None:
    if "--test" in sys.argv or os.environ.get("TEST_PUSH") == "true":
        sys.exit(0 if send("Tagesbrief", "Test: Push funktioniert ✓", tag="test") else 1)

    now = datetime.now(TZ)
    state = load_state()
    changed = morning_push(state, now)

    news = collect(hours=WINDOW_HOURS)
    if not fresh_story_in_two_outlets(news["items"], now):
        print(f"{len(news['items'])} Meldungen, nichts Frisches bei zwei Medien – KI wird nicht gefragt.", file=sys.stderr)
    else:
        try:
            for b in check_breaking(state, news["items"], now):
                print(f"EILMELDUNG: {b['headline']} ({b['reason']})", file=sys.stderr)
                send("Eilmeldung", b["headline"], tag=b["id"], urgent=True)
                state["breaking"].append(b)
                changed = True
        except AIError as err:
            print(f"KI gerade nicht erreichbar, nächster Versuch in 15 Minuten: {err}", file=sys.stderr)

    if changed:
        save_state(state, now)


if __name__ == "__main__":
    main()
