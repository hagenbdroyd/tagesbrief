# Tagesbrief

Mein persönliches News-Briefing fürs iPhone – als Ersatz für Instagram.

Jeden Morgen sammelt ein Programm die Meldungen seriöser Medien aus Deutschland, der Schweiz,
Großbritannien, den USA und der EU. Eine KI (Google Gemini) wählt die wichtigsten Geschichten zu
**Politik & Welt** und **Wirtschaft & Börse** aus, fasst sie auf Deutsch zusammen und zeigt, wie
unterschiedlich die Medien berichten. Ein zweiter KI-Durchgang prüft jede Aussage gegen die Quellen.

- `index.html`, `app.js`, `styles.css` – die App (Web-App für den Homescreen)
- `pipeline/feeds.py` – welche Medien gelesen werden
- `pipeline/prompt.py` – der Auftrag an die KI, inklusive Eilmeldungs-Regeln
- `pipeline/build.py` – erstellt `data/briefing.json`
- `.github/workflows/briefing.yml` – läuft jeden Morgen automatisch

Die Zusammenfassungen schreibt eine KI – Fehler sind möglich. Jede Meldung verlinkt auf die Originalquelle.
