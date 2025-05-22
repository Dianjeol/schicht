import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import random
from collections import defaultdict, Counter
import sqlite3
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

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

# PDF-Generation-Funktionen
def generate_pdf_report(schedule_data, title, weeks_data):
    """Generiert ein PDF-Report des Schichtplans"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center
        textColor=colors.HexColor('#2E4057')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=20,
        alignment=1,  # Center
        textColor=colors.HexColor('#888888')
    )
    
    # Content
    story = []
    
    # Title
    story.append(Paragraph("🌟 Schichtplaner 2025 🌟", title_style))
    story.append(Paragraph(title, subtitle_style))
    story.append(Paragraph(f"Erstellt am: {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}", subtitle_style))
    story.append(Spacer(1, 20))
    
    if weeks_data:
        # Erstelle Tabellendaten
        table_data = [["📅 Kalenderwoche", "🔵 Mo", "🟢 Di", "🟡 Mi", "🟠 Do", "🔴 Fr"]]
        
        for week_info in weeks_data:
            table_data.append([
                week_info["Kalenderwoche"],
                week_info["Montag"] or "-",
                week_info["Dienstag"] or "-", 
                week_info["Mittwoch"] or "-",
                week_info["Donnerstag"] or "-",
                week_info["Freitag"] or "-"
            ])
        
        # Erstelle Tabelle
        table = Table(table_data, colWidths=[2.2*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            # Header-Styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E4057')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            
            # Content-Styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            
            # Border-Styling
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
        ]))
        
        story.append(table)
    else:
        story.append(Paragraph("Keine Daten für den gewählten Zeitraum verfügbar.", styles['Normal']))
    
    # Footer
    story.append(Spacer(1, 30))
    story.append(Paragraph("💖 Erstellt mit Liebe und Streamlit-Magie 💖", subtitle_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def get_current_and_next_weeks(schedule_data, num_weeks=4):
    """Holt die aktuelle und nächsten n Kalenderwochen"""
    current_date = datetime.now()
    current_year, current_week, _ = current_date.isocalendar()
    
    target_weeks = []
    for i in range(num_weeks):
        week_num = current_week + i
        year = current_year
        
        # Handle year rollover
        if week_num > 52:
            week_num = week_num - 52
            year += 1
        
        target_weeks.append((year, week_num))
    
    # Filter schedule data for target weeks
    filtered_data = {}
    for date_str, employee in schedule_data.items():
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        year, week, _ = date_obj.isocalendar()
        
        if (year, week) in target_weeks:
            filtered_data[date_str] = employee
    
    return filtered_data

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

# Passwort-Authentifizierung
def check_password():
    """Überprüft das Passwort für den Zugang zur App"""
    
    def password_entered():
        """Überprüft ob das eingegebene Passwort korrekt ist"""
        if st.session_state["password"] == "msh":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Passwort aus Session State entfernen
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Erstes Mal - zeige Passwort-Eingabe
        st.markdown("### 🔐 Schichtplaner 2025 - Zugang")
        st.markdown("*Bitte geben Sie das Passwort ein:*")
        st.text_input(
            "Passwort", 
            type="password", 
            on_change=password_entered, 
            key="password",
            placeholder="Passwort eingeben..."
        )
        st.markdown("---")
        st.markdown("*💝 Mit Liebe für faire Teams entwickelt*")
        return False
    elif not st.session_state["password_correct"]:
        # Passwort war falsch
        st.markdown("### 🔐 Schichtplaner 2025 - Zugang")
        st.markdown("*Bitte geben Sie das Passwort ein:*")
        st.text_input(
            "Passwort", 
            type="password", 
            on_change=password_entered, 
            key="password",
            placeholder="Passwort eingeben..."
        )
        st.error("😞 Passwort ist leider nicht korrekt. Bitte versuchen Sie es erneut.")
        st.markdown("---")
        st.markdown("*💝 Mit Liebe für faire Teams entwickelt*")
        return False
    else:
        # Passwort korrekt
        return True

# Streamlit UI
def main():
    # Passwort-Check
    if not check_password():
        return
    
    # Initialisiere Datenbank
    init_database()
    
    st.title("🌟✨ Schichtplaner 2025 ✨🌟")
    st.markdown("*Mit Liebe für faire Teams entwickelt* 💝")
    
    # Logout-Button in der Sidebar
    with st.sidebar:
        if st.button("🚪 Logout", type="secondary"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.rerun()
    
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
        
        # Eingabeformular ohne Form (um Session State Problem zu vermeiden)
        st.subheader("Neue Präferenz hinzufügen")
        
        # Initialisiere Session State für Formular-Reset
        if 'form_reset_trigger' not in st.session_state:
            st.session_state.form_reset_trigger = 0
        
        name = st.text_input(
            "Name des Mitarbeitenden:",
            placeholder="z.B. Max Mustermann",
            key=f"name_input_{st.session_state.form_reset_trigger}"
        )
        
        weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
        
        st.markdown("**Geben Sie Ihre 3 Wunsch-Wochentage in Prioritätsreihenfolge an:**")
        st.info("💡 **Wichtig**: Bitte wählen Sie alle 3 Prioritäten aus! Dies ermöglicht eine faire Schichtverteilung, auch wenn Ihr Erstwunsch nicht verfügbar ist.")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            first_choice = st.selectbox(
                "🥇 1. Wahl:",
                ["Bitte wählen..."] + weekdays,
                index=0,
                help="Ihr absoluter Lieblings-Wochentag",
                key=f"first_choice_{st.session_state.form_reset_trigger}"
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
                index=0,
                help="Ihr zweitliebster Wochentag",
                key=f"second_choice_{st.session_state.form_reset_trigger}"
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
                index=0,
                help="Ihr drittliebster Wochentag",
                key=f"third_choice_{st.session_state.form_reset_trigger}"
            )
        
        # Submit Button außerhalb des Forms
        submitted = st.button("Präferenz speichern", type="primary", use_container_width=True)
        
        if submitted:
            # Validierung der Eingaben
            if not name.strip():
                st.error("❌ Bitte geben Sie einen Namen ein.")
            elif (first_choice == "Bitte wählen..." or 
                  second_choice == "Bitte wählen..." or 
                  third_choice == "Bitte wählen..."):
                # Zeige genau was noch fehlt
                missing = []
                if first_choice == "Bitte wählen...":
                    missing.append("🥇 1. Wahl")
                if second_choice == "Bitte wählen...":
                    missing.append("🥈 2. Wahl") 
                if third_choice == "Bitte wählen...":
                    missing.append("🥉 3. Wahl")
                
                st.error(f"❌ Bitte vervollständigen Sie Ihre Auswahl!")
                st.warning(f"💡 **Noch fehlend**: {' und '.join(missing)}")
                st.info("ℹ️ **Hinweis**: Sie müssen alle 3 Prioritäten (1., 2. und 3. Wahl) auswählen, um eine faire Schichtverteilung zu ermöglichen.")
            else:
                # Prüfe auf Duplikate
                choices = [first_choice, second_choice, third_choice]
                if len(set(choices)) != 3:
                    st.error("❌ Bitte wählen Sie 3 verschiedene Wochentage aus.")
                    st.warning(f"💡 **Problem**: Doppelte Auswahl erkannt. Jeder Tag darf nur einmal gewählt werden.")
                else:
                    # Alles korrekt - speichern
                    preferred_days = [first_choice, second_choice, third_choice]
                    save_preferences(name.strip(), preferred_days)
                    st.success(f"✅ Präferenz für **{name.strip()}** erfolgreich gespeichert! 🎉")
                    st.success(f"🎯 **Ihre Prioritäten**: 🥇 {first_choice} | 🥈 {second_choice} | 🥉 {third_choice}")
                    st.balloons()  # Kleine Feier! 🎈
                    # Reset das Formular durch Erhöhung des Triggers
                    st.session_state.form_reset_trigger += 1
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
            # Hilfsfunktion um das Datum einer Kalenderwoche zu berechnen
            def get_week_dates(year, week):
                # Erster Tag der Woche (Montag)
                jan4 = datetime(year, 1, 4)
                week_start = jan4 + timedelta(days=(week - 1) * 7 - jan4.weekday())
                # Letzter Arbeitstag der Woche (Freitag)
                week_end = week_start + timedelta(days=4)
                return week_start, week_end
            
            # Erstelle Kalenderwochen-Tabelle
            weekly_data = {}
            
            for date_str, employee in filtered_schedule.items():
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Berechne Kalenderwoche
                year, week, weekday = date_obj.isocalendar()
                
                # Berechne Start- und Enddatum der Woche
                week_start, week_end = get_week_dates(year, week)
                
                # Formatiere die KW mit Datumsbereich
                kw_display = f"KW {week:02d}"
                date_range = f"{week_start.strftime('%d.%m.')} - {week_end.strftime('%d.%m.')}"
                kw_key = f"KW {week:02d}"
                
                if kw_key not in weekly_data:
                    # Formatiere mit grauen Klammern und Datum
                    kw_formatted = f"{kw_display} ({date_range})"
                    weekly_data[kw_key] = {
                        "Kalenderwoche": kw_formatted,
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
            
            # CSS für bessere Darstellung der Kalenderwochen
            st.markdown("""
                <style>
                /* Styling für Kalenderwochen-Tabelle */
                .stDataFrame [data-testid="stDataFrameCell"] {
                    font-size: 0.9em;
                }
                
                /* Allgemeine Verbesserungen */
                .date-range {
                    color: #888888 !important;
                    font-size: 0.85em !important;
                }
                </style>
            """, unsafe_allow_html=True)
            
            # Zeige die Tabelle mit verbessertem Styling
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Kalenderwoche": st.column_config.TextColumn("📅 Kalenderwoche", width="medium", help="Kalenderwoche mit Zeitraum (Montag bis Freitag)"),
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
            st.subheader("💾 Download-Optionen")
            
            # CSV Downloads
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📄 CSV-Downloads:**")
                # Kalenderwochen-CSV
                weekly_csv = df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📊 Kalenderwochen-Plan (CSV)",
                    data=weekly_csv,
                    file_name=f"schichtplan_kalenderwochen_2025.csv",
                    mime="text/csv"
                )
                
                # Listen-CSV
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
                        label="📋 Listen-Plan (CSV)",
                        data=list_csv,
                        file_name=f"schichtplan_liste_2025.csv",
                        mime="text/csv"
                    )
            
            with col2:
                st.markdown("**📄 PDF-Downloads:**")
                
                # Ganzes Jahr PDF
                try:
                    full_year_pdf = generate_pdf_report(
                        filtered_schedule, 
                        f"Vollständiger Jahresplan 2025 ({len(sorted_data)} Kalenderwochen)",
                        sorted_data
                    )
                    st.download_button(
                        label="🗓️ Ganzes Jahr (PDF)",
                        data=full_year_pdf.getvalue(),
                        file_name=f"schichtplan_2025_komplett.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"PDF-Generierung fehlgeschlagen: {str(e)}")
                
                # Aktuelle + nächste 3 KW PDF
                try:
                    current_date = datetime.now()
                    current_week = current_date.isocalendar()[1]
                    
                    # Hole original schedule (nicht gefiltert) für aktuelle Wochen
                    original_schedule = load_schedule()
                    current_weeks_schedule = get_current_and_next_weeks(original_schedule, 4)
                    
                    if current_weeks_schedule:
                        # Baue weeks_data für aktuelle Wochen
                        weekly_data_current = {}
                        
                        for date_str, employee in current_weeks_schedule.items():
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            year, week, weekday = date_obj.isocalendar()
                            week_start, week_end = get_week_dates(year, week)
                            kw_display = f"KW {week:02d}"
                            date_range = f"{week_start.strftime('%d.%m.')} - {week_end.strftime('%d.%m.')}"
                            kw_key = f"KW {week:02d}"
                            
                            if kw_key not in weekly_data_current:
                                weekly_data_current[kw_key] = {
                                    "Kalenderwoche": f"{kw_display} ({date_range})",
                                    "Montag": "",
                                    "Dienstag": "",
                                    "Mittwoch": "",
                                    "Donnerstag": "",
                                    "Freitag": ""
                                }
                            
                            weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                            if weekday in weekday_names:
                                day_name = weekday_names[weekday]
                                weekly_data_current[kw_key][day_name] = employee
                        
                        sorted_weeks_current = sorted(weekly_data_current.keys(), key=lambda x: int(x.split()[1]))
                        sorted_data_current = [weekly_data_current[kw] for kw in sorted_weeks_current]
                        
                        current_weeks_pdf = generate_pdf_report(
                            current_weeks_schedule,
                            f"Aktuelle und nächste 3 Kalenderwochen (KW {current_week}-{current_week+3})",
                            sorted_data_current
                        )
                        st.download_button(
                            label="📅 Nächste 4 Wochen (PDF)",
                            data=current_weeks_pdf.getvalue(),
                            file_name=f"schichtplan_naechste_4kw.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.info("Keine Daten für die nächsten 4 Wochen verfügbar.")
                        
                except Exception as e:
                    st.error(f"PDF-Generierung (4 Wochen) fehlgeschlagen: {str(e)}")
                    
                # Hilfsfunktion für PDF-Generation (falls noch nicht definiert)
                if 'get_week_dates' not in globals():
                    def get_week_dates(year, week):
                        jan4 = datetime(year, 1, 4)
                        week_start = jan4 + timedelta(days=(week - 1) * 7 - jan4.weekday())
                        week_end = week_start + timedelta(days=4)
                        return week_start, week_end
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