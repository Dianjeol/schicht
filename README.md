# 🌟✨ Schichtplaner 2025 ✨🌟  
*Mit Liebe für faire Teams entwickelt* 💝

> 🎭 **Live erleben:** [schicht.streamlit.app](https://schicht.streamlit.app/) 🚀  
> Ein zauberhafter Schichtplaner für harmonische Teams! 🤗

Dieser liebevoll gestaltete Schichtplaner bringt Fairness und Freude in Ihren Arbeitsalltag. Mitarbeitende können ihre Herzenswünsche für Wochentage eingeben, und unser magischer Algorithmus erstellt einen perfekt ausbalancierten Jahresschichtplan! ✨💫

## 🎨💖 Magische Features

- 🎪 **Intuitive Magie**: Jeder Mitarbeiter wählt liebevoll 3 Herzenswünsche für Wochentage
- 🧚‍♀️ **Fairness-Zauber**: Unser Algorithm zaubert perfekte Balance zwischen allen Wünschen  
- 🎭 **Wunderschöne Anzeige**: Elegant gefilterte Tabellen mit CSV-Export-Liebe
- 💾 **Ewige Erinnerungen**: SQLite-Datenbank bewahrt alle Träume sicher auf
- 📱💻 **Überall Zuhause**: Responsive Design für alle Ihre liebsten Geräte
- 🌈 **Deutscher Charme**: Vollständig in deutscher Sprache mit Herz

## 🎼✨ Die Symphonie der Fairness

1. 💝 **Wünsche sammeln**: Jeder Mitarbeiter teilt seine 3 Lieblings-Wochentage mit uns
2. 🎯 **Zauber entfalten**: Unser Algorithmus komponiert einen harmonischen Jahresplan (Mo-Fr Werktage)
3. 📈 **Wunder betrachten**: Bezaubernde Statistiken zeigen Verteilung und Glücksmomente
4. 📅 **Träume verwirklichen**: Filterable Traumübersicht mit liebevollem CSV-Export

### 🧙‍♀️ Der Fairness-Zauberspruch

- 🤲 Jeder Mitarbeiter erhält etwa gleich viele Schichten mit Liebe
- 💖 Herzenswünsche bekommen magische Priorität
- 🎲 Natürliche Zufälligkeit sorgt für lebendige Variation  
- 🌸 Gleichmäßige Verteilung blüht über das ganze Jahr

## 🏠💕 Lokales Wunderland errichten

### 🎀 Was Sie benötigen:
- 🐍 Python 3.8+ (mit viel Liebe installiert)
- 📦 pip (Ihr treuer Paketbote)

### 🎪 Magisches Setup:
```bash
# Das wundervolle Repository zu sich holen
git clone https://github.com/Dianjeol/schicht.git
cd schicht

# Alle magischen Dependencies einladen
pip install -r requirements.txt

# Die Träume zum Leben erwecken
streamlit run app.py
```

✨ **Voilà!** Ihre lokale Magie erwacht unter `http://localhost:8501` zum Leben! 🌟

## ☁️🌈 In die Cloud schweben

### 1. 🎋 Repository-Liebe teilen
- 💝 Forken Sie dieses Herzstück zu Ihrem GitHub-Account
- 🎁 Oder laden Sie alle Dateien in Ihr eigenes Lieblings-Repository

### 2. 🎭 Streamlit Cloud Zauber
1. ✨ Schweben Sie zu [streamlit.io/cloud](https://streamlit.io/cloud)
2. 🤗 Verbinden Sie sich liebevoll mit Ihrem GitHub-Account  
3. 🎪 Klicken Sie auf "New app" mit Vorfreude
4. 💖 Wählen Sie Ihr Repository und Branch mit Bedacht
5. 🎯 Hauptdatei: `app.py` (unser Herzstück!)
6. 🚀 Klicken Sie auf "Deploy" und lassen Sie die Magie geschehen

### 3. 🎉 Träume werden wahr!
Ihre wunderschöne App tanzt automatisch unter `https://[app-name].streamlit.app`! 🌟

> 💫 **Psst...** Unsere Live-App wartet bereits auf Sie: [schicht.streamlit.app](https://schicht.streamlit.app/) 💕

## 🎨📂 Unser liebevolles Zuhause

```
schicht/ 🏡
├── app.py              # 💖 Das schlagende Herz unserer App
├── requirements.txt    # 📋 Alle magischen Python-Zutaten
├── .gitignore         # 🙈 Geheimnisse, die Git nicht sehen soll
└── README.md          # 📖 Diese wundervolle Geschichte (Sie sind hier! 👋)
```

## 🔬💫 Die Magie hinter den Kulissen

- 🎭 **Bühne**: Streamlit (unser wunderschönes Theater)
- 🐍 **Dirigent**: Python mit SQLite (die harmonische Symphonie)  
- 💾 **Gedächtnis**: SQLite (automatisch entstehende Erinnerungsschatzkiste)
- 🧮 **Zaubertrick**: Gewichtetes Scoring-System für liebevolle Fairness

### 🏛️✨ Die Schatzkammer der Daten

```sql
-- 💝 Herzenswünsche der Mitarbeitenden
CREATE TABLE preferences (
    id INTEGER PRIMARY KEY,          -- 🔑 Jeder Wunsch ist einzigartig
    name TEXT UNIQUE NOT NULL,       -- 👤 Der liebevolle Name
    preferred_days TEXT NOT NULL     -- 💖 Die 3 Herzenswünsche
);

-- 📅 Die zauberhaften Schichtpläne  
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY,              -- 🎯 Jede Schicht ist besonders
    date TEXT NOT NULL,                  -- 📆 Das wichtige Datum
    employee_name TEXT NOT NULL,         -- 👋 Wer darf heute glänzen
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- ⏰ Wann die Magie entstand
);
```

## 🎨🔮 Weitere Wunder möglich!

- 👥 **Mehr Seelen**: Teamgröße in `generate_fair_schedule()` liebevoll anpassen
- 🌅 **Wochenend-Zauber**: Samstag & Sonntag in die Magie einbeziehen
- 🌟 **Mehrfach-Glück**: Mehrere Schichten pro Tag für extra Freude
- 🏖️ **Traum-Auszeiten**: Urlaub und Abwesenheiten sanft berücksichtigen

## 🤗💕 Wir sind für Sie da!

Haben Sie Fragen, Wünsche oder brauchen Sie eine warme Umarmung?
1. 📚 Besuchen Sie die [Streamlit Cloud Dokumentation](https://docs.streamlit.io/streamlit-cloud)
2. 💌 Erstellen Sie ein liebevolles Issue in diesem Repository
3. 🫂 Kontaktieren Sie uns - wir sind immer für Sie da!

## 📜✨ Lizenz mit Herz

MIT License - Teilen Sie diese Liebe frei mit der ganzen Welt! 🌍💖

---

<div align="center">

### 🌟 **Entwickelt mit unendlicher Liebe, Streamlit-Magie und einer Prise Träume** 🌟

*Von Herzen für Teams, die Fairness leben* 💝

🎭 **[Erleben Sie die Magie live!](https://schicht.streamlit.app/)** 🎭

---

*"Wo Fairness auf Freude trifft, entstehen die schönsten Schichtpläne."* ✨

</div> 