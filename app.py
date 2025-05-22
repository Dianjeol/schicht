import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import random
from collections import defaultdict, Counter
import sqlite3

# Seitenkonfiguration
st.set_page_config(
    page_title="Schichtplaner 2024",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Datenbankfunktionen
def init_database():
    """Initialisiert die SQLite-Datenbank"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    # Tabelle für Mitarbeiterpräferenzen
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            preferred_days TEXT NOT NULL
        )
    ''')
    
    # Tabelle für generierte Schichtpläne
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            employee_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def save_preferences(name, preferred_days):
    """Speichert Mitarbeiterpräferenzen in der Datenbank"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    preferred_days_str = ','.join(preferred_days)
    cursor.execute('''
        INSERT OR REPLACE INTO preferences (name, preferred_days)
        VALUES (?, ?)
    ''', (name, preferred_days_str))
    
    conn.commit()
    conn.close()

def load_preferences():
    """Lädt alle Mitarbeiterpräferenzen aus der Datenbank"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT name, preferred_days FROM preferences')
    results = cursor.fetchall()
    
    preferences = {}
    for name, preferred_days_str in results:
        preferences[name] = preferred_days_str.split(',')
    
    conn.close()
    return preferences

def save_schedule(schedule_data):
    """Speichert den generierten Schichtplan"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    # Lösche alte Schichtpläne
    cursor.execute('DELETE FROM schedules')
    
    # Speichere neuen Plan
    for date_str, employee_name in schedule_data.items():
        cursor.execute('''
            INSERT INTO schedules (date, employee_name)
            VALUES (?, ?)
        ''', (date_str, employee_name))
    
    conn.commit()
    conn.close()

def load_schedule():
    """Lädt den gespeicherten Schichtplan"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT date, employee_name FROM schedules ORDER BY date')
    results = cursor.fetchall()
    
    schedule = {}
    for date_str, employee_name in results:
        schedule[date_str] = employee_name
    
    conn.close()
    return schedule

# Schichtplanungsalgorithmus
def generate_fair_schedule(preferences, year=2024):
    """
    Generiert einen fairen Jahresschichtplan basierend auf Mitarbeiterpräferenzen
    """
    # Wochentage Mapping
    weekdays = {
        'Montag': 0, 'Dienstag': 1, 'Mittwoch': 2, 
        'Donnerstag': 3, 'Freitag': 4, 'Samstag': 5, 'Sonntag': 6
    }
    
    # Erstelle Liste aller Arbeitstage im Jahr (Mo-Fr)
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    
    workdays = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Montag = 0, Freitag = 4
            workdays.append(current_date)
        current_date += timedelta(days=1)
    
    # Initialisiere Zähler und Zuweisungen
    employees = list(preferences.keys())
    assignment_count = {emp: 0 for emp in employees}
    preference_score = {emp: 0 for emp in employees}
    schedule = {}
    
    # Sortiere Arbeitstage für gleichmäßige Verteilung
    random.shuffle(workdays)
    
    for date in workdays:
        weekday_name = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag'][date.weekday()]
        
        # Bewerte jeden Mitarbeiter für diesen Tag
        scores = []
        for emp in employees:
            # Basis-Score: Negative Anzahl bisheriger Zuweisungen (weniger = besser)
            base_score = -assignment_count[emp]
            
            # Bonus für Wunschtag
            preference_bonus = 10 if weekday_name in preferences[emp] else 0
            
            # Kleiner Zufallsfaktor für Variabilität
            random_factor = random.uniform(-1, 1)
            
            total_score = base_score + preference_bonus + random_factor
            scores.append((total_score, emp))
        
        # Wähle Mitarbeiter mit höchstem Score
        scores.sort(reverse=True)
        chosen_employee = scores[0][1]
        
        # Aktualisiere Zähler
        assignment_count[chosen_employee] += 1
        if weekday_name in preferences[chosen_employee]:
            preference_score[chosen_employee] += 1
        
        # Speichere Zuweisung
        schedule[date.strftime('%Y-%m-%d')] = chosen_employee
    
    return schedule, assignment_count, preference_score

# Streamlit UI
def main():
    # Initialisiere Datenbank
    init_database()
    
    st.title("📅 Schichtplaner 2024")
    st.markdown("*Fairer Jahresschichtplan für 20 Mitarbeitende*")
    
    # Sidebar für Navigation
    st.sidebar.title("Navigation")
    mode = st.sidebar.radio(
        "Wählen Sie eine Option:",
        ["Präferenzen eingeben", "Schichtplan generieren", "Plan anzeigen"]
    )
    
    if mode == "Präferenzen eingeben":
        st.header("👥 Mitarbeiterpräferenzen eingeben")
        
        # Lade vorhandene Präferenzen
        existing_prefs = load_preferences()
        
        # Zeige bereits eingegeben Präferenzen
        if existing_prefs:
            st.subheader("Bereits eingegebene Präferenzen:")
            for name, days in existing_prefs.items():
                st.write(f"**{name}**: {', '.join(days)}")
            st.write(f"**Gesamt**: {len(existing_prefs)} von 20 Mitarbeitenden")
        
        st.divider()
        
        # Eingabeformular
        with st.form("preference_form"):
            st.subheader("Neue Präferenz hinzufügen")
            
            name = st.text_input(
                "Name des Mitarbeitenden:",
                placeholder="z.B. Max Mustermann"
            )
            
            weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
            preferred_days = st.multiselect(
                "Wählen Sie genau 3 bevorzugte Wochentage:",
                weekdays,
                help="Bitte wählen Sie exakt 3 Tage aus"
            )
            
            submitted = st.form_submit_button("Präferenz speichern")
            
            if submitted:
                if not name.strip():
                    st.error("Bitte geben Sie einen Namen ein.")
                elif len(preferred_days) != 3:
                    st.error("Bitte wählen Sie genau 3 Wochentage aus.")
                else:
                    save_preferences(name.strip(), preferred_days)
                    st.success(f"Präferenz für {name} erfolgreich gespeichert!")
                    st.rerun()
    
    elif mode == "Schichtplan generieren":
        st.header("⚙️ Schichtplan generieren")
        
        preferences = load_preferences()
        
        if len(preferences) == 0:
            st.warning("Noch keine Präferenzen eingegeben. Bitte gehen Sie zu 'Präferenzen eingeben'.")
            return
        
        st.write(f"**Anzahl eingetragener Mitarbeitender**: {len(preferences)}")
        
        if len(preferences) < 10:
            st.warning("⚠️ Weniger als 10 Mitarbeitende eingegeben. Für optimale Fairness sollten alle 20 Mitarbeitenden ihre Präferenzen eingeben.")
        
        # Übersicht der Präferenzen
        st.subheader("Übersicht der Präferenzen")
        prefs_df = pd.DataFrame([
            {"Name": name, "Bevorzugte Tage": ", ".join(days)}
            for name, days in preferences.items()
        ])
        st.dataframe(prefs_df, use_container_width=True)
        
        st.divider()
        
        # Generierung starten
        if st.button("🎯 Fairen Schichtplan generieren", type="primary"):
            with st.spinner("Generiere optimalen Schichtplan..."):
                schedule, assignment_count, preference_score = generate_fair_schedule(preferences)
                save_schedule(schedule)
                
                st.success("✅ Schichtplan erfolgreich generiert!")
                
                # Statistiken anzeigen
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Zuweisungsstatistik")
                    stats_df = pd.DataFrame([
                        {"Name": name, "Anzahl Schichten": count}
                        for name, count in assignment_count.items()
                    ]).sort_values("Anzahl Schichten", ascending=False)
                    st.dataframe(stats_df, use_container_width=True)
                
                with col2:
                    st.subheader("💯 Wunscherfüllungsrate")
                    pref_df = pd.DataFrame([
                        {
                            "Name": name, 
                            "Wunschtage erfüllt": preference_score[name],
                            "Rate": f"{(preference_score[name]/assignment_count[name]*100):.1f}%" if assignment_count[name] > 0 else "0%"
                        }
                        for name in preferences.keys()
                    ])
                    st.dataframe(pref_df, use_container_width=True)
                
                st.info("💡 Der Plan wurde gespeichert und kann unter 'Plan anzeigen' eingesehen werden.")
    
    elif mode == "Plan anzeigen":
        st.header("📋 Generierter Schichtplan")
        
        schedule = load_schedule()
        
        if not schedule:
            st.warning("Noch kein Schichtplan generiert. Bitte gehen Sie zu 'Schichtplan generieren'.")
            return
        
        # Filter-Optionen
        col1, col2 = st.columns(2)
        with col1:
            month_filter = st.selectbox(
                "Monat auswählen:",
                ["Alle"] + [f"{i:02d} - {datetime(2024, i, 1).strftime('%B')}" for i in range(1, 13)]
            )
        
        with col2:
            employee_filter = st.selectbox(
                "Mitarbeiter filtern:",
                ["Alle"] + sorted(set(schedule.values()))
            )
        
        # Daten für Anzeige vorbereiten
        schedule_data = []
        for date_str, employee in schedule.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Monatfilter anwenden
            if month_filter != "Alle":
                selected_month = int(month_filter.split(" - ")[0])
                if date_obj.month != selected_month:
                    continue
            
            # Mitarbeiterfilter anwenden
            if employee_filter != "Alle" and employee != employee_filter:
                continue
            
            schedule_data.append({
                "Datum": date_obj.strftime('%d.%m.%Y'),
                "Wochentag": date_obj.strftime('%A'),
                "Mitarbeiter": employee
            })
        
        if schedule_data:
            # Sortiere nach Datum
            schedule_data.sort(key=lambda x: datetime.strptime(x["Datum"], '%d.%m.%Y'))
            
            # Deutsche Wochentage
            german_weekdays = {
                'Monday': 'Montag', 'Tuesday': 'Dienstag', 'Wednesday': 'Mittwoch',
                'Thursday': 'Donnerstag', 'Friday': 'Freitag', 'Saturday': 'Samstag', 'Sunday': 'Sonntag'
            }
            
            for item in schedule_data:
                item["Wochentag"] = german_weekdays.get(item["Wochentag"], item["Wochentag"])
            
            df = pd.DataFrame(schedule_data)
            
            st.subheader(f"📅 Schichtplan ({len(schedule_data)} Einträge)")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Download-Option
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📄 Plan als CSV herunterladen",
                data=csv,
                file_name=f"schichtplan_2024.csv",
                mime="text/csv"
            )
        else:
            st.info("Keine Einträge für die gewählten Filter gefunden.")
    
    # Footer
    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <small>Schichtplaner 2024 | Erstellt mit Streamlit | 
            <a href='https://github.com/Dianjeol/schicht' target='_blank'>GitHub Repository</a></small>
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main() 