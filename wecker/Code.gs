// =====================================================================
//  Tagesbrief – Wecker (läuft bei Google Apps Script)
// =====================================================================
// GitHubs eigener Zeitplan startet Läufe oft Stunden zu spät. Dieses Skript
// stößt die beiden Abläufe deshalb pünktlich von außen an:
//   - Wächter (Eilmeldungen + Morgen-Push): alle 15 Minuten
//   - Briefing: jeden Morgen zwischen 5:00 und 5:30 Uhr
//
// Der GitHub-Schlüssel steht NICHT hier im Code, sondern in den
// Skripteigenschaften unter dem Namen GITHUB_TOKEN.

const REPO = 'hagenbdroyd/tagesbrief';

function weckeWaechter() {
  starte_('waechter.yml');
}

function weckeBriefing() {
  starte_('briefing.yml');
}

function starte_(workflow) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('GITHUB_TOKEN fehlt: Projekteinstellungen → Skripteigenschaften');
  const res = UrlFetchApp.fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${workflow}/dispatches`, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    payload: JSON.stringify({ ref: 'main' }),
    muteHttpExceptions: true,
  });
  // 204 = GitHub hat den Lauf angenommen
  if (res.getResponseCode() !== 204) {
    throw new Error(`GitHub antwortet ${res.getResponseCode()}: ${res.getContentText()}`);
  }
}

// Einmal von Hand ausführen: richtet die beiden Weckzeiten ein (alte werden vorher gelöscht).
function einrichten() {
  ScriptApp.getProjectTriggers().forEach((t) => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('weckeWaechter').timeBased().everyMinutes(15).create();
  ScriptApp.newTrigger('weckeBriefing').timeBased().atHour(5).nearMinute(15).everyDays(1)
    .inTimezone('Europe/Berlin').create();
  weckeWaechter(); // gleich einmal testen
}
