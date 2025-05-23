# Schichtplaner

**Ein intelligenter Schichtplaner für faire Arbeitsverteilung**

[Live Demo](https://schicht.streamlit.app/)

## Übersicht

Der Schichtplaner automatisiert die faire Verteilung von Arbeitsschichten basierend auf Mitarbeiterpräferenzen. Das System berücksichtigt Wochentag-Präferenzen, Urlaubszeiten und gesetzliche Feiertage in Berlin.

## Features

- **Präferenz-basierte Planung**: Mitarbeiter wählen bis zu 3 bevorzugte Wochentage
- **Faire Verteilung**: Algorithmus sorgt für ausgeglichene Schichtverteilung
- **Feiertags-Integration**: Automatische Berücksichtigung Berliner Feiertage
- **Flexibler Export**: CSV und PDF Export für verschiedene Zeiträume
- **Responsive Design**: Optimiert für Desktop und Mobile
- **Datenbeständigkeit**: SQLite-Datenbank für lokale Datenspeicherung

## Installation

### Voraussetzungen
- Python 3.8+
- pip

### Setup
```bash
git clone https://github.com/Dianjeol/schicht.git
cd schicht
pip install -r requirements.txt
streamlit run app.py
```

Die Anwendung ist anschließend unter `http://localhost:8501` erreichbar.

## Deployment

### Streamlit Cloud
1. Repository auf GitHub forken oder hochladen
2. Bei [streamlit.io/cloud](https://streamlit.io/cloud) anmelden
3. "New app" wählen und Repository verbinden
4. Hauptdatei: `app.py`
5. Deployment starten

Die App ist automatisch unter `https://[app-name].streamlit.app` verfügbar.

## Projektstruktur

```
schicht/
├── app.py              # Hauptanwendung
├── requirements.txt    # Python-Dependencies
├── .gitignore         # Git-Ausschlüsse
└── README.md          # Dokumentation
```

## Technologie-Stack

- **Frontend**: Streamlit
- **Backend**: Python mit SQLite
- **Datenbank**: SQLite (automatisch erstellt)
- **Feiertage**: holidays Library für Berlin
- **Export**: pandas (CSV), reportlab (PDF)

## Datenbank-Schema

```sql
-- Mitarbeiterpräferenzen
CREATE TABLE preferences (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    preferred_days TEXT NOT NULL
);

-- Schichtpläne
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    employee_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Nicht-Verfügbarkeiten
CREATE TABLE unavailability (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    date TEXT,
    weekday TEXT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Algorithmus

Der Schichtplanungsalgorithmus funktioniert nach folgenden Prinzipien:

1. **Round-Robin Rotation**: Alle Mitarbeiter kommen gleichmäßig zum Zug
2. **Präferenz-Optimierung**: Bevorzugte Wochentage werden priorisiert
3. **Verfügbarkeits-Prüfung**: Urlaub und Feiertage werden ausgeschlossen
4. **Fairness-Garantie**: Gleichmäßige Verteilung über alle Mitarbeiter

## Erweiterungsmöglichkeiten

- Anpassung der Teamgröße in `generate_fair_schedule()`
- Wochenend-Schichten (Samstag/Sonntag)
- Mehrfach-Schichten pro Tag
- Integration weiterer Bundesland-Feiertage
- E-Mail-Benachrichtigungen
- API-Integration für externe Systeme

## Support

- [Streamlit Cloud Dokumentation](https://docs.streamlit.io/streamlit-cloud)
- Issues in diesem Repository erstellen

## Lizenz

MIT License - siehe LICENSE Datei für Details.

---

**Entwickelt für effiziente Schichtplanung mit Python und Streamlit** 