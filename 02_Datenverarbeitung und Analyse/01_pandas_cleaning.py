"""
=============================================================================
SKRIPT 2: PANDAS - DATA CLEANING & TRANSFORMATION
=============================================================================

USE CASE:
---------
Rohdaten sind nie perfekt! Als Data Analyst müssen wir Daten bereinigen,
transformieren und strukturieren, bevor wir sie analysieren können.
Pandas ist DAS Werkzeug dafür - wie Excel auf Steroiden!

ZIELE DIESES SKRIPTS:
----------------------
1. Datentypen korrigieren (Text → Zahlen, Datumswerte)
2. Fehlende Werte behandeln (Missing Data Strategy)
3. Neue Features erstellen (Feature Engineering)
4. Daten gruppieren und aggregieren (Group By)
5. Zeitreihen-Analysen durchführen
6. Top-Performer identifizieren

BUSINESS IMPACT:
----------------
- Saubere Daten = bessere Entscheidungen
- Feature Engineering = neue Insights
- Aggregationen = Management-Reports
- Zeit-Analysen = Trend-Erkennung
"""

# Bibliotheken importieren
import pandas as pd                   # Pandas für Datenverarbeitung
import numpy as np                    # NumPy für numerische Operationen
import warnings
warnings.filterwarnings('ignore')

# Pandas Display-Einstellungen optimieren
pd.set_option('display.max_columns', None)      # Zeige alle Spalten
pd.set_option('display.width', 120)             # Breitere Ausgabe
pd.set_option('display.precision', 2)           # 2 Dezimalstellen

print("=" * 100)
print("PANDAS DATA CLEANING & TRANSFORMATION PIPELINE")
print("=" * 100)
print()

# ============================================================================
# SCHRITT 1: DATEN EINLESEN UND INSPIZIEREN
# ============================================================================
print("📂 Schritt 1: Daten einlesen und ersten Überblick bekommen...")
print("-" * 100)

# CSV einlesen mit speziellem Separator (Semikolon statt Komma)
df = pd.read_csv('all_raw_data_100to2000.csv', sep=';')

print(f"✓ Datensatz eingelesen: {df.shape[0]:,} Zeilen × {df.shape[1]} Spalten")
print()

# Erste 3 Zeilen anzeigen (wie "Vorschau" in Excel)
print("Erste 3 Zeilen:")
print(df.head(3))
print()

# Datentypen überprüfen
print("Aktuelle Datentypen:")
print(df.dtypes)
print()

# ============================================================================
# SCHRITT 2: DATENQUALITÄT PRÜFEN (MISSING VALUES)
# ============================================================================
print("🔍 Schritt 2: Datenqualität analysieren...")
print("-" * 100)

# Zähle fehlende Werte pro Spalte
missing_counts = df.isnull().sum()
missing_percent = (df.isnull().sum() / len(df) * 100).round(2)

# Erstelle einen übersichtlichen Report
missing_report = pd.DataFrame({
    'Fehlende Werte': missing_counts,
    'Prozent': missing_percent
})

# Zeige nur Spalten mit fehlenden Werten
missing_report = missing_report[missing_report['Fehlende Werte'] > 0].sort_values('Fehlende Werte', ascending=False)

print("Fehlende Werte pro Spalte:")
print(missing_report)
print()

# ============================================================================
# SCHRITT 3: DATENTYPEN KORRIGIEREN
# ============================================================================
print("🔧 Schritt 3: Datentypen korrigieren...")
print("-" * 100)

# Problem 1: 'Odd' ist als Text gespeichert, sollte aber Zahl sein
print("Korrigiere 'Odd' (Quote) von Text zu Nummer...")
df['Odd'] = pd.to_numeric(df['Odd'], errors='coerce')
# errors='coerce' bedeutet: Wenn Konvertierung nicht klappt, setze NaN

# Problem 2: 'Yield' hat Prozentzeichen ("7%"), muss bereinigt werden
print("Korrigiere 'Yield' von '7%' zu 0.07...")
df['Yield'] = df['Yield'].str.rstrip('%').astype(float) / 100
# .str.rstrip('%') entfernt das %-Zeichen am Ende
# / 100 konvertiert von Prozent zu Dezimal

# Problem 3: Datumswerte sind als Text gespeichert
print("Konvertiere Datumswerte...")
df['Publish_date'] = pd.to_datetime(df['Publish_date'], format='%d/%m/%Y %H:%M', errors='coerce')
df['Kickoff_Date'] = pd.to_datetime(df['Kickoff_Date'], format='%d/%m/%Y %H:%M', errors='coerce')

# Problem 4: 'Registered_at' ist Jahr als Dezimalzahl
df['Registered_at'] = df['Registered_at'].astype('Int64')  # Int64 erlaubt NaN-Werte

print("✓ Datentypen korrigiert!")
print()

# ============================================================================
# SCHRITT 4: FEHLENDE WERTE BEHANDELN
# ============================================================================
print("🩹 Schritt 4: Fehlende Werte behandeln...")
print("-" * 100)

# Strategie 1: Füllen mit sinnvollem Standardwert
print("Fülle 'Sport' mit 'Unknown' wo leer...")
df['Sport'].fillna('Unknown', inplace=True)

print("Fülle 'Bet_Country' mit 'International' wo leer...")
df['Bet_Country'].fillna('International', inplace=True)

# Strategie 2: Zeilen löschen wo kritische Werte fehlen
print("Lösche Zeilen wo 'Odd' oder 'Lable' fehlt (kritisch für Analyse)...")
original_rows = len(df)
df.dropna(subset=['Odd', 'Lable'], inplace=True)
deleted_rows = original_rows - len(df)
print(f"  └─ {deleted_rows:,} Zeilen gelöscht ({deleted_rows/original_rows*100:.2f}%)")
print()

# ============================================================================
# SCHRITT 5: FEATURE ENGINEERING - NEUE SPALTEN ERSTELLEN
# ============================================================================
print("⚙️ Schritt 5: Feature Engineering - neue Variablen erstellen...")
print("-" * 100)

# Feature 1: Zeitbasierte Features
print("Erstelle Zeit-Features aus Publish_date...")
df['Hour_Published'] = df['Publish_date'].dt.hour                    # Stunde (0-23)
df['Day_of_Week'] = df['Publish_date'].dt.day_name()                 # Wochentag (Monday, ...)
df['Month'] = df['Publish_date'].dt.month                             # Monat (1-12)
df['Year'] = df['Publish_date'].dt.year                               # Jahr
df['Is_Weekend'] = df['Publish_date'].dt.dayofweek.isin([5, 6])      # Samstag/Sonntag

# Feature 2: Kategorische Quote-Segmente
print("Erstelle Quoten-Kategorien...")
df['Odds_Category'] = pd.cut(
    df['Odd'],
    bins=[0, 1.5, 2.0, 3.0, 5.0, 100],
    labels=['Sehr niedrig', 'Niedrig', 'Mittel', 'Hoch', 'Sehr hoch']
)

# Feature 3: Win/Loss als numerische Variable (1/0)
print("Erstelle numerische Win-Flag...")
df['Win_Binary'] = (df['Lable'] == 'WIN').astype(int)

# Feature 4: ROI pro Wette
print("Berechne ROI pro Wette...")
df['ROI'] = np.where(df['Win_Binary'] == 1, df['Odd'] - 1, -1)

print("✓ Neue Features erstellt!")
print(f"  └─ Jetzt haben wir {df.shape[1]} Spalten (vorher: 26)")
print()

# ============================================================================
# SCHRITT 6: GRUPPIEREN UND AGGREGIEREN (GROUP BY)
# ============================================================================
print("📊 Schritt 6: Daten gruppieren für Business Insights...")
print("-" * 100)

# Analyse 1: Performance nach Sportart
print("\n1️⃣ Performance nach Sportart:")
print("-" * 100)

sport_analysis = df.groupby('Sport').agg({
    'Win_Binary': ['sum', 'mean', 'count'],    # Anzahl Wins, Win-Rate, Anzahl Wetten
    'Odd': 'mean',                              # Durchschnitts-Quote
    'Profit': 'sum',                            # Gesamt-Profit
    'ROI': 'mean'                               # Durchschnittlicher ROI
}).round(3)

# Spalten-Namen vereinfachen
sport_analysis.columns = ['Anzahl_Wins', 'Win_Rate', 'Anzahl_Wetten', 'Avg_Odd', 'Total_Profit', 'Avg_ROI']

# Sortiere nach Total Profit
sport_analysis = sport_analysis.sort_values('Total_Profit', ascending=False)

# Zeige Top 10 Sportarten
print(sport_analysis.head(10))
print()

# Analyse 2: Performance nach Wochentag
print("\n2️⃣ Performance nach Wochentag:")
print("-" * 100)

# Definiere die richtige Reihenfolge der Wochentage
weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

weekday_analysis = df.groupby('Day_of_Week').agg({
    'Win_Binary': 'mean',
    'ROI': 'mean',
    'Odd': 'count'
}).round(3)

weekday_analysis.columns = ['Win_Rate', 'Avg_ROI', 'Anzahl_Wetten']

# Sortiere nach Wochentag
weekday_analysis = weekday_analysis.reindex(weekday_order)

print(weekday_analysis)
print()

# Analyse 3: Performance nach Tageszeit
print("\n3️⃣ Performance nach Tageszeit:")
print("-" * 100)

# Erstelle Tageszeit-Kategorien
df['Time_of_Day'] = pd.cut(
    df['Hour_Published'],
    bins=[0, 6, 12, 18, 24],
    labels=['Nacht (0-6)', 'Morgen (6-12)', 'Nachmittag (12-18)', 'Abend (18-24)'],
    include_lowest=True
)

time_analysis = df.groupby('Time_of_Day').agg({
    'Win_Binary': 'mean',
    'ROI': 'mean',
    'Odd': 'count'
}).round(3)

time_analysis.columns = ['Win_Rate', 'Avg_ROI', 'Anzahl_Wetten']

print(time_analysis)
print()

# ============================================================================
# SCHRITT 7: TOP-PERFORMER IDENTIFIZIEREN
# ============================================================================
print("🏆 Schritt 7: Top-Performer (User) identifizieren...")
print("-" * 100)

# Aggregiere Daten pro User
user_performance = df.groupby('Username').agg({
    'Profit': 'sum',                    # Gesamt-Profit
    'Win_Binary': 'mean',               # Win-Rate
    'Lable': 'count',                   # Anzahl Tipps
    '#Followers': 'first',              # Anzahl Follower
    'Yield': 'first'                    # Yield
}).round(3)

user_performance.columns = ['Total_Profit', 'Win_Rate', 'Anzahl_Tipps', 'Followers', 'Yield']

# Filter: Nur User mit mindestens 50 Tipps (statistisch relevant)
user_performance = user_performance[user_performance['Anzahl_Tipps'] >= 50]

# Sortiere nach Profit
user_performance = user_performance.sort_values('Total_Profit', ascending=False)

print("Top 10 profitabelste User:")
print(user_performance.head(10))
print()

print("Top 10 User mit höchster Win-Rate (min. 50 Tipps):")
top_winrate = user_performance.sort_values('Win_Rate', ascending=False)
print(top_winrate.head(10))
print()

# ============================================================================
# SCHRITT 8: PIVOT-TABELLEN (WIE IN EXCEL)
# ============================================================================
print("📋 Schritt 8: Pivot-Tabellen erstellen...")
print("-" * 100)

# Erstelle eine Pivot-Tabelle: Sport × Result
print("Pivot: Profit nach Sport und Ergebnis (WIN/LOST)")
print("-" * 100)

pivot_sport_result = pd.pivot_table(
    df,
    values='Profit',
    index='Sport',
    columns='Lable',
    aggfunc='sum',
    fill_value=0
).round(2)

# Füge Total-Spalte hinzu
pivot_sport_result['TOTAL'] = pivot_sport_result['WIN'] + pivot_sport_result['LOST']

# Sortiere nach Total
pivot_sport_result = pivot_sport_result.sort_values('TOTAL', ascending=False)

print(pivot_sport_result.head(10))
print()

# ============================================================================
# SCHRITT 9: ZEITREIHEN-ANALYSE
# ============================================================================
print("📈 Schritt 9: Zeitreihen-Analyse...")
print("-" * 100)

# Setze Datum als Index
df_time = df.set_index('Publish_date').sort_index()

# Aggregiere nach Tag
daily_stats = df_time.resample('D').agg({
    'ROI': 'sum',                       # Täglicher ROI
    'Win_Binary': ['sum', 'count'],     # Gewinne und Anzahl Wetten pro Tag
    'Profit': 'sum'                     # Täglicher Profit
}).round(2)

# Vereinfache Spalten-Namen
daily_stats.columns = ['Daily_ROI', 'Daily_Wins', 'Daily_Bets', 'Daily_Profit']

# Berechne kumulative Werte
daily_stats['Cumulative_ROI'] = daily_stats['Daily_ROI'].cumsum()
daily_stats['Cumulative_Profit'] = daily_stats['Daily_Profit'].cumsum()

print("Tägliche Statistiken (erste 10 Tage):")
print(daily_stats.head(10))
print()

print("Tägliche Statistiken (letzte 10 Tage):")
print(daily_stats.tail(10))
print()

# ============================================================================
# SCHRITT 10: DATEN FILTERN UND QUERY
# ============================================================================
print("🔎 Schritt 10: Erweiterte Filter-Techniken...")
print("-" * 100)

# Filter 1: High-Value Bets
print("Filter 1: High-Value Bets (Quote 1.8-2.5, viele Follower)")
high_value = df[
    (df['Odd'] >= 1.8) & 
    (df['Odd'] <= 2.5) & 
    (df['#Followers'] > 50)
]
print(f"  └─ {len(high_value):,} High-Value Bets gefunden ({len(high_value)/len(df)*100:.1f}%)")
print(f"  └─ Win-Rate: {high_value['Win_Binary'].mean():.2%}")
print(f"  └─ Avg ROI: {high_value['ROI'].mean():.4f}")
print()

# Filter 2: Weekend Football Bets
print("Filter 2: Wochenend-Fußballwetten")
weekend_football = df[
    (df['Sport'] == 'Football') & 
    (df['Is_Weekend'] == True)
]
print(f"  └─ {len(weekend_football):,} Wochenend-Fußballwetten")
print(f"  └─ Win-Rate: {weekend_football['Win_Binary'].mean():.2%}")
print()

# Filter 3: Query-Syntax (Alternative zu Brackets)
print("Filter 3: Abendwetten (mit .query() Methode)")
evening_bets = df.query('Hour_Published >= 18 and Hour_Published <= 22')
print(f"  └─ {len(evening_bets):,} Abendwetten (18-22 Uhr)")
print(f"  └─ Win-Rate: {evening_bets['Win_Binary'].mean():.2%}")
print()

# ============================================================================
# SCHRITT 11: DATEN EXPORTIEREN
# ============================================================================
print("💾 Schritt 11: Bereinigte Daten speichern...")
print("-" * 100)

# Speichere bereinigte Daten
output_file = 'cleaned_betting_data.csv'
df.to_csv(output_file, index=False, sep=';')
print(f"✓ Bereinigte Daten gespeichert: {output_file}")
print(f"  └─ {len(df):,} Zeilen × {len(df.columns)} Spalten")
print()

# Speichere auch die Aggregations-Ergebnisse
sport_analysis.to_csv('analysis_by_sport.csv', sep=';')
user_performance.to_csv('top_performers.csv', sep=';')
print("✓ Analyse-Reports gespeichert:")
print("  └─ analysis_by_sport.csv")
print("  └─ top_performers.csv")
print()

# ============================================================================
# ZUSAMMENFASSUNG
# ============================================================================
print("=" * 100)
print("📋 ZUSAMMENFASSUNG - WAS WIR ERREICHT HABEN")
print("=" * 100)
print()

print("✓ DATENQUALITÄT:")
print(f"  └─ {deleted_rows:,} fehlerhafte Zeilen entfernt")
print(f"  └─ Alle Datentypen korrigiert (Zahlen, Datum, Kategorien)")
print()

print("✓ FEATURE ENGINEERING:")
print(f"  └─ {df.shape[1] - 26} neue Features erstellt")
print(f"  └─ Zeit-Features, Kategorien, berechnete KPIs")
print()

print("✓ BUSINESS INSIGHTS:")
print(f"  └─ Performance-Analyse nach {sport_analysis.shape[0]} Sportarten")
print(f"  └─ {user_performance.shape[0]:,} qualifizierte Top-Performer identifiziert")
print(f"  └─ Zeitreihen-Analyse über {len(daily_stats)} Tage")
print()

print("✓ BEST PERFORMER:")
best_sport = sport_analysis.index[0]
best_sport_winrate = sport_analysis.loc[best_sport, 'Win_Rate']
print(f"  └─ Beste Sportart: {best_sport} ({best_sport_winrate:.1%} Win-Rate)")

if len(user_performance) > 0:
    best_user = user_performance.index[0]
    best_user_profit = user_performance.loc[best_user, 'Total_Profit']
    print(f"  └─ Bester User: #{best_user} ({best_user_profit:,.2f} Profit)")
else:
    print(f"  └─ Keine User mit ausreichend Tipps (min. 50) gefunden")
print()

print("=" * 100)
print("✓ Pandas Data Cleaning & Transformation abgeschlossen!")
print("=" * 100)

"""
LERNZIELE ERREICHT:
-------------------
✓ Datentypen korrekt konvertiert
✓ Missing Values professionell behandelt
✓ Feature Engineering durchgeführt
✓ GroupBy und Aggregationen gemeistert
✓ Pivot-Tabellen erstellt
✓ Zeitreihen-Analysen durchgeführt
✓ Filter-Techniken angewendet
✓ Daten exportiert

NÄCHSTE SCHRITTE:
-----------------
→ Skript 3: Matplotlib für Visualisierungen
→ Skript 4: Seaborn für statistische Plots
"""
