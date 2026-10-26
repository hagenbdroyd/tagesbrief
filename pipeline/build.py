"""
=====================================================================
 Tagesbrief – Briefing bauen
=====================================================================
Sammelt die News, lässt die KI das Briefing schreiben und speichert
es in data/briefing.json, das die App anzeigt.

Ist die KI nicht erreichbar, gibt es trotzdem ein Briefing: dann eben
nur mit den neuesten Schlagzeilen, ohne Zusammenfassung.

Aufruf:  python3 pipeline/build.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai import LAST_RESORT, AIError
from collect import collect
from summarize import SECTIONS, summarize

ROOT = Path(__file__).resolve().parent.parent
BRIEFING = ROOT / "data" / "briefing.json"
NEWS_OUT = ROOT / "pipeline" / "out" / "news.json"  # Rohdaten zum Nachschauen
TZ = ZoneInfo("Europe/Berlin")
WINDOW_HOURS = 24
FALLBACK_NOTICE = "Die KI war gerade nicht erreichbar. Hier deshalb nur die neuesten Schlagzeilen, ohne Zusammenfassung."

MORE_TARGET = 20  # so viele weitere Schlagzeilen sollen es mindestens sein
MORE_PER_SECTION = 15
MORE_PER_SOURCE = 2  # damit nicht eine Zeitung die ganze Liste füllt

STOPWORDS = set("""
    nach über unter gegen wird werden soll sollen sind gibt hat haben kann will wieder mehr auch noch beim einem einer eines
    sich nicht ohne erst zwei drei neue neuer neues jetzt heute schon diese dieser dieses dass weil wenn aber oder
    with from after over into about will would their this that what when have has been more amid says said than
""".split())


def keywords(title: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z]{4,}", plain) if w not in STOPWORDS}


def same_story(a: set[str], b: set[str]) -> bool:
    """Grobe Ähnlichkeit: mindestens zwei gemeinsame Stichwörter, die einen guten Teil der kürzeren Schlagzeile ausmachen."""
    shared = len(a & b)
    return shared >= 3 or (shared == 2 and shared / max(1, min(len(a), len(b))) >= 0.25)


def pick_more(items: list[dict], section_ids: list[str], known_titles: list[str] = ()) -> list[dict]:
    """Neueste Schlagzeilen ohne KI. known_titles: Geschichten, die schon im Briefing stehen."""
    picked = []
    stories: list[set[str]] = [keywords(t) for t in known_titles]  # gleiche Geschichte nur einmal, egal wie viele Medien berichten
    for section in section_ids:
        per_source: Counter = Counter()
        count = 0
        for item in items:  # schon nach Zeit sortiert, neueste zuerst
            if item["section"] != section or per_source[item["source"]] >= MORE_PER_SOURCE:
                continue
            words = keywords(item["title"])
            if any(same_story(words, s) for s in stories):
                continue
            stories.append(words)
            per_source[item["source"]] += 1
            picked.append({
                "section": section,
                "headline": item["title"],
                "source": item["source"],
                "country": item["country"],
                "url": item["url"],
                "time": item["published"],
                "opinion": item["opinion"],
                "image": item.get("image"),
            })
            count += 1
            if count == MORE_PER_SECTION:
                break
    return sorted(picked, key=lambda h: h["time"], reverse=True)


def drop_known_breaking(briefing: dict) -> None:
    """Was der Wächter schon als Eilmeldung verschickt hat, zeigt die App ohnehin oben an – nicht doppelt."""
    state = ROOT / "data" / "state.json"
    known = json.loads(state.read_text(encoding="utf-8"))["breaking"] if state.exists() else []

    def is_known(b: dict) -> bool:
        urls = {s["url"] for s in b["sources"]}
        return any(urls & {s["url"] for s in k["sources"]} or same_story(keywords(b["headline"]), keywords(k["headline"]))
                   for k in known)

    briefing["breaking"] = [b for b in briefing["breaking"] if not is_known(b)]


def top_up_more(briefing: dict, items: list[dict]) -> None:
    """Liefert die KI zu wenige weitere Schlagzeilen, mit den neuesten (ohne Doppelte) auffüllen."""
    missing = MORE_TARGET - len(briefing["more"])
    if missing <= 0:
        return
    stories = briefing["breaking"] + [i for s in briefing["sections"] for i in s["items"]]
    used = {src["url"] for story in stories for src in story["sources"]} | {h["url"] for h in briefing["more"]}
    known = [i["title"] for i in items if i["url"] in used]
    extra = pick_more([i for i in items if i["url"] not in used], [s["id"] for s in briefing["sections"]], known)
    briefing["more"] += extra[:missing]


def already_done_today(now: datetime) -> bool:
    """Gibt es heute schon ein gutes Briefing (ab 4 Uhr, von einem starken Modell)? Dann nicht überschreiben –
    wichtig, weil GitHub geplante Läufe manchmal stundenlang verschiebt."""
    if not BRIEFING.exists():
        return False
    old = json.loads(BRIEFING.read_text(encoding="utf-8"))
    made = datetime.fromisoformat(old["generatedAt"]).astimezone(TZ)
    return made.date() == now.date() and made.hour >= 4 and old.get("aiModel") not in (None, LAST_RESORT)


def main() -> None:
    if "--skip-if-fresh" in sys.argv and already_done_today(datetime.now(TZ)):
        print("Heute gibt es schon ein gutes Briefing – nichts zu tun.")
        return

    news = collect(hours=WINDOW_HOURS)
    NEWS_OUT.parent.mkdir(parents=True, exist_ok=True)
    NEWS_OUT.write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [f"{f['source']} ({f['url']})" for f in news["feeds"] if f["error"]]
    print(f"{len(news['items'])} Meldungen aus den letzten {WINDOW_HOURS} Stunden gesammelt.")
    if failed:
        print("Nicht erreichbar:", ", ".join(failed))

    now = datetime.now(TZ)
    briefing = {
        "date": now.date().isoformat(),
        "generatedAt": now.isoformat(timespec="seconds"),
        "notice": None,
        "aiModel": None,
        "push": None,
        "breaking": [],
        "sections": [{"id": sid, "title": title, "items": []} for sid, title, _ in SECTIONS],
        "more": [],
    }
    try:
        result = summarize(news["items"], now)
        (NEWS_OUT.parent / "ki-antworten.json").write_text(json.dumps(result.pop("_raw"), ensure_ascii=False, indent=2), encoding="utf-8")
        briefing.update(result)
        drop_known_breaking(briefing)
        top_up_more(briefing, news["items"])
        stories = sum(len(s["items"]) for s in briefing["sections"])
        print(f"KI ({briefing['aiModel']}): {stories} Geschichten, {len(briefing['breaking'])} Eilmeldungen, {len(briefing['more'])} weitere Schlagzeilen.")
    except (AIError, ValueError) as err:
        print(f"KI nicht verfügbar, nur Schlagzeilen: {err}", file=sys.stderr)
        briefing.update(notice=FALLBACK_NOTICE, more=pick_more(news["items"], [sid for sid, _, _ in SECTIONS]))

    BRIEFING.write_text(json.dumps(briefing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
