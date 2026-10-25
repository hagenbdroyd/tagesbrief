"""
=====================================================================
 Tagesbrief – News-Sammler
=====================================================================
Holt alle Feeds aus feeds.py, räumt die Meldungen auf (HTML raus,
Tracking-Parameter raus, Doppelte raus) und gibt sie einheitlich zurück.

Nur Python-Standardbibliothek, damit es überall ohne Installation läuft.
Direkt aufrufen zum Testen:  python3 pipeline/collect.py
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from feeds import FEEDS

USER_AGENT = "Mozilla/5.0 (compatible; Tagesbrief/1.0; private news reader)"
TIMEOUT = 15
MAX_TEASER = 320
TRACKING_PARAMS = re.compile(r"^(utm_|at_|maca$|ref$|cmpid$|ns_)", re.I)
# Manche Medien liefern nur kleine Vorschaubilder – über die Adresse lässt sich eine größere Version anfordern
IMAGE_UPGRADES = [
    (re.compile(r"(ichef\.bbci\.co\.uk/ace/standard/)\d+/"), r"\g<1>800/"),
    (re.compile(r"(img\.zeit\.de/.+/)(?:original|wide)__\d+x\d+$"), r"\g<1>wide__820x461"),
    (re.compile(r"(images\.tagesschau\.de/[^?]+\?width=)\d+"), r"\g<1>1024"),
    (re.compile(r"(img-msp-prod\.nzz\.ch/[^?]+)\?.*"), r"\1?width=900&height=900&fit=bounds"),
]
IMG_TAG = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
OPINION_HINTS = re.compile(r"/(meinung|kommentar[e]?|opinion|commentisfree|leitartikel)/|^(kommentar|meinung|leitartikel|opinion)\b", re.I)


# ---------- Hilfsfunktionen
def local(tag: str) -> str:
    """Tag-Name ohne XML-Namespace ({http://...}title → title)."""
    return tag.rsplit("}", 1)[-1].lower()


def clean_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(html.unescape(text))  # manche Feeds sind doppelt kodiert
    return re.sub(r"\s+", " ", text).strip()


def shorten(text: str, limit: int = MAX_TEASER) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:–-") + " …"


def clean_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)  # RSS: "Sun, 25 Oct 2026 05:15:52 GMT"
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # RDF/Atom: "2026-10-25T16:12:00Z"
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def find_image(node: ET.Element, html_text: str | None) -> str | None:
    """Bestes Foto einer Meldung: größtes media:content/thumbnail, sonst Anhang, sonst erstes <img> im Text."""
    media, enclosure = [], None
    for child in node:
        name, url = local(child.tag), child.get("url")
        if not url:
            continue
        if name in ("content", "thumbnail") and child.get("medium", "image") == "image" \
                and not child.get("type", "image/").startswith(("video", "audio")):
            media.append((int(child.get("width") or 0), url))
        elif name == "enclosure" and child.get("type", "").startswith("image"):
            enclosure = enclosure or url
    if media:
        image = max(media)[1]
    elif enclosure:
        image = enclosure
    else:
        found = IMG_TAG.search(html_text or "")
        image = html.unescape(found.group(1)) if found else None
    if not image or not image.startswith("http"):
        return None
    for pattern, replacement in IMAGE_UPGRADES:
        image = pattern.sub(replacement, image)
    return image


def section_for(feed: dict, url: str) -> str:
    if feed["section"] != "auto":
        return feed["section"]
    return "politik" if "/politik/" in urlsplit(url).path else "wirtschaft"


# ---------- Ein Feed
def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return res.read()


def parse_feed(feed: dict, data: bytes) -> list[dict]:
    root = ET.fromstring(data)
    entries = []
    for node in root.iter():
        if local(node.tag) not in ("item", "entry"):
            continue
        fields: dict[str, str] = {}
        for child in node:
            name = local(child.tag)
            if name == "link" and not (child.text or "").strip():
                if child.get("rel", "alternate") == "alternate" and child.get("href"):
                    fields.setdefault("link", child.get("href"))  # Atom
                continue
            if name not in fields and child.text and child.text.strip():
                fields[name] = child.text

        title = clean_text(fields.get("title"))
        link = (fields.get("link") or "").strip()
        # Leer-Titel wie „Here's the latest.“ (Liveblog-Updates) sagen nichts aus
        if len(title.split()) < 4 or not link.startswith("http"):
            continue
        url = clean_url(link)
        published = parse_date(fields.get("pubdate") or fields.get("date") or fields.get("published") or fields.get("updated"))
        teaser = clean_text(fields.get("description") or fields.get("summary") or fields.get("encoded"))
        entries.append({
            "id": hashlib.sha1(url.encode()).hexdigest()[:12],
            "title": title,
            "teaser": shorten(teaser) if teaser != title else "",
            "url": url,
            "source": feed["source"],
            "country": feed["country"],
            "lang": feed["lang"],
            "section": section_for(feed, url),
            "published": published.isoformat(timespec="seconds") if published else None,
            "opinion": bool(OPINION_HINTS.search(urlsplit(url).path) or OPINION_HINTS.search(title)),
            "image": find_image(node, fields.get("encoded") or fields.get("description")),
        })
    return entries


def load_feed(feed: dict) -> tuple[dict, list[dict], str | None]:
    error = None
    for _ in range(2):  # zweiter Versuch, falls der Server kurz hakt
        try:
            return feed, parse_feed(feed, fetch(feed["url"])), None
        except Exception as err:  # ein kaputter Feed darf den Rest nicht aufhalten
            error = f"{type(err).__name__}: {err}"
    return feed, [], error


# ---------- Alle Feeds
def collect(hours: int = 36) -> dict:
    """Alle Meldungen der letzten `hours` Stunden, neueste zuerst, ohne Doppelte."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(load_feed, FEEDS))

    items: list[dict] = []
    seen_urls: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    report = []
    for feed, entries, error in results:
        kept = 0
        for item in entries:
            if not item["published"] or datetime.fromisoformat(item["published"]) < cutoff:
                continue
            title_key = (item["source"], re.sub(r"\W+", "", item["title"].lower()))
            if item["url"] in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(item["url"])
            seen_titles.add(title_key)
            items.append(item)
            kept += 1
        report.append({"source": feed["source"], "section": feed["section"], "url": feed["url"], "found": len(entries), "kept": kept, "error": error})

    items.sort(key=lambda i: i["published"], reverse=True)
    return {
        "collectedAt": now.isoformat(timespec="seconds"),
        "windowHours": hours,
        "feeds": report,
        "items": items,
    }


if __name__ == "__main__":
    news = collect()
    for r in news["feeds"]:
        status = f"FEHLER {r['error']}" if r["error"] else f"{r['kept']:3d} von {r['found']:3d}"
        print(f"{r['source']:<16} {r['section']:<10} {status}", file=sys.stderr)
    print(f"\n{len(news['items'])} Meldungen aus den letzten {news['windowHours']} Stunden", file=sys.stderr)
    json.dump(news, sys.stdout, ensure_ascii=False, indent=2)
