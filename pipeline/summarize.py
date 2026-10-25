"""
=====================================================================
 Tagesbrief – KI-Zusammenfassung
=====================================================================
Gibt der KI alle gesammelten Meldungen, prüft die Antwort und macht
daraus die Bausteine des Briefings (Rubriken, Eilmeldungen, „Mehr“).

Alles, was die KI liefert, wird gegen die echten Meldungen geprüft:
Quellen-IDs, die es nicht gibt, fliegen raus; eine Eilmeldung zählt
nur, wenn wirklich mindestens zwei verschiedene Medien berichten.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from ai import LAST_RESORT, AIError, generate_json
from feeds import FEEDS
from prompt import CHECK_SCHEMA, CHECK_SYSTEM, SCHEMA, SYSTEM

TZ = ZoneInfo("Europe/Berlin")
SECTIONS = [("politik", "Politik & Welt", 6), ("wirtschaft", "Wirtschaft & Börse", 5)]
MAX_SOURCES = 4
MAX_MORE = 24
MAX_TEASER_IN_PROMPT = 220
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
LITE_NOTICE = "Die großen KI-Modelle waren überlastet, dieses Briefing stammt vom kleinen Ersatzmodell. Es kann ungenauer sein – prüf Wichtiges in den Quellen."
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


# ---------- Meldungen für die KI aufbereiten
def format_items(items: list[dict]) -> tuple[str, dict[str, dict]]:
    """Nummeriert die Meldungen ([1], [2], …) – kurze IDs vertut die KI seltener als lange."""
    by_ref: dict[str, dict] = {}
    lines = []
    for n, item in enumerate(items, 1):
        ref = str(n)
        by_ref[ref] = item
        t = datetime.fromisoformat(item["published"]).astimezone(TZ)
        flag = " · MEINUNG" if item["opinion"] else ""
        teaser = item["teaser"][:MAX_TEASER_IN_PROMPT]
        lines.append(
            f"[{ref}] {item['source']} ({item['country']}) · {item['section']} · {t:%d.%m. %H:%M}{flag}\n"
            f"{item['title']}" + (f" — {teaser}" if teaser else "")
        )  # gleicher Ausschnitt wie in source_line(), damit die Faktenprüfung dasselbe sieht
    return "\n\n".join(lines), by_ref


def build_prompt(items: list[dict], now: datetime) -> tuple[str, dict[str, dict]]:
    listing, by_ref = format_items(items)
    header = (
        f"Jetzt ist {WEEKDAYS[now.weekday()]}, {now.day}. {MONTHS[now.month - 1]} {now.year}, {now:%H:%M} Uhr.\n"
        f"Hier sind {len(items)} Meldungen der letzten Stunden:\n\n"
    )
    return header + listing, by_ref


# ---------- Antwort der KI prüfen
# Woran man erkennt, dass die Einordnung ein bestimmtes Medium nennt
OUTLET_PATTERNS = {
    "Tagesschau": r"Tagesschau|\bARD\b",
    "Deutschlandfunk": r"Deutschlandfunk|\bDLF\b",
    "Zeit": r"\b[Dd](?:ie|er) Zeit\b|Zeit Online|\bZEIT\b",
    "FAZ": r"\bFAZ\b|Frankfurter Allgemeine",
    "NZZ": r"\bNZZ\b|Neue Zürcher",
    "Deutsche Welle": r"Deutsche Welle|\bDW\b",
    "Financial Times": r"Financial Times|\bFT\b",
    "New York Times": r"New York Times|\bNYT\b",
    "Politico Europe": r"Politico",
}
OUTLETS = {f["source"]: re.compile(OUTLET_PATTERNS.get(f["source"], re.escape(f["source"]))) for f in FEEDS}
FOREIGN_SOURCES = re.compile(r"Nachrichtenagentur|Agenturen|Agenturmeldung")


def foreign_outlets(text: str, outlets: set[str]) -> list[str]:
    """Medien, die die Einordnung nennt, obwohl sie bei dieser Geschichte gar keine Quelle sind."""
    found = [m.group(0) for m in [FOREIGN_SOURCES.search(text)] if m]
    return found + [name for name, pattern in OUTLETS.items() if name not in outlets and pattern.search(text)]


def perspectives_ok(text: str, outlets: set[str]) -> bool:
    return not foreign_outlets(text, outlets)


def digits(text: str) -> set[str]:
    """Alle Zahlen ohne Trennzeichen („1.000“, „1,000“ → „1000“), damit Deutsch und Englisch vergleichbar sind."""
    return {re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*\d|\d", text)}


def source_entry(item: dict) -> dict:
    return {"name": item["source"], "country": item["country"], "url": item["url"]}


def pick_image(items: list[dict]) -> dict | None:
    """Foto aus der ersten Quelle, die eins hat – mit Angabe, von wem es stammt."""
    for item in items:
        if item.get("image"):
            return {"url": item["image"], "source": item["source"]}
    return None


def check_story(raw: dict, by_ref: dict[str, dict], used: set[str]) -> dict | None:
    items, outlets = [], set()
    for ref in raw.get("sources") or []:
        ref = str(ref).strip(" []")
        item = by_ref.get(ref)
        # unbekannte IDs, Kommentare und doppelte Medien weglassen
        if not item or item["opinion"] or item["source"] in outlets:
            continue
        items.append(item)
        outlets.add(item["source"])
        used.add(ref)
        if len(items) == MAX_SOURCES:
            break
    headline, summary = (raw.get("headline") or "").strip(), (raw.get("summary") or "").strip()
    if not items or not headline or not summary:
        return None
    return {
        "headline": headline,
        "summary": summary,
        "perspectives": (raw.get("perspectives") or "").strip() or None,
        "sources": [source_entry(i) for i in items],
        "time": min(i["published"] for i in items),
        "image": pick_image(items),
        "breaking": bool(raw.get("breaking")) and len(outlets) >= 2,
        "_items": items,
    }


def source_line(item: dict) -> str:
    """Genau der Text, den die KI von einer Meldung zu sehen bekommt."""
    teaser = item["teaser"][:MAX_TEASER_IN_PROMPT]
    return f"{item['source']} ({item['country']}): {item['title']}" + (f" — {teaser}" if teaser else "")


def majority_section(items: list[dict], fallback: str) -> str:
    """Die KI sortiert meist richtig ein. Nur wenn alle Quellen (mindestens zwei) aus der anderen Rubrik kommen,
    wird umsortiert – die Feed-Rubriken allein sind zu grob (z. B. SpaceX-Finanzierung im Politik-Feed)."""
    sections = Counter(i["section"] for i in items)
    if len(items) >= 2 and len(sections) == 1:
        return next(iter(sections))
    return fallback


# ---------- Zweiter Durchgang: Faktenprüfung
def factcheck(stories: list[dict], model: str) -> dict | None:
    """Lässt jede Geschichte gegen genau ihre Quellen prüfen und übernimmt die Korrekturen."""
    blocks = []
    for n, s in enumerate(stories, 1):
        sources = "\n".join(f"{k}. {source_line(i)}" for k, i in enumerate(s["_items"], 1))
        blocks.append(
            f"### Geschichte {n}\nSchlagzeile: {s['headline']}\nZusammenfassung: {s['summary']}\n"
            f"Einordnung: {s['perspectives'] or ''}\nMeldungen:\n{sources}"
        )
    try:
        answer, _ = generate_json(CHECK_SYSTEM, "\n\n".join(blocks), CHECK_SCHEMA, start_with=model)
    except AIError as err:
        print(f"  Faktenprüfung ausgefallen, Texte bleiben ungeprüft: {err}", file=sys.stderr)
        return None
    checked = 0
    for result in answer.get("stories") or []:
        n = result.get("n")
        if not isinstance(n, int) or not 1 <= n <= len(stories):
            continue
        story = stories[n - 1]
        checked += 1
        for issue in result.get("issues") or []:
            print(f"  Faktenprüfung „{story['headline']}“: {issue}", file=sys.stderr)
        # Meldungen, die zu einem anderen Ereignis gehören, als Quelle streichen (mindestens eine bleibt)
        unrelated = {k for k in result.get("unrelated") or [] if isinstance(k, int)}
        keep = [k for k in range(len(story["_items"])) if k + 1 not in unrelated]
        if keep and len(keep) < len(story["_items"]):
            for k in sorted(unrelated):
                if 1 <= k <= len(story["_items"]):
                    print(f"  Quelle gehört nicht dazu, entfernt: {story['_items'][k - 1]['title']}", file=sys.stderr)
            story["_items"] = [story["_items"][k] for k in keep]
            story["sources"] = [story["sources"][k] for k in keep]
        for field in ("headline", "summary", "perspectives"):
            text = (result.get(field) or "").strip()
            if text or field == "perspectives":
                story[field] = text or None
    print(f"  Faktenprüfung: {checked} von {len(stories)} Geschichten geprüft.", file=sys.stderr)
    return answer


def final_checks(story: dict) -> None:
    """Letzte Kontrolle ohne KI: fremde Medien in der Einordnung, Zahlen ohne Beleg."""
    outlets = {i["source"] for i in story["_items"]}
    foreign = foreign_outlets(story["perspectives"] or "", outlets)
    if foreign:
        print(f"  Einordnung verworfen (nennt {', '.join(foreign)}, Quellen sind {', '.join(sorted(outlets))}): "
              f"{story['headline']}\n    „{story['perspectives']}“", file=sys.stderr)
        story["perspectives"] = None
    text = f"{story['headline']} {story['summary']} {story['perspectives'] or ''}"
    unknown = digits(text) - digits(" ".join(source_line(i) for i in story["_items"]))
    if unknown:
        print(f"  Achtung, Zahl(en) {sorted(unknown)} nicht in den Quellen: {story['headline']}", file=sys.stderr)


def summarize(items: list[dict], now: datetime) -> dict:
    """Erstellt die KI-Teile des Briefings. Wirft AIError, wenn die KI nicht erreichbar ist."""
    prompt, by_ref = build_prompt(items, now)
    answer, model = generate_json(SYSTEM, prompt, SCHEMA)

    used: set[str] = set()
    stories = []
    for section_id, _, limit in SECTIONS:
        for raw in (answer.get(section_id) or [])[:limit]:
            story = check_story(raw, by_ref, used)
            if story:
                story["section"] = majority_section(story["_items"], section_id)
                stories.append(story)

    check = factcheck(stories, model)

    sections = [{"id": sid, "title": title, "items": []} for sid, title, _ in SECTIONS]
    by_section = {s["id"]: s for s in sections}
    breaking = []
    for story in stories:
        final_checks(story)
        story["image"] = pick_image(story["_items"])  # die Faktenprüfung hat evtl. Quellen entfernt
        story["time"] = min(i["published"] for i in story.pop("_items"))
        target = by_section[story.pop("section")]
        # nach der Faktenprüfung nochmal: Eilmeldung nur mit mindestens zwei verschiedenen Medien
        if story.pop("breaking") and len(story["sources"]) >= 2:
            breaking.append({"id": f"b{len(breaking) + 1}", **story})
        else:
            target["items"].append({"id": f"{target['id'][0]}{len(target['items']) + 1}", **story})

    more = []
    for ref in answer.get("more") or []:
        ref = str(ref).strip(" []")
        item = by_ref.get(ref)
        if not item or ref in used:
            continue
        used.add(ref)
        more.append({
            "section": item["section"],
            "headline": item["title"],
            "source": item["source"],
            "country": item["country"],
            "url": item["url"],
            "time": item["published"],
            "opinion": item["opinion"],
            "image": item.get("image"),
        })
        if len(more) == MAX_MORE:
            break

    if sum(len(s["items"]) for s in sections) + len(breaking) < 3:
        raise ValueError("Die KI hat zu wenige brauchbare Geschichten geliefert")

    return {
        "breaking": breaking,
        "sections": sections,
        "more": more,
        "push": (answer.get("push") or "").strip() or None,
        "aiModel": model,
        "notice": LITE_NOTICE if model == LAST_RESORT else None,
        "_raw": {"model": model, "answer": answer, "factcheck": check},  # Rohantworten zum Nachschauen
    }
