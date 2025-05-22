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
    page_title="Schichtplaner 2025",
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
def generate_fair_schedule(preferences, year=2025):
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
            
            # Prioritäts-basierter Bonus für Wunschtag
            preference_bonus = 0
            if weekday_name in preferences[emp]:
                priority_index = preferences[emp].index(weekday_name)
                if priority_index == 0:  # 1. Wahl
                    preference_bonus = 15
                elif priority_index == 1:  # 2. Wahl
                    preference_bonus = 10
                elif priority_index == 2:  # 3. Wahl
                    preference_bonus = 5
            
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
    
    st.title("🌟✨ Schichtplaner 2025 ✨🌟")
    st.markdown("*Mit Liebe für faire Teams entwickelt* 💝")
    
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
                if len(days) >= 3:
                    pref_text = f"🥇 {days[0]} | 🥈 {days[1]} | 🥉 {days[2]}"
                else:
                    pref_text = ', '.join(days)
                st.write(f"**{name}**: {pref_text}")
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
            
            st.markdown("**Geben Sie Ihre 3 Wunsch-Wochentage in Prioritätsreihenfolge an:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                first_choice = st.selectbox(
                    "🥇 1. Wahl:",
                    ["Bitte wählen..."] + weekdays,
                    help="Ihr absoluter Lieblings-Wochentag"
                )
            
            with col2:
                # Entferne die bereits gewählten Optionen
                if first_choice == "Bitte wählen...":
                    available_second = weekdays
                else:
                    available_second = [day for day in weekdays if day != first_choice]
                
                second_choice = st.selectbox(
                    "🥈 2. Wahl:",
                    ["Bitte wählen..."] + available_second,
                    help="Ihr zweitliebster Wochentag"
                )
            
            with col3:
                # Entferne bereits gewählte Optionen
                chosen_days = []
                if first_choice != "Bitte wählen...":
                    chosen_days.append(first_choice)
                if second_choice != "Bitte wählen...":
                    chosen_days.append(second_choice)
                
                available_third = [day for day in weekdays if day not in chosen_days]
                
                third_choice = st.selectbox(
                    "🥉 3. Wahl:",
                    ["Bitte wählen..."] + available_third,
                    help="Ihr drittliebster Wochentag"
                )
            
            submitted = st.form_submit_button("Präferenz speichern")
            
            if submitted:
                if not name.strip():
                    st.error("Bitte geben Sie einen Namen ein.")
                elif (first_choice == "Bitte wählen..." or 
                      second_choice == "Bitte wählen..." or 
                      third_choice == "Bitte wählen..."):
                    st.error("Bitte wählen Sie alle 3 Prioritäten aus.")
                else:
                    # Speichere in Prioritätsreihenfolge
                    preferred_days = [first_choice, second_choice, third_choice]
                    save_preferences(name.strip(), preferred_days)
                    st.success(f"Präferenz für {name} erfolgreich gespeichert! 🎉")
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
            {
                "Name": name, 
                "🥇 1. Wahl": days[0] if len(days) > 0 else "",
                "🥈 2. Wahl": days[1] if len(days) > 1 else "",
                "🥉 3. Wahl": days[2] if len(days) > 2 else ""
            }
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
                    
                    # Berechne detaillierte Statistiken
                    detailed_stats = []
                    for name in preferences.keys():
                        total_assignments = assignment_count[name]
                        total_preference_matches = preference_score[name]
                        
                        if total_assignments > 0:
                            rate = (total_preference_matches / total_assignments * 100)
                        else:
                            rate = 0
                            
                        detailed_stats.append({
                            "Name": name,
                            "Gesamt Schichten": total_assignments,
                            "Wunschtage erfüllt": total_preference_matches,
                            "Erfüllungsrate": f"{rate:.1f}%"
                        })
                    
                    pref_df = pd.DataFrame(detailed_stats)
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
                ["Alle"] + [f"{i:02d} - {datetime(2025, i, 1).strftime('%B')}" for i in range(1, 13)]
            )
        
        with col2:
            employee_filter = st.selectbox(
                "Mitarbeiter filtern:",
                ["Alle"] + sorted(set(schedule.values()))
            )
        
        # Daten für Kalenderwochen-Ansicht vorbereiten
        filtered_schedule = {}
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
                
            filtered_schedule[date_str] = employee
        
        if filtered_schedule:
            # Erstelle Kalenderwochen-Tabelle
            weekly_data = {}
            
            for date_str, employee in filtered_schedule.items():
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Berechne Kalenderwoche
                year, week, weekday = date_obj.isocalendar()
                kw_key = f"KW {week:02d}"
                
                if kw_key not in weekly_data:
                    weekly_data[kw_key] = {
                        "KW": kw_key,
                        "Montag": "",
                        "Dienstag": "",
                        "Mittwoch": "",
                        "Donnerstag": "",
                        "Freitag": ""
                    }
                
                # Weekday: 1=Montag, 2=Dienstag, ..., 5=Freitag
                weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                
                if weekday in weekday_names:
                    day_name = weekday_names[weekday]
                    weekly_data[kw_key][day_name] = employee
            
            # Sortiere nach Kalenderwoche
            sorted_weeks = sorted(weekly_data.keys(), key=lambda x: int(x.split()[1]))
            sorted_data = [weekly_data[kw] for kw in sorted_weeks]
            
            # Erstelle DataFrame
            df = pd.DataFrame(sorted_data)
            
            st.subheader(f"📅 Schichtplan Kalenderwochen-Ansicht ({len(filtered_schedule)} Schichten)")
            
            # Zeige die Tabelle mit verbessertem Styling
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "KW": st.column_config.TextColumn("📅 KW", width="small"),
                    "Montag": st.column_config.TextColumn("🔵 Montag", width="medium"),
                    "Dienstag": st.column_config.TextColumn("🟢 Dienstag", width="medium"),
                    "Mittwoch": st.column_config.TextColumn("🟡 Mittwoch", width="medium"),
                    "Donnerstag": st.column_config.TextColumn("🟠 Donnerstag", width="medium"),
                    "Freitag": st.column_config.TextColumn("🔴 Freitag", width="medium")
                }
            )
            
            # Zusätzliche Listen-Ansicht als Toggle
            if st.toggle("📋 Zusätzliche Listen-Ansicht anzeigen"):
                list_data = []
                for date_str, employee in sorted(filtered_schedule.items()):
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    list_data.append({
                        "Datum": date_obj.strftime('%d.%m.%Y'),
                        "Wochentag": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][date_obj.weekday()],
                        "Mitarbeiter": employee
                    })
                
                list_df = pd.DataFrame(list_data)
                st.dataframe(list_df, use_container_width=True, hide_index=True)
            
            # Download-Optionen
            col1, col2 = st.columns(2)
            
            with col1:
                # Kalenderwochen-CSV
                weekly_csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📄 Kalenderwochen-Plan als CSV",
                    data=weekly_csv,
                    file_name=f"schichtplan_kalenderwochen_2025.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Listen-CSV (wie vorher)
                if filtered_schedule:
                    list_data = []
                    for date_str, employee in sorted(filtered_schedule.items()):
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        list_data.append({
                            "Datum": date_obj.strftime('%d.%m.%Y'),
                            "Wochentag": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][date_obj.weekday()],
                            "Mitarbeiter": employee
                        })
                    
                    list_df = pd.DataFrame(list_data)
                    list_csv = list_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📄 Listen-Plan als CSV",
                        data=list_csv,
                        file_name=f"schichtplan_liste_2025.csv",
                        mime="text/csv"
                    )
        else:
            st.info("Keine Einträge für die gewählten Filter gefunden.")
    
    # Footer
    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: #666; padding: 20px;'>
            <small>✨ Schichtplaner 2025 | Mit 💖 und Streamlit-Magie erstellt ✨<br>
            🎭 <a href='https://github.com/Dianjeol/schicht' target='_blank' style='text-decoration: none; color: #ff6b6b;'>GitHub Repository</a> | 
            🌟 <a href='https://schicht.streamlit.app/' target='_blank' style='text-decoration: none; color: #4ecdc4;'>Live erleben</a> 🌟</small>
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main() 