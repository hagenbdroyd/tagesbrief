# =====================================================================
#  Tagesbrief – Quellen
# =====================================================================
# section: "politik" | "wirtschaft" | "auto" (Rubrik aus dem Link ablesen)
# country: Herkunft des Mediums – steht in der App neben der Quelle,
#          damit du einordnen kannst, wer berichtet
# lang:    Sprache des Feeds (die KI fasst später alles auf Deutsch zusammen)

FEEDS = [
    # ---------- Politik & Welt
    {"source": "Tagesschau", "country": "DE", "lang": "de", "section": "politik", "url": "https://www.tagesschau.de/inland/index~rss2.xml"},
    {"source": "Tagesschau", "country": "DE", "lang": "de", "section": "politik", "url": "https://www.tagesschau.de/ausland/index~rss2.xml"},
    {"source": "Deutschlandfunk", "country": "DE", "lang": "de", "section": "politik", "url": "https://www.deutschlandfunk.de/politikportal-100.rss"},
    {"source": "Spiegel", "country": "DE", "lang": "de", "section": "politik", "url": "https://www.spiegel.de/politik/index.rss"},
    {"source": "Spiegel", "country": "DE", "lang": "de", "section": "politik", "url": "https://www.spiegel.de/ausland/index.rss"},
    {"source": "Zeit", "country": "DE", "lang": "de", "section": "politik", "url": "https://newsfeed.zeit.de/politik/index"},
    {"source": "FAZ", "country": "DE", "lang": "de", "section": "politik", "url": "https://www.faz.net/rss/aktuell/politik/"},
    {"source": "NZZ", "country": "CH", "lang": "de", "section": "politik", "url": "https://www.nzz.ch/international.rss"},
    {"source": "Deutsche Welle", "country": "DE", "lang": "en", "section": "politik", "url": "https://rss.dw.com/rdf/rss-en-world"},
    {"source": "BBC", "country": "UK", "lang": "en", "section": "politik", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"source": "Guardian", "country": "UK", "lang": "en", "section": "politik", "url": "https://www.theguardian.com/world/rss"},
    {"source": "Financial Times", "country": "UK", "lang": "en", "section": "politik", "url": "https://www.ft.com/world?format=rss"},
    {"source": "New York Times", "country": "US", "lang": "en", "section": "politik", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"source": "New York Times", "country": "US", "lang": "en", "section": "politik", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml"},
    {"source": "Politico Europe", "country": "EU", "lang": "en", "section": "politik", "url": "https://www.politico.eu/feed/"},

    # ---------- Wirtschaft & Börse
    {"source": "Tagesschau", "country": "DE", "lang": "de", "section": "wirtschaft", "url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml"},
    {"source": "Deutschlandfunk", "country": "DE", "lang": "de", "section": "wirtschaft", "url": "https://www.deutschlandfunk.de/wirtschaft-106.rss"},
    {"source": "Spiegel", "country": "DE", "lang": "de", "section": "wirtschaft", "url": "https://www.spiegel.de/wirtschaft/index.rss"},
    {"source": "Zeit", "country": "DE", "lang": "de", "section": "wirtschaft", "url": "https://newsfeed.zeit.de/wirtschaft/index"},
    {"source": "FAZ", "country": "DE", "lang": "de", "section": "wirtschaft", "url": "https://www.faz.net/rss/aktuell/wirtschaft/"},
    {"source": "FAZ", "country": "DE", "lang": "de", "section": "wirtschaft", "url": "https://www.faz.net/rss/aktuell/finanzen/"},
    {"source": "Handelsblatt", "country": "DE", "lang": "de", "section": "auto", "url": "https://www.handelsblatt.com/contentexport/feed/schlagzeilen"},
    {"source": "Handelsblatt", "country": "DE", "lang": "de", "section": "wirtschaft", "url": "https://www.handelsblatt.com/contentexport/feed/finanzen"},
    {"source": "NZZ", "country": "CH", "lang": "de", "section": "wirtschaft", "url": "https://www.nzz.ch/wirtschaft.rss"},
    {"source": "Deutsche Welle", "country": "DE", "lang": "en", "section": "wirtschaft", "url": "https://rss.dw.com/rdf/rss-en-bus"},
    {"source": "BBC", "country": "UK", "lang": "en", "section": "wirtschaft", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"source": "Guardian", "country": "UK", "lang": "en", "section": "wirtschaft", "url": "https://www.theguardian.com/business/rss"},
    {"source": "Financial Times", "country": "UK", "lang": "en", "section": "wirtschaft", "url": "https://www.ft.com/markets?format=rss"},
    {"source": "New York Times", "country": "US", "lang": "en", "section": "wirtschaft", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"},
    {"source": "CNBC", "country": "US", "lang": "en", "section": "wirtschaft", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
]
