# 📅 Schichtplaner 2024

Ein fairer Schichtplaner für Teams, entwickelt mit Streamlit. Die App ermöglicht es 20 Mitarbeitenden, ihre Wunsch-Wochentage anzugeben und generiert automatisch einen fairen Jahresschichtplan.

## 🚀 Features

- **Intuitive Eingabe**: Jeder Mitarbeiter kann 3 bevorzugte Wochentage auswählen
- **Fairer Algorithmus**: Gleichmäßige Verteilung der Schichten unter Berücksichtigung der Präferenzen  
- **Übersichtliche Darstellung**: Tabellarische Ansicht mit Filter- und Exportfunktionen
- **Persistente Speicherung**: SQLite-Datenbank für dauerhafte Datenhaltung
- **Responsive Design**: Funktioniert auf Desktop und mobilen Geräten

## 📊 Funktionsweise

1. **Präferenzen sammeln**: Mitarbeiter geben ihre 3 Wunsch-Wochentage ein
2. **Plan generieren**: Algorithmus erstellt fairen Jahresplan (nur Werktage Mo-Fr)
3. **Statistiken anzeigen**: Verteilung der Schichten und Wunscherfüllungsrate
4. **Plan einsehen**: Filterable Übersicht mit CSV-Export

### Fairness-Algorithmus

- Jeder Mitarbeiter bekommt etwa gleich viele Schichten
- Wunschtage werden mit höherer Priorität behandelt
- Zufälliger Faktor sorgt für natürliche Variation
- Gleichmäßige Verteilung über das Jahr

## 🛠️ Lokale Installation

### Voraussetzungen
- Python 3.8 oder höher
- pip

### Setup
```bash
# Repository klonen
git clone https://github.com/Dianjeol/schicht.git
cd schicht

# Dependencies installieren
pip install -r requirements.txt

# App starten
streamlit run app.py
```

Die App ist dann unter `http://localhost:8501` erreichbar.

## ☁️ Deploy auf Streamlit Cloud

### 1. Fork/Clone Repository
- Forken Sie dieses Repository zu Ihrem GitHub-Account
- Oder laden Sie die Dateien in ein neues Repository hoch

### 2. Streamlit Cloud Setup
1. Gehen Sie zu [streamlit.io/cloud](https://streamlit.io/cloud)
2. Melden Sie sich mit Ihrem GitHub-Account an
3. Klicken Sie auf "New app"
4. Wählen Sie Ihr Repository und Branch aus
5. Hauptdatei: `app.py`
6. Klicken Sie auf "Deploy"

### 3. Fertig!
Ihre App ist automatisch unter `https://[app-name].streamlit.app` verfügbar.

## 📁 Projektstruktur

```
schicht/
├── app.py              # Haupt-Streamlit-App
├── requirements.txt    # Python-Dependencies
├── .gitignore         # Git-Ignorierung
└── README.md          # Diese Datei
```

## 🔧 Technische Details

- **Frontend**: Streamlit
- **Backend**: Python mit SQLite
- **Datenbank**: SQLite (automatisch erstellt)
- **Algorithmus**: Gewichtetes Scoring-System für faire Verteilung

### Datenbankschema

```sql
-- Mitarbeiterpräferenzen
CREATE TABLE preferences (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    preferred_days TEXT NOT NULL
);

-- Generierte Schichtpläne  
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    employee_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🎯 Anpassungsmöglichkeiten

- **Anzahl Mitarbeiter**: Variable in der `generate_fair_schedule()` Funktion ändern
- **Wochentage**: Erweiterung um Wochenenden möglich
- **Mehrere Schichten pro Tag**: Datenbankschema erweitern
- **Urlaub/Abwesenheiten**: Zusätzliche Ausschlussdaten implementieren

## 🆘 Support

Bei Fragen oder Problemen:
1. Überprüfen Sie die [Streamlit Cloud Dokumentation](https://docs.streamlit.io/streamlit-cloud)
2. Erstellen Sie ein Issue in diesem Repository
3. Kontaktieren Sie den Entwickler

## 📜 Lizenz

MIT License - Sie können die App frei verwenden und modifizieren.

---

**Entwickelt mit ❤️ und Streamlit** 