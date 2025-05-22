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
import hashlib
import uuid

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
    
    # Tabelle für Login-Sessions (90 Tage Passwort-Speicherung)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
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
    """Lädt alle Mitarbeiterpräferenzen aus der Datenbank (alphabetisch sortiert)"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT name, preferred_days FROM preferences ORDER BY name ASC')
    results = cursor.fetchall()
    
    preferences = {}
    for name, preferred_days_str in results:
        preferences[name] = preferred_days_str.split(',')
    
    conn.close()
    return preferences

def delete_preference(name):
    """Löscht eine Mitarbeiterpräferenz aus der Datenbank"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM preferences WHERE name = ?', (name,))
    
    conn.commit()
    conn.close()

def get_preference_by_name(name):
    """Holt eine spezifische Präferenz nach Name"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT preferred_days FROM preferences WHERE name = ?', (name,))
    result = cursor.fetchone()
    
    conn.close()
    if result:
        return result[0].split(',')
    return None

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

# Session-Management für 90-Tage Passwort-Speicherung
def create_session_token():
    """Erstellt einen neuen Session-Token"""
    return str(uuid.uuid4())

def save_login_session(token):
    """Speichert einen Login-Session-Token für 90 Tage"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    expires_at = datetime.now() + timedelta(days=90)
    
    cursor.execute('''
        INSERT INTO login_sessions (session_token, expires_at)
        VALUES (?, ?)
    ''', (token, expires_at))
    
    conn.commit()
    conn.close()

def is_valid_session_token(token):
    """Prüft ob ein Session-Token noch gültig ist"""
    if not token:
        return False
        
    try:
        conn = sqlite3.connect('schichtplaner.db')
        cursor = conn.cursor()
        
        # Prüfe ob Tabelle existiert
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='login_sessions'
        ''')
        
        if not cursor.fetchone():
            conn.close()
            return False
        
        cursor.execute('''
            SELECT expires_at FROM login_sessions 
            WHERE session_token = ? AND expires_at > datetime('now')
        ''', (token,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    except sqlite3.Error:
        return False

def cleanup_expired_sessions():
    """Entfernt abgelaufene Session-Tokens"""
    try:
        conn = sqlite3.connect('schichtplaner.db')
        cursor = conn.cursor()
        
        # Prüfe ob Tabelle existiert
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='login_sessions'
        ''')
        
        if cursor.fetchone():
            cursor.execute('DELETE FROM login_sessions WHERE expires_at <= datetime("now")')
            conn.commit()
        
        conn.close()
    except sqlite3.Error:
        # Fehler beim Cleanup ignorieren - Tabelle existiert möglicherweise noch nicht
        pass

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
    story.append(Paragraph("Schichtplaner 2025 - Automatisch generiert", subtitle_style))
    
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
    Generiert einen fairen Jahresschichtplan mit optimaler Prioritätenverteilung:
    1. Möglichst gleich viele Schichten für alle
    2. Möglichst gleich viele erste/zweite/dritte Wünsche für alle
    """
    # Erstelle Liste aller Arbeitstage im Jahr (Mo-Fr)
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    
    workdays = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Montag = 0, Freitag = 4
            workdays.append(current_date)
        current_date += timedelta(days=1)
    
    # Initialisiere Zähler
    employees = list(preferences.keys())
    assignment_count = {emp: 0 for emp in employees}
    preference_stats = {emp: {'first': 0, 'second': 0, 'third': 0, 'fourth': 0, 'fifth': 0, 'none': 0} for emp in employees}
    schedule = {}
    
    # Sortiere Arbeitstage für gleichmäßige Verteilung
    random.shuffle(workdays)
    
    for date in workdays:
        weekday_name = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag'][date.weekday()]
        
        # Finde optimalen Mitarbeiter basierend auf Fairness-Prioritäten
        best_employees = employees[:]
        
        # Priorität 1: Mitarbeiter mit wenigsten Schichten
        min_assignments = min(assignment_count[emp] for emp in employees)
        best_employees = [emp for emp in best_employees if assignment_count[emp] == min_assignments]
        
        if len(best_employees) == 1:
            chosen_employee = best_employees[0]
        else:
            # Priorität 2: Unter denen mit wenigsten Schichten, 
            # bevorzuge die mit diesem Wochentag in ihren Präferenzen
            
            # Kategorisiere Mitarbeiter nach ihrer Präferenz für diesen Tag
            first_choice_candidates = []
            second_choice_candidates = []
            third_choice_candidates = []
            fourth_choice_candidates = []
            fifth_choice_candidates = []
            no_preference_candidates = []
            
            for emp in best_employees:
                if weekday_name in preferences[emp]:
                    priority_index = preferences[emp].index(weekday_name)
                    if priority_index == 0:  # 1. Wahl
                        first_choice_candidates.append(emp)
                    elif priority_index == 1:  # 2. Wahl
                        second_choice_candidates.append(emp)
                    elif priority_index == 2:  # 3. Wahl
                        third_choice_candidates.append(emp)
                    elif priority_index == 3:  # 4. Wahl
                        fourth_choice_candidates.append(emp)
                    elif priority_index == 4:  # 5. Wahl
                        fifth_choice_candidates.append(emp)
                else:
                    no_preference_candidates.append(emp)
            
            # Wähle nach Präferenz-Priorität und Fairness
            chosen_employee = None
            
            # Prüfe erst 1. Wahl Kandidaten
            if first_choice_candidates:
                min_first_wishes = min(preference_stats[emp]['first'] for emp in first_choice_candidates)
                fairest_candidates = [emp for emp in first_choice_candidates 
                                    if preference_stats[emp]['first'] == min_first_wishes]
                chosen_employee = random.choice(fairest_candidates)
            
            # Dann 2. Wahl Kandidaten
            elif second_choice_candidates:
                min_second_wishes = min(preference_stats[emp]['second'] for emp in second_choice_candidates)
                fairest_candidates = [emp for emp in second_choice_candidates 
                                    if preference_stats[emp]['second'] == min_second_wishes]
                chosen_employee = random.choice(fairest_candidates)
            
            # Dann 3. Wahl Kandidaten
            elif third_choice_candidates:
                min_third_wishes = min(preference_stats[emp]['third'] for emp in third_choice_candidates)
                fairest_candidates = [emp for emp in third_choice_candidates 
                                    if preference_stats[emp]['third'] == min_third_wishes]
                chosen_employee = random.choice(fairest_candidates)
            
            # Dann 4. Wahl Kandidaten
            elif fourth_choice_candidates:
                min_fourth_wishes = min(preference_stats[emp]['fourth'] for emp in fourth_choice_candidates)
                fairest_candidates = [emp for emp in fourth_choice_candidates 
                                    if preference_stats[emp]['fourth'] == min_fourth_wishes]
                chosen_employee = random.choice(fairest_candidates)
            
            # Dann 5. Wahl Kandidaten
            elif fifth_choice_candidates:
                min_fifth_wishes = min(preference_stats[emp]['fifth'] for emp in fifth_choice_candidates)
                fairest_candidates = [emp for emp in fifth_choice_candidates 
                                    if preference_stats[emp]['fifth'] == min_fifth_wishes]
                chosen_employee = random.choice(fairest_candidates)
            
            # Zuletzt die ohne Präferenz für diesen Tag
            else:
                min_none_assignments = min(preference_stats[emp]['none'] for emp in no_preference_candidates)
                fairest_candidates = [emp for emp in no_preference_candidates 
                                    if preference_stats[emp]['none'] == min_none_assignments]
                chosen_employee = random.choice(fairest_candidates)
        
        # Aktualisiere Zähler
        assignment_count[chosen_employee] += 1
        
        # Aktualisiere Präferenz-Statistiken
        if weekday_name in preferences[chosen_employee]:
            priority_index = preferences[chosen_employee].index(weekday_name)
            if priority_index == 0:  # 1. Wahl
                preference_stats[chosen_employee]['first'] += 1
            elif priority_index == 1:  # 2. Wahl
                preference_stats[chosen_employee]['second'] += 1
            elif priority_index == 2:  # 3. Wahl
                preference_stats[chosen_employee]['third'] += 1
            elif priority_index == 3:  # 4. Wahl
                preference_stats[chosen_employee]['fourth'] += 1
            elif priority_index == 4:  # 5. Wahl
                preference_stats[chosen_employee]['fifth'] += 1
        else:
            preference_stats[chosen_employee]['none'] += 1
        
        # Speichere Zuweisung
        schedule[date.strftime('%Y-%m-%d')] = chosen_employee
    
    # Berechne traditionelle preference_score für Kompatibilität mit vorhandener UI
    preference_score = {}
    for emp in employees:
        preference_score[emp] = (preference_stats[emp]['first'] + 
                               preference_stats[emp]['second'] + 
                               preference_stats[emp]['third'] +
                               preference_stats[emp]['fourth'] +
                               preference_stats[emp]['fifth'])
    
    return schedule, assignment_count, preference_score, preference_stats

# Passwort-Authentifizierung mit 90-Tage Speicherung
def check_password():
    """Überprüft das Passwort für den Zugang zur App mit 90-Tage Speicherung"""
    
    # Initialisiere Datenbank falls noch nicht geschehen
    init_database()
    
    # Cleanup abgelaufene Sessions
    cleanup_expired_sessions()
    
    # Prüfe ob bereits ein gültiger Session-Token existiert
    if "session_token" in st.session_state:
        if is_valid_session_token(st.session_state["session_token"]):
            return True
        else:
            # Token abgelaufen, entferne aus Session State
            del st.session_state["session_token"]
    
    def password_entered():
        """Überprüft ob das eingegebene Passwort korrekt ist"""
        if st.session_state["password"] == "msh":
            # Passwort korrekt - erstelle neuen Session-Token
            token = create_session_token()
            save_login_session(token)
            st.session_state["session_token"] = token
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
        st.markdown("*Effizienter Schichtplaner für Teams*")
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
        st.markdown("*Effizienter Schichtplaner für Teams*")
        return False
    else:
        # Passwort korrekt
        return True

# Streamlit UI
def main():
    # Passwort-Check (initialisiert auch die Datenbank)
    if not check_password():
        return
    
    st.title("📅 Schichtplaner 2025")
    st.markdown("*Effiziente Schichtplanung für Teams*")
    
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
        ["Personen eingeben", "Schichtplan generieren", "Plan anzeigen"]
    )
    
    if mode == "Personen eingeben":
        st.header("👥 Mitarbeiterpersonen eingeben")
        
        # Lade vorhandene Personen
        existing_prefs = load_preferences()
        
        # Zeige bereits eingegebene Personen mit Bearbeitungsoptionen
        if existing_prefs:
            st.subheader("Bereits eingegebene Personen (alphabetisch sortiert):")
            
            # Erstelle DataFrame für bessere Darstellung
            prefs_list = []
            for name, days in existing_prefs.items():
                if len(days) >= 5:
                    prefs_list.append({
                        "Name": name,
                        "🥇 1. Wahl": days[0],
                        "🥈 2. Wahl": days[1], 
                        "🥉 3. Wahl": days[2],
                        "🏅 4. Wahl": days[3],
                        "🏅 5. Wahl": days[4]
                    })
                else:
                    # Fallback für unvollständige Daten
                    prefs_list.append({
                        "Name": name,
                        "🥇 1. Wahl": days[0] if len(days) > 0 else "",
                        "🥈 2. Wahl": days[1] if len(days) > 1 else "",
                        "🥉 3. Wahl": days[2] if len(days) > 2 else "",
                        "🏅 4. Wahl": days[3] if len(days) > 3 else "",
                        "🏅 5. Wahl": days[4] if len(days) > 4 else ""
                    })
            
            prefs_df = pd.DataFrame(prefs_list)
            st.dataframe(prefs_df, use_container_width=True, hide_index=True)
            
            st.write(f"**Gesamt**: {len(existing_prefs)} Mitarbeitende")
        
        st.divider()
        
        # Bearbeitungsmodus
        if st.session_state.get("edit_mode", False):
            st.subheader(f"✏️ Person bearbeiten: {st.session_state.edit_name}")
            st.info("💡 Ändern Sie die gewünschten Werte und speichern Sie.")
            
            edit_name = st.text_input(
                "Name:",
                value=st.session_state.edit_name,
                key="edit_name_input"
            )
            
            weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
            current_prefs = st.session_state.edit_prefs
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                edit_first = st.selectbox(
                    "🥇 1. Wahl:",
                    weekdays,
                    index=weekdays.index(current_prefs[0]) if len(current_prefs) > 0 and current_prefs[0] in weekdays else 0,
                    key="edit_first_choice"
                )
            
            with col2:
                available_second = [day for day in weekdays if day != edit_first]
                edit_second = st.selectbox(
                    "🥈 2. Wahl:",
                    available_second,
                    index=available_second.index(current_prefs[1]) if len(current_prefs) > 1 and current_prefs[1] in available_second else 0,
                    key="edit_second_choice"
                )
            
            with col3:
                available_third = [day for day in weekdays if day not in [edit_first, edit_second]]
                edit_third = st.selectbox(
                    "🥉 3. Wahl:",
                    available_third,
                    index=available_third.index(current_prefs[2]) if len(current_prefs) > 2 and current_prefs[2] in available_third else 0,
                    key="edit_third_choice"
                )
            
            with col4:
                available_fourth = [day for day in weekdays if day not in [edit_first, edit_second, edit_third]]
                edit_fourth = st.selectbox(
                    "🏅 4. Wahl:",
                    available_fourth,
                    index=available_fourth.index(current_prefs[3]) if len(current_prefs) > 3 and current_prefs[3] in available_fourth else 0,
                    key="edit_fourth_choice"
                )
            
            with col5:
                available_fifth = [day for day in weekdays if day not in [edit_first, edit_second, edit_third, edit_fourth]]
                edit_fifth = st.selectbox(
                    "🏅 5. Wahl:",
                    available_fifth,
                    index=available_fifth.index(current_prefs[4]) if len(current_prefs) > 4 and current_prefs[4] in available_fifth else 0,
                    key="edit_fifth_choice"
                )
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Änderungen speichern", type="primary"):
                    # Lösche alte Person wenn Name geändert wurde
                    if edit_name != st.session_state.edit_name:
                        delete_preference(st.session_state.edit_name)
                    
                    # Speichere neue/geänderte Person
                    new_prefs = [edit_first, edit_second, edit_third, edit_fourth, edit_fifth]
                    save_preferences(edit_name, new_prefs)
                    
                    st.success(f"✅ Person **{edit_name}** wurde aktualisiert!")
                    
                    # Reset edit mode
                    del st.session_state.edit_mode
                    del st.session_state.edit_name
                    del st.session_state.edit_prefs
                    st.rerun()
            
            with col_cancel:
                if st.button("❌ Abbrechen", type="secondary"):
                    # Reset edit mode
                    del st.session_state.edit_mode
                    del st.session_state.edit_name
                    del st.session_state.edit_prefs
                    st.rerun()
            
            st.divider()
        
        # Eingabeformular ohne Form (um Session State Problem zu vermeiden)
        st.subheader("Neue Person hinzufügen")
        
        # Initialisiere Session State für Formular-Reset
        if 'form_reset_trigger' not in st.session_state:
            st.session_state.form_reset_trigger = 0
        
        name = st.text_input(
            "Name des Mitarbeitenden:",
            placeholder="z.B. Max Mustermann",
            key=f"name_input_{st.session_state.form_reset_trigger}"
        )
        
        weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
        
        st.markdown("**Geben Sie Ihre 5 Wunsch-Wochentage in Prioritätsreihenfolge an:**")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
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
            chosen_days = []
            if first_choice != "Bitte wählen...":
                chosen_days.append(first_choice)
            available_second = [day for day in weekdays if day not in chosen_days]
            
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
        
        with col4:
            # Entferne bereits gewählte Optionen
            chosen_days = []
            if first_choice != "Bitte wählen...":
                chosen_days.append(first_choice)
            if second_choice != "Bitte wählen...":
                chosen_days.append(second_choice)
            if third_choice != "Bitte wählen...":
                chosen_days.append(third_choice)
            available_fourth = [day for day in weekdays if day not in chosen_days]
            
            fourth_choice = st.selectbox(
                "🏅 4. Wahl:",
                ["Bitte wählen..."] + available_fourth,
                index=0,
                help="Ihr viertliebster Wochentag",
                key=f"fourth_choice_{st.session_state.form_reset_trigger}"
            )
        
        with col5:
            # Entferne bereits gewählte Optionen
            chosen_days = []
            if first_choice != "Bitte wählen...":
                chosen_days.append(first_choice)
            if second_choice != "Bitte wählen...":
                chosen_days.append(second_choice)
            if third_choice != "Bitte wählen...":
                chosen_days.append(third_choice)
            if fourth_choice != "Bitte wählen...":
                chosen_days.append(fourth_choice)
            available_fifth = [day for day in weekdays if day not in chosen_days]
            
            fifth_choice = st.selectbox(
                "🏅 5. Wahl:",
                ["Bitte wählen..."] + available_fifth,
                index=0,
                help="Ihr fünftliebster Wochentag",
                key=f"fifth_choice_{st.session_state.form_reset_trigger}"
            )
        
        # Submit Button außerhalb des Forms
        submitted = st.button("Person speichern", type="primary", use_container_width=True)
        
        if submitted:
            # Validierung der Eingaben
            if not name.strip():
                st.error("❌ Bitte geben Sie einen Namen ein.")
            elif (first_choice == "Bitte wählen..." or 
                  second_choice == "Bitte wählen..." or 
                  third_choice == "Bitte wählen..." or
                  fourth_choice == "Bitte wählen..." or
                  fifth_choice == "Bitte wählen..."):
                # Zeige genau was noch fehlt
                missing = []
                if first_choice == "Bitte wählen...":
                    missing.append("🥇 1. Wahl")
                if second_choice == "Bitte wählen...":
                    missing.append("🥈 2. Wahl") 
                if third_choice == "Bitte wählen...":
                    missing.append("🥉 3. Wahl")
                if fourth_choice == "Bitte wählen...":
                    missing.append("🏅 4. Wahl")
                if fifth_choice == "Bitte wählen...":
                    missing.append("🏅 5. Wahl")
                
                st.error(f"❌ Bitte vervollständigen Sie Ihre Auswahl!")
                st.warning(f"💡 **Noch fehlend**: {' und '.join(missing)}")
                st.info("ℹ️ **Hinweis**: Sie müssen alle 5 Prioritäten (1., 2., 3., 4. und 5. Wahl) auswählen, um eine faire Schichtverteilung zu ermöglichen.")
            else:
                # Prüfe auf Duplikate
                choices = [first_choice, second_choice, third_choice, fourth_choice, fifth_choice]
                if len(set(choices)) != 5:
                    st.error("❌ Bitte wählen Sie 5 verschiedene Wochentage aus.")
                    st.warning(f"💡 **Problem**: Doppelte Auswahl erkannt. Jeder Tag darf nur einmal gewählt werden.")
                else:
                    # Alles korrekt - speichern
                    preferred_days = [first_choice, second_choice, third_choice, fourth_choice, fifth_choice]
                    save_preferences(name.strip(), preferred_days)
                    st.success(f"✅ Person **{name.strip()}** erfolgreich gespeichert! 🎉")
                    st.success(f"🎯 **Ihre Prioritäten**: 🥇 {first_choice} | 🥈 {second_choice} | 🥉 {third_choice} | 🏅 {fourth_choice} | 🏅 {fifth_choice}")
                    st.balloons()  # Kleine Feier! 🎈
                    # Reset das Formular durch Erhöhung des Triggers
                    st.session_state.form_reset_trigger += 1
                    st.rerun()
        
        # Bearbeitungs- und Löschoptionen
        if existing_prefs:
            st.divider()
            st.subheader("🔧 Personen bearbeiten/löschen")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Person bearbeiten:**")
                edit_name = st.selectbox(
                    "Person auswählen:",
                    ["Keine Auswahl"] + list(existing_prefs.keys()),
                    key="edit_selectbox"
                )
                
                if edit_name != "Keine Auswahl":
                    if st.button(f"✏️ {edit_name} bearbeiten", type="secondary"):
                        st.session_state.edit_mode = True
                        st.session_state.edit_name = edit_name
                        st.session_state.edit_prefs = existing_prefs[edit_name]
                        st.rerun()
            
            with col2:
                st.markdown("**Person löschen:**")
                delete_name = st.selectbox(
                    "Person auswählen:",
                    ["Keine Auswahl"] + list(existing_prefs.keys()),
                    key="delete_selectbox"
                )
                
                if delete_name != "Keine Auswahl":
                    if st.button(f"🗑️ {delete_name} löschen", type="secondary"):
                        if st.session_state.get("confirm_delete", False):
                            delete_preference(delete_name)
                            st.success(f"✅ Person **{delete_name}** wurde gelöscht.")
                            if "confirm_delete" in st.session_state:
                                del st.session_state["confirm_delete"]
                            st.rerun()
                        else:
                            st.session_state.confirm_delete = True
                            st.warning(f"⚠️ Klicken Sie erneut, um **{delete_name}** endgültig zu löschen!")
    
    elif mode == "Schichtplan generieren":
        st.header("⚙️ Schichtplan generieren")
        
        preferences = load_preferences()
        
        if len(preferences) == 0:
            st.warning("Noch keine Personen eingegeben. Bitte gehen Sie zu 'Personen eingeben'.")
            return
        
        st.write(f"**Anzahl eingetragener Mitarbeitender**: {len(preferences)}")
        

        
        # Übersicht der Personen (alphabetisch sortiert)
        st.subheader("Übersicht der Personen (alphabetisch sortiert)")
        prefs_df = pd.DataFrame([
            {
                "Name": name, 
                "🥇 1. Wahl": days[0] if len(days) > 0 else "",
                "🥈 2. Wahl": days[1] if len(days) > 1 else "",
                "🥉 3. Wahl": days[2] if len(days) > 2 else "",
                "🏅 4. Wahl": days[3] if len(days) > 3 else "",
                "🏅 5. Wahl": days[4] if len(days) > 4 else ""
            }
            for name, days in sorted(preferences.items())  # Alphabetische Sortierung
        ])
        st.dataframe(prefs_df, use_container_width=True)
        
        st.divider()
        
        # Generierung starten
        if st.button("🎯 Schichtplan generieren", type="primary"):
            with st.spinner("Generiere optimalen Schichtplan..."):
                schedule, assignment_count, preference_score, preference_stats = generate_fair_schedule(preferences)
                save_schedule(schedule)
                
                st.success("✅ Schichtplan erfolgreich generiert!")
                
                # Statistiken anzeigen
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Schichtverteilung")
                    stats_df = pd.DataFrame([
                        {"Name": name, "Anzahl Schichten": count}
                        for name, count in assignment_count.items()
                    ]).sort_values("Anzahl Schichten", ascending=False)
                    st.dataframe(stats_df, use_container_width=True)
                    
                    # Zeige Verteilungsstatistik
                    min_shifts = min(assignment_count.values())
                    max_shifts = max(assignment_count.values())
                    st.metric("Fairness", f"Spreizung: {max_shifts - min_shifts} Schichten", 
                             help="Unterschied zwischen Person mit meisten und wenigsten Schichten")
                
                with col2:
                    st.subheader("🎯 Detaillierte Wunscherfüllung")
                    
                    # Erstelle detaillierte Wunsch-Statistik
                    detailed_stats = []
                    for name in sorted(preferences.keys()):
                        total_assignments = assignment_count[name]
                        first_wishes = preference_stats[name]['first']
                        second_wishes = preference_stats[name]['second'] 
                        third_wishes = preference_stats[name]['third']
                        fourth_wishes = preference_stats[name]['fourth']
                        fifth_wishes = preference_stats[name]['fifth']
                        no_wishes = preference_stats[name]['none']
                        
                        detailed_stats.append({
                            "Name": name,
                            "🥇 1. Wünsche": first_wishes,
                            "🥈 2. Wünsche": second_wishes,
                            "🥉 3. Wünsche": third_wishes,
                            "🏅 4. Wünsche": fourth_wishes,
                            "🏅 5. Wünsche": fifth_wishes,
                            "❌ Keine Wünsche": no_wishes,
                            "Gesamt": total_assignments
                        })
                    
                    pref_df = pd.DataFrame(detailed_stats)
                    st.dataframe(pref_df, use_container_width=True)
                    
                    # Zeige Fairness-Metriken für Wünsche
                    total_first = sum(preference_stats[emp]['first'] for emp in preferences.keys())
                    total_second = sum(preference_stats[emp]['second'] for emp in preferences.keys())
                    total_third = sum(preference_stats[emp]['third'] for emp in preferences.keys())
                    total_fourth = sum(preference_stats[emp]['fourth'] for emp in preferences.keys())
                    total_fifth = sum(preference_stats[emp]['fifth'] for emp in preferences.keys())
                    
                    col_a, col_b, col_c, col_d, col_e = st.columns(5)
                    with col_a:
                        st.metric("🥇 1. Wünsche", total_first)
                    with col_b:
                        st.metric("🥈 2. Wünsche", total_second)
                    with col_c:
                        st.metric("🥉 3. Wünsche", total_third)
                    with col_d:
                        st.metric("🏅 4. Wünsche", total_fourth)
                    with col_e:
                        st.metric("🏅 5. Wünsche", total_fifth)
                
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
                ["Alle"] + sorted(set(schedule.values()))  # Bereits alphabetisch sortiert
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
            <small>📅 Schichtplaner 2025 | Effiziente Schichtplanung</small>
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main() 