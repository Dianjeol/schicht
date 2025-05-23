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
import holidays

# Seitenkonfiguration
st.set_page_config(
    page_title="🗓️ Schichtplaner Pro",
    page_icon="🗓️",
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
    
    # Tabelle für Urlaub und Nichtverfügbarkeit
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unavailability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,  -- 'urlaub' oder 'wochentag'
            date TEXT,           -- Für Urlaub: YYYY-MM-DD Format
            weekday TEXT,        -- Für Wochentag: z.B. 'Montag'
            reason TEXT,         -- Beschreibung/Grund
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

def save_unavailability(name, unavail_type, date=None, weekday=None, reason=""):
    """Speichert Urlaub oder Wochentag-Nichtverfügbarkeit"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO unavailability (name, type, date, weekday, reason)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, unavail_type, date, weekday, reason))
    
    conn.commit()
    conn.close()

def load_unavailability():
    """Lädt alle Urlaubs- und Nichtverfügbarkeitseinträge (alphabetisch sortiert)"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT name, type, date, weekday, reason FROM unavailability ORDER BY name, date, weekday')
    results = cursor.fetchall()
    
    conn.close()
    return results

def delete_unavailability(entry_id):
    """Löscht einen Urlaubs-/Nichtverfügbarkeitseintrag"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM unavailability WHERE id = ?', (entry_id,))
    
    conn.commit()
    conn.close()

def get_unavailability_by_id(entry_id):
    """Holt einen spezifischen Urlaubs-/Nichtverfügbarkeitseintrag"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, type, date, weekday, reason FROM unavailability WHERE id = ?', (entry_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result

def is_employee_unavailable(employee, date_obj):
    """Prüft ob ein Mitarbeiter an einem bestimmten Datum nicht verfügbar ist"""
    conn = sqlite3.connect('schichtplaner.db')
    cursor = conn.cursor()
    
    date_str = date_obj.strftime('%Y-%m-%d')
    weekday_name = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag'][date_obj.weekday()]
    
    # Prüfe Urlaub an diesem Datum
    cursor.execute('SELECT id FROM unavailability WHERE name = ? AND type = "urlaub" AND date = ?', (employee, date_str))
    if cursor.fetchone():
        conn.close()
        return True
    
    # Prüfe generelle Nichtverfügbarkeit an diesem Wochentag
    cursor.execute('SELECT id FROM unavailability WHERE name = ? AND type = "wochentag" AND weekday = ?', (employee, weekday_name))
    if cursor.fetchone():
        conn.close()
        return True
    
    conn.close()
    return False

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
def calculate_statistics_from_schedule(schedule_data):
    """Berechnet Statistiken aus vorhandenen Schichtplan-Daten (ohne Feiertage)"""
    if not schedule_data:
        return {}, {}
    
    # Lade Präferenzen für Wunscherfüllung
    preferences = load_preferences()
    
    # Initialisiere Zähler
    assignment_count = defaultdict(int)
    preference_stats = defaultdict(lambda: {'first': 0, 'second': 0, 'third': 0, 'fourth': 0, 'fifth': 0, 'none': 0})
    
    weekday_names = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
    
    # Durchlaufe alle Schichten und zähle (aber schließe Feiertage aus)
    for date_str, employee in schedule_data.items():
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Überspringe Feiertage bei der Statistik-Berechnung
            if is_holiday_berlin(date_obj):
                continue
                
            # Zähle Schichten
            assignment_count[employee] += 1
            
            # Bestimme Wochentag
            weekday_name = weekday_names[date_obj.weekday()]
            
            # Prüfe Wunscherfüllung
            if employee in preferences and weekday_name in preferences[employee]:
                priority_index = preferences[employee].index(weekday_name)
                if priority_index == 0:  # 1. Wahl
                    preference_stats[employee]['first'] += 1
                elif priority_index == 1:  # 2. Wahl
                    preference_stats[employee]['second'] += 1
                elif priority_index == 2:  # 3. Wahl
                    preference_stats[employee]['third'] += 1
                elif priority_index == 3:  # 4. Wahl
                    preference_stats[employee]['fourth'] += 1
                elif priority_index == 4:  # 5. Wahl
                    preference_stats[employee]['fifth'] += 1
            else:
                preference_stats[employee]['none'] += 1
        except (ValueError, IndexError):
            # Fehlerhafte Daten ignorieren
            preference_stats[employee]['none'] += 1
    
    return dict(assignment_count), dict(preference_stats)

def generate_pdf_report(schedule_data, title, weeks_data, include_statistics=False):
    """Generiert ein PDF-Report des Schichtplans mit optionalen Statistiken"""
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
    story.append(Paragraph("🌟 Schichtplaner 🌟", title_style))
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
    
    # Statistiken hinzufügen wenn gewünscht
    if include_statistics and schedule_data:
        story.append(Spacer(1, 30))
        
        # Berechne Statistiken aus den Schichtplan-Daten
        assignment_count, preference_stats = calculate_statistics_from_schedule(schedule_data)
        
        if assignment_count:
            # Heading für Statistiken
            stats_heading = ParagraphStyle(
                'StatsHeading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=15,
                textColor=colors.HexColor('#2E4057')
            )
            story.append(Paragraph("📊 Statistiken", stats_heading))
            
            # Schichtverteilung
            story.append(Paragraph("Schichtverteilung:", styles['Heading3']))
            stats_data = [["Name", "Anzahl Schichten"]]
            
            # Sortiere nach Anzahl Schichten (absteigend)
            sorted_assignments = sorted(assignment_count.items(), key=lambda x: x[1], reverse=True)
            for name, count in sorted_assignments:
                stats_data.append([name, str(count)])
            
            # Gesamtsumme
            if len(assignment_count) > 0:
                total_shifts = sum(assignment_count.values())
                stats_data.append(["", ""])  # Leerzeile
                stats_data.append(["Summe", f"{total_shifts} Schichten"])
            
            stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F4FD')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2E4057')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -2), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(stats_table)
            story.append(Spacer(1, 20))
            
            # Wunscherfüllung
            story.append(Paragraph("Detaillierte Wunscherfüllung:", styles['Heading3']))
            wish_data = [["Name", "🥇 1. Wünsche", "🥈 2. Wünsche", "🥉 3. Wünsche", "🏅 4. Wünsche", "🏅 5. Wünsche", "Gesamt"]]
            
            # Sortiere alphabetisch
            for name in sorted(preference_stats.keys()):
                stats = preference_stats[name]
                total = sum(stats.values())
                wish_data.append([
                    name,
                    str(stats['first']),
                    str(stats['second']),
                    str(stats['third']),
                    str(stats['fourth']),
                    str(stats['fifth']),
                    str(total)
                ])
            
            wish_table = Table(wish_data, colWidths=[1.8*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch])
            wish_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F4FD')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2E4057')),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
            ]))
            
            story.append(wish_table)
            
            # Zusammenfassung der Wünsche
            story.append(Spacer(1, 15))
            total_first = sum(stats['first'] for stats in preference_stats.values())
            total_second = sum(stats['second'] for stats in preference_stats.values())
            total_third = sum(stats['third'] for stats in preference_stats.values())
            total_fourth = sum(stats['fourth'] for stats in preference_stats.values())
            total_fifth = sum(stats['fifth'] for stats in preference_stats.values())
            
            summary_text = f"Gesamt-Wunscherfüllung: 🥇 {total_first} | 🥈 {total_second} | 🥉 {total_third} | 🏅 {total_fourth} | 🏅 {total_fifth}"
            story.append(Paragraph(summary_text, styles['Normal']))
    
    
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
def generate_fair_schedule(preferences, start_date=None, end_date=None, year=2025):
    """
    Generiert einen fairen Schichtplan mit User-für-User Rotation:
    1. Jeder Mitarbeiter kommt nacheinander dran (Round-Robin)
    2. Jedem wird der bestmögliche verfügbare Tag zugeteilt (vorzugsweise 1. Wunsch)
    3. Garantiert gleichmäßige Verteilung und maximale Wunscherfüllung
    
    Args:
        preferences: Dictionary mit Mitarbeiter-Präferenzen
        start_date: Startdatum (datetime object) - überschreibt year Parameter
        end_date: Enddatum (datetime object) - überschreibt year Parameter  
        year: Jahr für Generierung (nur verwendet wenn start_date/end_date nicht gesetzt)
    """
    # Bestimme Zeitraum
    if start_date is None or end_date is None:
        # Fallback auf Jahr-Parameter
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
    
    # Erstelle Liste aller Arbeitstage im Zeitraum (Mo-Fr, ohne Feiertage)
    
    available_days = []
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Montag = 0, Freitag = 4
            # Prüfe, ob es kein Feiertag in Berlin ist
            if not is_holiday_berlin(current_date):
                available_days.append(current_date)
        current_date += timedelta(days=1)
    
    
    
    # Initialisiere Zähler
    employees = list(preferences.keys())
    assignment_count = {emp: 0 for emp in employees}
    preference_stats = {emp: {'first': 0, 'second': 0, 'third': 0, 'fourth': 0, 'fifth': 0, 'none': 0} for emp in employees}
    schedule = {}
    
    # Wochentag-Namen für Zuordnung
    weekday_names = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
    
    # Round-Robin durch alle Mitarbeiter
    employee_index = 0
    
    while available_days:
        current_employee = employees[employee_index]
        
        # Finde den besten verfügbaren Tag für diesen Mitarbeiter
        best_day = None
        best_priority = 6  # Schlechter als alle Prioritäten (1-5)
        
        # Durchsuche verfügbare Tage nach bestem Match
        for day in available_days:
            # Prüfe ob Mitarbeiter an diesem Tag verfügbar ist
            if is_employee_unavailable(current_employee, day):
                continue  # Überspringe Urlaubs-/Nichtverfügbarkeitstage
                
            weekday_name = weekday_names[day.weekday()]
            
            if weekday_name in preferences[current_employee]:
                # Tag ist in den Präferenzen - bestimme Priorität
                priority = preferences[current_employee].index(weekday_name) + 1  # 1-5
                if priority < best_priority:
                    best_priority = priority
                    best_day = day
            else:
                # Tag ist nicht in Präferenzen - nur nehmen wenn nichts besseres da ist
                if best_priority == 6:
                    best_day = day
        
        # Falls kein Tag gefunden, suche nach anderen Mitarbeitern oder überspringe
        if best_day is None:
            # Wenn kein Tag für diesen Mitarbeiter verfügbar ist, überspringe ihn
            employee_index = (employee_index + 1) % len(employees)
            continue
        
        # Weise Tag zu
        schedule[best_day.strftime('%Y-%m-%d')] = current_employee
        available_days.remove(best_day)
        assignment_count[current_employee] += 1
        
        # Aktualisiere Präferenz-Statistiken
        weekday_name = weekday_names[best_day.weekday()]
        if weekday_name in preferences[current_employee]:
            priority_index = preferences[current_employee].index(weekday_name)
            if priority_index == 0:  # 1. Wahl
                preference_stats[current_employee]['first'] += 1
            elif priority_index == 1:  # 2. Wahl
                preference_stats[current_employee]['second'] += 1
            elif priority_index == 2:  # 3. Wahl
                preference_stats[current_employee]['third'] += 1
            elif priority_index == 3:  # 4. Wahl
                preference_stats[current_employee]['fourth'] += 1
            elif priority_index == 4:  # 5. Wahl
                preference_stats[current_employee]['fifth'] += 1
        else:
            preference_stats[current_employee]['none'] += 1
        
        # Nächster Mitarbeiter (Round-Robin)
        employee_index = (employee_index + 1) % len(employees)
    
    
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
        st.markdown("### 🔐 Schichtplaner - Zugang")
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
        st.markdown("### 🔐 Schichtplaner - Zugang")
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
    
    # Modernes Streamlit Design
    st.markdown("""
        <style>
        /* Modern Streamlit Design - Best Practices */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* Globale Variablen für moderne Farben */
        :root {
            --primary-blue: #1f77b4;
            --primary-dark: #0d47a1;
            --secondary-purple: #9c27b0;
            --accent-green: #4caf50;
            --accent-orange: #ff9800;
            --accent-red: #f44336;
            --background-light: #fafafa;
            --background-card: #ffffff;
            --text-primary: #2e3440;
            --text-secondary: #5e81ac;
            --border-light: #e3f2fd;
            --shadow-soft: 0 2px 10px rgba(0,0,0,0.08);
            --shadow-medium: 0 4px 20px rgba(0,0,0,0.12);
        }
        
        /* Hauptcontainer */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 0;
        }
        
        /* Header-Bereich */
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3rem 2rem 2rem 2rem;
            margin: -2rem -2rem 3rem -2rem;
            border-radius: 0 0 30px 30px;
            text-align: center;
            box-shadow: var(--shadow-medium);
        }
        
        .main-title {
            font-family: 'Inter', sans-serif;
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .main-subtitle {
            font-family: 'Inter', sans-serif;
            font-size: 1.2rem;
            font-weight: 300;
            opacity: 0.9;
            margin-bottom: 0;
        }
        
        /* Content Area */
        .content-container {
            background: var(--background-card);
            border-radius: 20px;
            padding: 2rem;
            margin: 1rem 0;
            box-shadow: var(--shadow-soft);
            border: 1px solid var(--border-light);
        }
        
        /* Moderne Button Styles */
        .stButton > button {
            background: linear-gradient(45deg, var(--primary-blue), var(--primary-dark));
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.75rem 2rem;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            font-size: 0.95rem;
            box-shadow: var(--shadow-soft);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 2px solid transparent;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-medium);
            background: linear-gradient(45deg, var(--primary-dark), var(--secondary-purple));
        }
        
        .stButton > button:focus {
            outline: none;
            border: 2px solid var(--accent-green);
            transform: translateY(-1px);
        }
        
        /* Sekundäre Buttons */
        .stButton > button[kind="secondary"] {
            background: linear-gradient(45deg, var(--text-secondary), var(--secondary-purple));
            color: white;
        }
        
        .stButton > button[kind="secondary"]:hover {
            background: linear-gradient(45deg, var(--secondary-purple), var(--accent-orange));
        }
        
        /* Sidebar Styling */
        .css-1d391kg, .css-17eq0hr {
            background: linear-gradient(180deg, var(--primary-dark) 0%, var(--secondary-purple) 100%);
        }
        
        .sidebar .sidebar-content {
            background: transparent;
            border-radius: 0 20px 20px 0;
        }
        
        /* Sidebar Navigation */
        .stRadio > label {
            color: white;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            font-size: 1rem;
        }
        
        /* Sidebar Radio Caption Styling */
        .stRadio > div > label {
            color: black !important;
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            font-size: 1rem;
        }
        
        .stRadio > div {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 1rem;
            margin: 0.5rem 0;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        /* Subheader Styling */
        h2, h3 {
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            border-bottom: 3px solid var(--primary-blue);
            padding-bottom: 0.5rem;
            margin-bottom: 1.5rem;
        }
        
        /* Input Styling */
        .stSelectbox > div > div, .stTextInput > div > div {
            border-radius: 12px;
            border: 2px solid var(--border-light);
            font-family: 'Inter', sans-serif;
            transition: all 0.3s ease;
        }
        
        .stSelectbox > div > div:focus-within, .stTextInput > div > div:focus-within {
            border-color: var(--primary-blue);
            box-shadow: 0 0 0 3px rgba(31, 119, 180, 0.1);
        }
        
        /* DataFrame Styling */
        .stDataFrame {
            border-radius: 15px;
            overflow: hidden;
            box-shadow: var(--shadow-soft);
            border: 1px solid var(--border-light);
        }
        
        .stDataFrame [data-testid="stDataFrameCell"] {
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
        }
        
        /* Info Boxes */
        .stInfo {
            background: linear-gradient(135deg, rgba(31, 119, 180, 0.1), rgba(156, 39, 176, 0.05));
            border-left: 4px solid var(--primary-blue);
            border-radius: 12px;
            font-family: 'Inter', sans-serif;
        }
        
        .stSuccess {
            background: linear-gradient(135deg, rgba(76, 175, 80, 0.1), rgba(102, 126, 234, 0.05));
            border-left: 4px solid var(--accent-green);
            border-radius: 12px;
            font-family: 'Inter', sans-serif;
        }
        
        .stWarning {
            background: linear-gradient(135deg, rgba(255, 152, 0, 0.1), rgba(244, 67, 54, 0.05));
            border-left: 4px solid var(--accent-orange);
            border-radius: 12px;
            font-family: 'Inter', sans-serif;
        }
        
        .stError {
            background: linear-gradient(135deg, rgba(244, 67, 54, 0.1), rgba(255, 152, 0, 0.05));
            border-left: 4px solid var(--accent-red);
            border-radius: 12px;
            font-family: 'Inter', sans-serif;
        }
        
        /* Metrics */
        .metric-container {
            background: var(--background-card);
            border-radius: 15px;
            padding: 1.5rem;
            box-shadow: var(--shadow-soft);
            border-left: 4px solid var(--primary-blue);
            font-family: 'Inter', sans-serif;
        }
        
        /* Download Buttons */
        .stDownloadButton > button {
            background: linear-gradient(45deg, var(--accent-green), #388e3c);
            color: white;
            border: none;
            border-radius: 12px;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            box-shadow: var(--shadow-soft);
            transition: all 0.3s ease;
        }
        
        .stDownloadButton > button:hover {
            background: linear-gradient(45deg, #388e3c, var(--secondary-purple));
            transform: translateY(-2px);
            box-shadow: var(--shadow-medium);
        }
        
        /* Toggle und Checkbox */
        .stCheckbox > label {
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            font-weight: 500;
        }
        
        /* Divider */
        hr {
            border: none;
            height: 2px;
            background: linear-gradient(90deg, var(--primary-blue), var(--secondary-purple), var(--accent-green));
            border-radius: 2px;
            margin: 3rem 0;
        }
        
        /* Responsive Design */
        @media (max-width: 768px) {
            .main-title {
                font-size: 2rem;
                padding: 1.5rem 1rem 1rem 1rem;
            }
            
            .awo-logo-container {
                top: 0.5rem;
                right: 0.5rem;
            }
            
            .awo-logo {
                height: 30px;
            }
        }
        
        /* Accessibility Improvements */
        button:focus {
            outline: 3px solid var(--awo-yellow);
            outline-offset: 2px;
        }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--awo-gray);
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, var(--awo-red), var(--awo-orange));
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, var(--awo-orange), var(--awo-red));
        }
        </style>
    """, unsafe_allow_html=True)
    
    
    # Haupttitel mit modernem Design
    st.markdown("""
        <div class="main-title">
            🗓️ Schichtplaner Pro
            <div class="main-subtitle">Effiziente Schichtplanung für Teams</div>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("*Berücksichtigt Feiertage für Berlin*")
    
    # Sidebar für Navigation
    st.sidebar.title("Navigation")
    mode = st.sidebar.radio(
        "Wählen Sie eine Option:",
        ["Personen eingeben", "Urlaub eintragen", "Schichtplan generieren", "Manuelle Änderungen", "Plan anzeigen"]
    )
    
    if mode == "Personen eingeben":
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
    
    elif mode == "Urlaub eintragen":
        st.header("🏖️ Urlaub und Nichtverfügbarkeit eintragen")
        
        preferences = load_preferences()
        
        if len(preferences) == 0:
            st.warning("Noch keine Personen eingegeben. Bitte gehen Sie zuerst zu 'Personen eingeben'.")
            return
        
        # Lade vorhandene Einträge
        unavail_entries = load_unavailability()
        
        # Zeige bereits eingetragene Urlaube/Nichtverfügbarkeiten
        if unavail_entries:
            st.subheader("Bereits eingetragene Urlaube und Nichtverfügbarkeiten:")
            
            # Erstelle DataFrame für bessere Darstellung
            entries_list = []
            for i, (name, entry_type, date, weekday, reason) in enumerate(unavail_entries):
                if entry_type == "urlaub":
                    if date:
                        date_obj = datetime.strptime(date, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%d.%m.%Y')
                        entry_desc = f"📅 Urlaub am {formatted_date}"
                    else:
                        entry_desc = "📅 Urlaub (Datum fehlt)"
                else:  # wochentag
                    entry_desc = f"⛔ Nie verfügbar am {weekday}"
                
                entries_list.append({
                    "Name": name,
                    "Art": entry_desc,
                    "Grund": reason if reason else "-",
                    "ID": i  # Für Löschen
                })
            
            entries_df = pd.DataFrame(entries_list)
            st.dataframe(entries_df[["Name", "Art", "Grund"]], use_container_width=True, hide_index=True)
            
            st.write(f"**Gesamt**: {len(unavail_entries)} Einträge")
        
        st.divider()
        
        # Eingabeformular
        st.subheader("Neue Nichtverfügbarkeit hinzufügen")
        
        # Initialisiere Session State für Formular-Reset
        if 'unavail_form_reset_trigger' not in st.session_state:
            st.session_state.unavail_form_reset_trigger = 0
        
        col1, col2 = st.columns(2)
        
        with col1:
            unavail_name = st.selectbox(
                "Person auswählen:",
                ["Bitte wählen..."] + list(preferences.keys()),
                key=f"unavail_name_{st.session_state.unavail_form_reset_trigger}"
            )
        
        with col2:
            unavail_type = st.radio(
                "Art der Nichtverfügbarkeit:",
                ["🏖️ Urlaub (spezifisches Datum)", "⛔ Generell nie verfügbar (Wochentag)"],
                key=f"unavail_type_{st.session_state.unavail_form_reset_trigger}"
            )
        
        if unavail_type == "🏖️ Urlaub (spezifisches Datum)":
            col3, col4 = st.columns(2)
            with col3:
                unavail_date = st.date_input(
                    "Urlaubsdatum:",
                    value=datetime.now().date(),
                    min_value=datetime(2025, 1, 1).date(),
                    max_value=datetime(2025, 12, 31).date(),
                    key=f"unavail_date_{st.session_state.unavail_form_reset_trigger}"
                )
            with col4:
                unavail_reason = st.text_input(
                    "Grund (optional):",
                    placeholder="z.B. Familienurlaub, Arzttermin...",
                    key=f"unavail_reason_{st.session_state.unavail_form_reset_trigger}"
                )
        else:  # Wochentag
            col3, col4 = st.columns(2)
            with col3:
                unavail_weekday = st.selectbox(
                    "Wochentag:",
                    ["Bitte wählen...", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"],
                    key=f"unavail_weekday_{st.session_state.unavail_form_reset_trigger}"
                )
            with col4:
                unavail_reason = st.text_input(
                    "Grund (optional):",
                    placeholder="z.B. Kinderbetreuung, andere Verpflichtung...",
                    key=f"unavail_reason_{st.session_state.unavail_form_reset_trigger}"
                )
        
        # Submit Button
        submitted = st.button("Nichtverfügbarkeit speichern", type="primary", use_container_width=True)
        
        if submitted:
            # Validierung der Eingaben
            if unavail_name == "Bitte wählen...":
                st.error("❌ Bitte wählen Sie eine Person aus.")
            elif unavail_type == "🏖️ Urlaub (spezifisches Datum)":
                # Prüfe Urlaubsdatum
                if unavail_date:
                    # Prüfe ob es ein Werktag ist
                    if unavail_date.weekday() >= 5:  # Samstag=5, Sonntag=6
                        st.error("❌ Urlaub kann nur für Werktage (Mo-Fr) eingetragen werden.")
                    else:
                        # Speichere Urlaub
                        save_unavailability(
                            unavail_name, 
                            "urlaub", 
                            date=unavail_date.strftime('%Y-%m-%d'),
                            reason=unavail_reason
                        )
                        st.success(f"✅ Urlaub für **{unavail_name}** am {unavail_date.strftime('%d.%m.%Y')} eingetragen! 🏖️")
                        # Reset das Formular
                        st.session_state.unavail_form_reset_trigger += 1
                        st.rerun()
                else:
                    st.error("❌ Bitte wählen Sie ein Datum aus.")
            else:  # Wochentag
                if unavail_weekday == "Bitte wählen...":
                    st.error("❌ Bitte wählen Sie einen Wochentag aus.")
                else:
                    # Speichere Wochentag-Nichtverfügbarkeit
                    save_unavailability(
                        unavail_name,
                        "wochentag",
                        weekday=unavail_weekday,
                        reason=unavail_reason
                    )
                    st.success(f"✅ **{unavail_name}** ist ab sofort nie am {unavail_weekday} verfügbar! ⛔")
                    # Reset das Formular
                    st.session_state.unavail_form_reset_trigger += 1
                    st.rerun()
        
        # Löschoptionen
        if unavail_entries:
            st.divider()
            st.subheader("🗑️ Einträge löschen")
            
            # Erstelle Optionen für Selectbox
            delete_options = ["Keine Auswahl"]
            for i, (name, entry_type, date, weekday, reason) in enumerate(unavail_entries):
                if entry_type == "urlaub":
                    if date:
                        date_obj = datetime.strptime(date, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%d.%m.%Y')
                        option_text = f"{name} - Urlaub am {formatted_date}"
                    else:
                        option_text = f"{name} - Urlaub (Datum fehlt)"
                else:  # wochentag
                    option_text = f"{name} - Nie verfügbar am {weekday}"
                
                if reason:
                    option_text += f" ({reason})"
                    
                delete_options.append(option_text)
            
            delete_selection = st.selectbox(
                "Eintrag zum Löschen auswählen:",
                delete_options,
                key="delete_unavail_selectbox"
            )
            
            if delete_selection != "Keine Auswahl":
                selected_index = delete_options.index(delete_selection) - 1  # -1 wegen "Keine Auswahl"
                
                if st.button(f"🗑️ Löschen: {delete_selection}", type="secondary"):
                    if st.session_state.get("confirm_delete_unavail", False):
                        # Lösche den Eintrag - wir brauchen die echte DB ID
                        conn = sqlite3.connect('schichtplaner.db')
                        cursor = conn.cursor()
                        cursor.execute('SELECT id FROM unavailability ORDER BY name, date, weekday LIMIT 1 OFFSET ?', (selected_index,))
                        result = cursor.fetchone()
                        if result:
                            entry_id = result[0]
                            delete_unavailability(entry_id)
                            st.success(f"✅ Eintrag wurde gelöscht.")
                        conn.close()
                        
                        if "confirm_delete_unavail" in st.session_state:
                            del st.session_state["confirm_delete_unavail"]
                        st.rerun()
                    else:
                        st.session_state.confirm_delete_unavail = True
                        st.warning(f"⚠️ Klicken Sie erneut, um den Eintrag endgültig zu löschen!")
    
    elif mode == "Schichtplan generieren":
        st.header("⚙️ Schichtplan generieren")
        
        preferences = load_preferences()
        
        if len(preferences) == 0:
            st.warning("Noch keine Personen eingegeben. Bitte gehen Sie zu 'Personen eingeben'.")
            return
        
        st.write(f"**Anzahl eingetragener Mitarbeitender**: {len(preferences)}")
        
        st.divider()
        
        # Zeitraum-Auswahl
        st.subheader("🗓️ Zeitraum für Schichtplan-Generierung")

        # Zeitraum-Modus auswählen
        time_mode = st.radio(
            "Zeitraum-Modus:",
            ["📅 Automatisch (1 Monat ab heute)", "📅 Automatisch (3 Monate ab heute)", "📅 Automatisch (1 Jahr ab heute)", "🎯 Benutzerdefiniert"],
            help="Wählen Sie zwischen automatischen Zeiträumen oder eigener Datumsauswahl"
        )

        if time_mode == "📅 Automatisch (1 Monat ab heute)":
            # Automatischer Zeitraum: Ab heute für 1 Monat
            today = datetime.now().date()
            schedule_start_date = datetime.combine(today, datetime.min.time())
            schedule_end_date = schedule_start_date + timedelta(days=30)
            
            # Berechne Anzahl Werktage ohne Feiertage
            weekdays = count_working_days(schedule_start_date, schedule_end_date)
            
            st.info(f"📆 **Automatischer Zeitraum**: {schedule_start_date.strftime('%d.%m.%Y')} - {schedule_end_date.strftime('%d.%m.%Y')} (1 Monat ab heute)")
            st.info(f"📊 **Werktage (Mo-Fr, ohne Feiertage)**: {weekdays}")
            schedule_valid = True

        elif time_mode == "📅 Automatisch (3 Monate ab heute)":
            # Automatischer Zeitraum: Ab heute für 3 Monate
            today = datetime.now().date()
            schedule_start_date = datetime.combine(today, datetime.min.time())
            schedule_end_date = schedule_start_date + timedelta(days=90)
            
            # Berechne Anzahl Werktage ohne Feiertage
            weekdays = count_working_days(schedule_start_date, schedule_end_date)
            
            st.info(f"📆 **Automatischer Zeitraum**: {schedule_start_date.strftime('%d.%m.%Y')} - {schedule_end_date.strftime('%d.%m.%Y')} (3 Monate ab heute)")
            st.info(f"📊 **Werktage (Mo-Fr, ohne Feiertage)**: {weekdays}")
            schedule_valid = True

        elif time_mode == "📅 Automatisch (1 Jahr ab heute)":
            # Automatischer Zeitraum: Ab heute für 1 Jahr
            today = datetime.now().date()
            schedule_start_date = datetime.combine(today, datetime.min.time())
            schedule_end_date = schedule_start_date + timedelta(days=365)
            
            # Berechne Anzahl Werktage ohne Feiertage
            weekdays = count_working_days(schedule_start_date, schedule_end_date)
            
            st.info(f"📆 **Automatischer Zeitraum**: {schedule_start_date.strftime('%d.%m.%Y')} - {schedule_end_date.strftime('%d.%m.%Y')} (1 Jahr ab heute)")
            st.info(f"📊 **Werktage (Mo-Fr, ohne Feiertage)**: {weekdays}")
            schedule_valid = True

        else:  # Benutzerdefiniert
            st.markdown("**🎯 Benutzerdefinierte Zeitraumauswahl:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                custom_start_date = st.date_input(
                    "Startdatum:",
                    value=datetime.now().date(),
                    min_value=datetime(2024, 1, 1).date(),
                    max_value=datetime(2030, 12, 31).date(),
                    help="Wählen Sie das Startdatum für den Schichtplan"
                )
            
            with col2:
                # Standardmäßig 1 Jahr nach Startdatum
                default_end_date = custom_start_date + timedelta(days=365) if custom_start_date else datetime.now().date() + timedelta(days=365)
                
                custom_end_date = st.date_input(
                    "Enddatum:",
                    value=default_end_date,
                    min_value=custom_start_date if custom_start_date else datetime(2024, 1, 1).date(),
                    max_value=datetime(2030, 12, 31).date(),
                    help="Wählen Sie das Enddatum für den Schichtplan"
                )
            
            # Validierung der benutzerdefinierten Eingaben
            if custom_start_date and custom_end_date:
                if custom_end_date <= custom_start_date:
                    st.error("❌ Das Enddatum muss nach dem Startdatum liegen!")
                    schedule_valid = False
                else:
                    # Konvertiere zu datetime objects
                    schedule_start_date = datetime.combine(custom_start_date, datetime.min.time())
                    schedule_end_date = datetime.combine(custom_end_date, datetime.min.time())
                    
                    # Berechne Zeitraumdauer und Werktage ohne Feiertage
                    duration_days = (schedule_end_date - schedule_start_date).days + 1
                    weekdays = count_working_days(schedule_start_date, schedule_end_date)
                    
                    # Warnungen für sehr kurze oder sehr lange Zeiträume
                    if duration_days < 30:
                        st.warning(f"⚠️ Kurzer Zeitraum: Nur {duration_days} Tage ({weekdays} Werktage ohne Feiertage)")
                    elif duration_days > 730:  # 2 Jahre
                        st.warning(f"⚠️ Langer Zeitraum: {duration_days} Tage ({weekdays} Werktage ohne Feiertage) - Generierung kann länger dauern")
                    
                    st.success(f"✅ **Zeitraum**: {schedule_start_date.strftime('%d.%m.%Y')} - {schedule_end_date.strftime('%d.%m.%Y')} ({duration_days} Tage)")
                    st.info(f"📊 **Werktage (Mo-Fr, ohne Feiertage)**: {weekdays}")
                    schedule_valid = True
            else:
                st.error("❌ Bitte wählen Sie Start- und Enddatum aus!")
                schedule_valid = False
        
        st.divider()
        
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
        
        # Generierung starten - nur wenn Zeitraum gültig ist
        schedule_button_disabled = False
        if time_mode == "🎯 Benutzerdefiniert":
            if 'schedule_valid' not in locals() or not schedule_valid:
                schedule_button_disabled = True
                
        if st.button("🎯 Schichtplan generieren", type="primary", disabled=schedule_button_disabled):
            with st.spinner("Generiere optimalen Schichtplan..."):
                schedule, assignment_count, preference_score, preference_stats = generate_fair_schedule(
                    preferences, 
                    start_date=schedule_start_date, 
                    end_date=schedule_end_date
                )
                save_schedule(schedule)
            
                # Berechne Anzahl generierter Schichten
                num_shifts = len(schedule)
                period_text = f"{schedule_start_date.strftime('%d.%m.%Y')} - {schedule_end_date.strftime('%d.%m.%Y')}"
                
                st.success(f"✅ Schichtplan erfolgreich generiert!")
                st.info(f"📅 **Zeitraum**: {period_text} | **Schichten**: {num_shifts}")
            
            # Statistiken anzeigen
            col1, col2 = st.columns([1, 3])
            
            with col1:
                st.subheader("📊 Schichtverteilung")
                stats_df = pd.DataFrame([
                    {"Name": name, "Anzahl Schichten": count}
                    for name, count in assignment_count.items()
                ]).sort_values("Anzahl Schichten", ascending=False)
                st.dataframe(stats_df, use_container_width=True)
                
                # Zeige Verteilungsstatistik
                total_shifts = sum(assignment_count.values())
                st.metric("Summe", f"{total_shifts} Schichten", 
                         help="Gesamtanzahl aller zugewiesenen Schichten")
            
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
    
    elif mode == "Manuelle Änderungen":
        st.header("✏️ Manuelle Änderungen")
        
        schedule = load_schedule()
        
        if not schedule:
            st.warning("Noch kein Schichtplan generiert. Bitte gehen Sie zu 'Schichtplan generieren'.")
            return
        
        preferences = load_preferences()
        if not preferences:
            st.warning("Keine Mitarbeitenden definiert. Bitte gehen Sie zu 'Personen eingeben'.")
            return
        
        st.info("💡 Hier können Sie einzelne Tage im Schichtplan tauschen oder ändern.")
        
        # Auswahl des Bearbeitungsmodus
        edit_mode = st.radio(
            "Was möchten Sie tun?",
            ["Einzelnen Tag ändern", "Zwei Tage tauschen"],
            horizontal=True
        )
        
        if edit_mode == "Einzelnen Tag ändern":
            st.subheader("📅 Einzelnen Tag ändern")
            
            # Erstelle Liste aller verfügbaren Tage
            date_options = []
            for date_str, employee in sorted(schedule.items()):
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                weekday_name = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][date_obj.weekday()]
                display_text = f"{date_obj.strftime('%d.%m.%Y')} ({weekday_name}) - {employee}"
                date_options.append((date_str, display_text))
            
            # Tag auswählen
            selected_date_info = st.selectbox(
                "Tag auswählen:",
                date_options,
                format_func=lambda x: x[1],
                help="Wählen Sie den Tag, den Sie ändern möchten"
            )
            
            if selected_date_info:
                selected_date_str = selected_date_info[0]
                current_employee = schedule[selected_date_str]
                date_obj = datetime.strptime(selected_date_str, '%Y-%m-%d')
                weekday_name = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][date_obj.weekday()]
                
                st.info(f"**Aktuell:** {date_obj.strftime('%d.%m.%Y')} ({weekday_name}) → {current_employee}")
                
                # Neuen Mitarbeiter auswählen
                employee_options = sorted(preferences.keys())
                try:
                    current_index = employee_options.index(current_employee)
                except ValueError:
                    current_index = 0
                
                new_employee = st.selectbox(
                    "Neuen Mitarbeiter auswählen:",
                    employee_options,
                    index=current_index,
                    help="Wählen Sie den Mitarbeiter, der an diesem Tag arbeiten soll"
                )
                
                # Warnung bei Änderung anzeigen
                if new_employee != current_employee:
                    st.warning(f"⚠️ Sie sind dabei, {current_employee} durch {new_employee} zu ersetzen.")
                    
                    # Prüfe Verfügbarkeit des neuen Mitarbeiters
                    if is_employee_unavailable(new_employee, date_obj):
                        st.error(f"❌ {new_employee} ist an diesem Tag nicht verfügbar (Urlaub oder Wochentag-Sperre)!")
                    
                    unavailable_reasons = []
                    if is_employee_unavailable(new_employee, date_obj):
                        unavailable_reasons.append("Urlaub oder Wochentag-Sperre")
                    if is_holiday_berlin(date_obj):
                        unavailable_reasons.append("Feiertag in Berlin")
                    
                    if unavailable_reasons:
                        reason_text = " und ".join(unavailable_reasons)
                        st.error(f"❌ {new_employee} ist an diesem Tag nicht verfügbar ({reason_text})!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Änderung bestätigen", type="primary"):
                            # Aktualisiere den Schedule
                            updated_schedule = schedule.copy()
                            updated_schedule[selected_date_str] = new_employee
                            save_schedule(updated_schedule)
                            st.success(f"✅ Tag erfolgreich geändert: {date_obj.strftime('%d.%m.%Y')} → {new_employee}")
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ Abbrechen", type="secondary"):
                            st.rerun()
                else:
                    st.info("💡 Keine Änderung ausgewählt.")
        
        elif edit_mode == "Zwei Tage tauschen":
            st.subheader("🔄 Zwei Tage tauschen")
            
            # Erstelle Liste aller verfügbaren Tage
            date_options = []
            for date_str, employee in sorted(schedule.items()):
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                weekday_name = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][date_obj.weekday()]
                display_text = f"{date_obj.strftime('%d.%m.%Y')} ({weekday_name}) - {employee}"
                date_options.append((date_str, display_text))
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Erster Tag:**")
                first_date_info = st.selectbox(
                    "Ersten Tag auswählen:",
                    date_options,
                    format_func=lambda x: x[1],
                    help="Wählen Sie den ersten Tag zum Tauschen",
                    key="first_date"
                )
            
            with col2:
                st.markdown("**Zweiter Tag:**")
                # Filtere den ersten Tag aus den Optionen heraus
                filtered_options = [opt for opt in date_options if opt != first_date_info] if first_date_info else date_options
                
                second_date_info = st.selectbox(
                    "Zweiten Tag auswählen:",
                    filtered_options,
                    format_func=lambda x: x[1],
                    help="Wählen Sie den zweiten Tag zum Tauschen",
                    key="second_date"
                )
            
            if first_date_info and second_date_info:
                first_date_str = first_date_info[0]
                second_date_str = second_date_info[0]
                
                first_employee = schedule[first_date_str]
                second_employee = schedule[second_date_str]
                
                first_date_obj = datetime.strptime(first_date_str, '%Y-%m-%d')
                second_date_obj = datetime.strptime(second_date_str, '%Y-%m-%d')
                
                first_weekday = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][first_date_obj.weekday()]
                second_weekday = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][second_date_obj.weekday()]
                
                st.info(f"""
                **Tausch-Vorschau:**
                - {first_date_obj.strftime('%d.%m.%Y')} ({first_weekday}): {first_employee} → {second_employee}
                - {second_date_obj.strftime('%d.%m.%Y')} ({second_weekday}): {second_employee} → {first_employee}
                """)
                
                # Prüfe Verfügbarkeit beider Mitarbeiter für die neuen Tage (inkl. Feiertage)
                warnings = []
                
                # Prüfe ersten Mitarbeiter (second_employee) am ersten Tag (first_date_obj)
                unavailable_reasons_first = []
                if is_employee_unavailable(second_employee, first_date_obj):
                    unavailable_reasons_first.append("Urlaub/Wochentag-Sperre")
                if is_holiday_berlin(first_date_obj):
                    unavailable_reasons_first.append("Feiertag")
                    
                if unavailable_reasons_first:
                    reason_text = "/".join(unavailable_reasons_first)
                    warnings.append(f"❌ {second_employee} ist am {first_date_obj.strftime('%d.%m.%Y')} nicht verfügbar ({reason_text})!")
                
                # Prüfe zweiten Mitarbeiter (first_employee) am zweiten Tag (second_date_obj)
                unavailable_reasons_second = []
                if is_employee_unavailable(first_employee, second_date_obj):
                    unavailable_reasons_second.append("Urlaub/Wochentag-Sperre")
                if is_holiday_berlin(second_date_obj):
                    unavailable_reasons_second.append("Feiertag")
                    
                if unavailable_reasons_second:
                    reason_text = "/".join(unavailable_reasons_second)
                    warnings.append(f"❌ {first_employee} ist am {second_date_obj.strftime('%d.%m.%Y')} nicht verfügbar ({reason_text})!")
                
                if warnings:
                    for warning in warnings:
                        st.error(warning)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 Tausch bestätigen", type="primary", disabled=bool(warnings)):
                        # Führe den Tausch durch
                        updated_schedule = schedule.copy()
                        updated_schedule[first_date_str] = second_employee
                        updated_schedule[second_date_str] = first_employee
                        save_schedule(updated_schedule)
                        st.success(f"✅ Tausch erfolgreich durchgeführt!")
                        st.rerun()
                
                with col2:
                    if st.button("❌ Abbrechen", type="secondary"):
                        st.rerun()
        
        st.divider()
        
        # Zeige aktuelle Übersicht der nächsten Wochen
        st.subheader("📋 Aktuelle Übersicht (nächste 4 Wochen)")
        
        # Hole die nächsten 4 Wochen
        current_weeks_schedule = get_current_and_next_weeks(schedule, 4)
        
        if current_weeks_schedule:
            # Baue weeks_data für aktuelle Wochen
            weekly_data_current = {}
            
            for date_str, employee in current_weeks_schedule.items():
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                year, week, weekday = date_obj.isocalendar()
                
                # Verwende tatsächliche Daten für Wochenberechnung
                week_start = date_obj - timedelta(days=date_obj.weekday())
                week_end = week_start + timedelta(days=4)
                
                kw_display = f"KW {week:02d}"
                date_range = f"{week_start.strftime('%d.%m.')} - {week_end.strftime('%d.%m.')}"
                kw_key = f"{week:02d}-{year}"
                
                if kw_key not in weekly_data_current:
                    weekly_data_current[kw_key] = {
                        "Kalenderwoche": f"{kw_display} ({date_range})",
                        "Montag": "",
                        "Dienstag": "",
                        "Mittwoch": "",
                        "Donnerstag": "",
                        "Freitag": "",
                        "sort_key": f"{year}-{week:02d}",
                        "week_start": week_start  # Für Feiertags-Überprüfung
                    }
                
                weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                if weekday in weekday_names:
                    day_name = weekday_names[weekday]
                    # Prüfe ob es ein Feiertag ist
                    if is_holiday_berlin(date_obj):
                        weekly_data_current[kw_key][day_name] = "—"
                    else:
                        weekly_data_current[kw_key][day_name] = employee
            
            # Zusätzlich: Fülle alle Feiertage der Kalenderwochen mit "—" auf
            for kw_key, week_info in weekly_data_current.items():
                week_start = week_info["week_start"]
                weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                
                # Prüfe jeden Wochentag der Kalenderwoche auf Feiertage
                for weekday_num, day_name in weekday_names.items():
                    current_date = week_start + timedelta(days=weekday_num - 1)
                    
                    # Wenn das Feld leer ist und es ein Feiertag ist, fülle mit "—"
                    if week_info[day_name] == "" and is_holiday_berlin(current_date):
                        weekly_data_current[kw_key][day_name] = "—"
            
            # Sortiere nach Kalenderwoche und Jahr
            sorted_weeks_current = sorted(weekly_data_current.keys(), key=lambda x: weekly_data_current[x]["sort_key"])
            sorted_data_current = [weekly_data_current[kw] for kw in sorted_weeks_current]
            
            # Entferne sort_key und week_start aus den Daten für die Anzeige
            for data in sorted_data_current:
                data.pop("sort_key", None)
                data.pop("week_start", None)
            
            # Erstelle DataFrame
            current_df = pd.DataFrame(sorted_data_current)
            
            st.dataframe(
                current_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Kalenderwoche": st.column_config.TextColumn("📅 Kalenderwoche", width="medium"),
                    "Montag": st.column_config.TextColumn("🔵 Montag", width="medium"),
                    "Dienstag": st.column_config.TextColumn("🟢 Dienstag", width="medium"),
                    "Mittwoch": st.column_config.TextColumn("🟡 Mittwoch", width="medium"),
                    "Donnerstag": st.column_config.TextColumn("🟠 Donnerstag", width="medium"),
                    "Freitag": st.column_config.TextColumn("🔴 Freitag", width="medium")
                }
            )
        else:
            st.info("Keine Daten für die nächsten 4 Wochen verfügbar.")

    elif mode == "Plan anzeigen":
        # Automatisch zum Seitenanfang scrollen
        st.markdown("""
            <style>
                .main .block-container {
                    scroll-behavior: smooth;
                }
            </style>
            <script>
                setTimeout(function() {
                    var mainContent = window.parent.document.querySelector('section.main');
                    if (mainContent) {
                        mainContent.scrollTop = 0;
                    }
                }, 50);
            </script>
        """, unsafe_allow_html=True)
        
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
                ["Alle"] + [f"{i:02d} - {datetime(datetime.now().year, i, 1).strftime('%B')}" for i in range(1, 13)]
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
            # Erstelle Kalenderwochen-Tabelle basierend auf tatsächlichen Daten
            weekly_data = {}
            
            for date_str, employee in filtered_schedule.items():
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Berechne Kalenderwoche
                year, week, weekday = date_obj.isocalendar()
                
                # Verwende tatsächliche Daten für Wochenberechnung
                # Finde Montag dieser Woche
                week_start = date_obj - timedelta(days=date_obj.weekday())
                # Finde Freitag dieser Woche  
                week_end = week_start + timedelta(days=4)
                
                # Formatiere die KW mit Datumsbereich
                kw_display = f"KW {week:02d}"
                date_range = f"{week_start.strftime('%d.%m.')} - {week_end.strftime('%d.%m.')}"
                kw_key = f"{week:02d}-{year}"  # Eindeutiger Key mit Jahr
                
                if kw_key not in weekly_data:
                    # Formatiere mit grauen Klammern und Datum
                    kw_formatted = f"{kw_display} ({date_range})"
                    weekly_data[kw_key] = {
                        "Kalenderwoche": kw_formatted,
                        "Montag": "",
                        "Dienstag": "",
                        "Mittwoch": "",
                        "Donnerstag": "",
                        "Freitag": "",
                        "sort_key": f"{year}-{week:02d}",  # Für korrekte Sortierung
                        "week_start": week_start  # Für Feiertags-Überprüfung
                    }
                
                # Weekday: 1=Montag, 2=Dienstag, ..., 5=Freitag
                weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                
                if weekday in weekday_names:
                    day_name = weekday_names[weekday]
                    # Prüfe ob es ein Feiertag ist
                    if is_holiday_berlin(date_obj):
                        weekly_data[kw_key][day_name] = "—"
                    else:
                        weekly_data[kw_key][day_name] = employee
            
            # Zusätzlich: Fülle alle Feiertage der Kalenderwochen mit "—" auf
            for kw_key, week_info in weekly_data.items():
                week_start = week_info["week_start"]
                weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                
                # Prüfe jeden Wochentag der Kalenderwoche auf Feiertage
                for weekday_num, day_name in weekday_names.items():
                    current_date = week_start + timedelta(days=weekday_num - 1)
                    
                    # Wenn das Feld leer ist und es ein Feiertag ist, fülle mit "—"
                    if week_info[day_name] == "" and is_holiday_berlin(current_date):
                        weekly_data[kw_key][day_name] = "—"
            
            # Sortiere nach Kalenderwoche und Jahr
            sorted_weeks = sorted(weekly_data.keys(), key=lambda x: weekly_data[x]["sort_key"])
            sorted_data = [weekly_data[kw] for kw in sorted_weeks]
            
            # Entferne sort_key und week_start aus den Daten für die Anzeige
            for data in sorted_data:
                data.pop("sort_key", None)
                data.pop("week_start", None)
            
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
                    # Prüfe ob es ein Feiertag ist
                    if is_holiday_berlin(date_obj):
                        display_employee = "—"
                    else:
                        display_employee = employee
                        
                    list_data.append({
                        "Datum": date_obj.strftime('%d.%m.%Y'),
                        "Wochentag": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][date_obj.weekday()],
                        "Mitarbeiter": display_employee
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
                    file_name=f"schichtplan_kalenderwochen_{datetime.now().year}.csv",
                    mime="text/csv"
                )
                
                # Listen-CSV
                if filtered_schedule:
                    list_data = []
                    for date_str, employee in sorted(filtered_schedule.items()):
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        # Prüfe ob es ein Feiertag ist
                        if is_holiday_berlin(date_obj):
                            display_employee = "—"
                        else:
                            display_employee = employee
                            
                        list_data.append({
                            "Datum": date_obj.strftime('%d.%m.%Y'),
                            "Wochentag": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"][date_obj.weekday()],
                            "Mitarbeiter": display_employee
                        })
                    
                    list_df = pd.DataFrame(list_data)
                    list_csv = list_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📋 Listen-Plan (CSV)",
                        data=list_csv,
                        file_name=f"schichtplan_liste_{datetime.now().year}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                st.markdown("**📄 PDF-Downloads:**")
                
                # Gesamter Zeitraum PDF
                try:
                    # Bestimme Start- und Enddatum aus dem filtered_schedule
                    if filtered_schedule:
                        dates = [datetime.strptime(date_str, '%Y-%m-%d') for date_str in filtered_schedule.keys()]
                        start_date = min(dates)
                        end_date = max(dates)
                        period_text = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
                        filename_period = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
                    else:
                        period_text = "Zeitraum"
                        filename_period = "zeitraum"
                    
                    full_period_pdf = generate_pdf_report(
                        filtered_schedule, 
                        f"Schichtplan {period_text} ({len(sorted_data)} Kalenderwochen)",
                        sorted_data,
                        include_statistics=True  # Für Zeitraum-PDF Statistiken hinzufügen
                    )
                    st.download_button(
                        label="🗓️ Gesamter Zeitraum (PDF)",
                        data=full_period_pdf.getvalue(),
                        file_name=f"schichtplan_{filename_period}.pdf",
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
                            
                            # Verwende tatsächliche Daten für Wochenberechnung
                            week_start = date_obj - timedelta(days=date_obj.weekday())
                            week_end = week_start + timedelta(days=4)
                            
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
                                    "Freitag": "",
                                    "week_start": week_start  # Für Feiertags-Überprüfung
                                }
                            
                            weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                            if weekday in weekday_names:
                                day_name = weekday_names[weekday]
                                # Prüfe ob es ein Feiertag ist
                                if is_holiday_berlin(date_obj):
                                    weekly_data_current[kw_key][day_name] = "—"
                                else:
                                    weekly_data_current[kw_key][day_name] = employee
                        
                        # Zusätzlich: Fülle alle Feiertage der Kalenderwochen mit "—" auf
                        for kw_key, week_info in weekly_data_current.items():
                            week_start = week_info["week_start"]
                            weekday_names = {1: "Montag", 2: "Dienstag", 3: "Mittwoch", 4: "Donnerstag", 5: "Freitag"}
                            
                            # Prüfe jeden Wochentag der Kalenderwoche auf Feiertage
                            for weekday_num, day_name in weekday_names.items():
                                current_date = week_start + timedelta(days=weekday_num - 1)
                                
                                # Wenn das Feld leer ist und es ein Feiertag ist, fülle mit "—"
                                if week_info[day_name] == "" and is_holiday_berlin(current_date):
                                    weekly_data_current[kw_key][day_name] = "—"
                        
                        sorted_weeks_current = sorted(weekly_data_current.keys(), key=lambda x: int(x.split()[1]))
                        sorted_data_current = [weekly_data_current[kw] for kw in sorted_weeks_current]
                        
                        # Entferne week_start aus den Daten für die PDF-Generierung
                        for data in sorted_data_current:
                            data.pop("week_start", None)
                        
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
                    
                # Alte get_week_dates Funktion entfernt - wird nicht mehr benötigt
            
            # Statistiken anzeigen
            st.divider()
            st.subheader("📊 Statistiken zum angezeigten Zeitraum")
            
            # Lade Präferenzen für Statistiken
            preferences = load_preferences()
            
            if preferences:
                # Berechne Statistiken basierend auf dem gefilterten Schedule
                assignment_count, preference_stats = calculate_statistics_from_schedule(filtered_schedule)
                
                if assignment_count:
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.subheader("📊 Schichtverteilung")
                        stats_df = pd.DataFrame([
                            {"Name": name, "Anzahl Schichten": count}
                            for name, count in assignment_count.items()
                        ]).sort_values("Anzahl Schichten", ascending=False)
                        st.dataframe(stats_df, use_container_width=True)
                        
                        # Zeige Gesamtsumme
                        total_shifts = sum(assignment_count.values())
                        st.metric("Summe", f"{total_shifts} Schichten", 
                                 help="Gesamtanzahl aller zugewiesenen Schichten")
                    
                    with col2:
                        st.subheader("🎯 Detaillierte Wunscherfüllung")
                        
                        # Erstelle detaillierte Wunsch-Statistik
                        detailed_stats = []
                        for name in sorted(preferences.keys()):
                            if name in assignment_count:  # Nur Mitarbeiter anzeigen, die im gefilterten Zeitraum Schichten haben
                                total_assignments = assignment_count[name]
                                first_wishes = preference_stats[name]['first']
                                second_wishes = preference_stats[name]['second'] 
                                third_wishes = preference_stats[name]['third']
                                fourth_wishes = preference_stats[name]['fourth']
                                fifth_wishes = preference_stats[name]['fifth']
                                
                                detailed_stats.append({
                                    "Name": name,
                                    "🥇 1. Wünsche": first_wishes,
                                    "🥈 2. Wünsche": second_wishes,
                                    "🥉 3. Wünsche": third_wishes,
                                    "🏅 4. Wünsche": fourth_wishes,
                                    "🏅 5. Wünsche": fifth_wishes,
                                    "Gesamt": total_assignments
                                })
                        
                        pref_df = pd.DataFrame(detailed_stats)
                        st.dataframe(pref_df, use_container_width=True)
                        
                        # Zeige Fairness-Metriken für Wünsche
                        total_first = sum(preference_stats[emp]['first'] for emp in assignment_count.keys())
                        total_second = sum(preference_stats[emp]['second'] for emp in assignment_count.keys())
                        total_third = sum(preference_stats[emp]['third'] for emp in assignment_count.keys())
                        total_fourth = sum(preference_stats[emp]['fourth'] for emp in assignment_count.keys())
                        total_fifth = sum(preference_stats[emp]['fifth'] for emp in assignment_count.keys())
                        
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
                else:
                    st.info("Keine Daten für Statistiken im gewählten Zeitraum verfügbar.")
            else:
                st.warning("Keine Mitarbeiterpräferenzen gefunden. Statistiken können nicht berechnet werden.")
                    
        else:
            st.info("Keine Einträge für die gewählten Filter gefunden.")
    
    # AWO Footer
    st.markdown("""
        <div class="modern-footer">
            <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                <div>
                    <div style="font-size: 1.5rem; font-weight: 700;">🗓️ Schichtplaner Pro</div>
                    <div style="font-size: 1rem; opacity: 0.9;">Intelligente Schichtplanung • Automatisiert • Benutzerfreundlich</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def is_holiday_berlin(date_obj):
    """Prüft ob ein Datum ein gesetzlicher Feiertag in Berlin ist"""
    berlin_holidays = holidays.Germany(state='BE', years=date_obj.year)
    return date_obj in berlin_holidays

def count_working_days(start_date, end_date):
    """Zählt Werktage (Mo-Fr) ohne Feiertage in Berlin im gegebenen Zeitraum"""
    count = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Montag = 0, Freitag = 4
            if not is_holiday_berlin(current_date):
                count += 1
        current_date += timedelta(days=1)
    return count

if __name__ == "__main__":
    main() 