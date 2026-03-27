"""
=============================================================================
SKRIPT 1: NUMPY - DIE MATHEMATISCHE GRUNDLAGE
=============================================================================

USE CASE:
---------
Als Analyst eines Sportwetten-Startups möchten wir schnell und effizient
mathematische Berechnungen auf großen Datenmengen durchführen. NumPy ist
dafür die perfekte Bibliothek - sie ist bis zu 100x schneller als normales
Python bei numerischen Operationen.

ZIELE DIESES SKRIPTS:
----------------------
1. Wett-Quoten in NumPy-Arrays umwandeln
2. Profitable Wetten identifizieren (ROI-Berechnung)
3. Statistische Kennzahlen berechnen (Durchschnitt, Standardabweichung)
4. Value-Bets finden (wo unsere Quote besser ist als die "echte" Quote)
5. Performance-Metriken für Wett-Strategien berechnen

BUSINESS IMPACT:
----------------
Mit diesen Berechnungen können wir:
- Profitable Wett-Muster erkennen
- Risiko-Kennzahlen bestimmen
- Schnelle Entscheidungen auf Basis von 1 Million Datenpunkten treffen
"""

# Bibliotheken importieren
import numpy as np                    # NumPy für schnelle numerische Berechnungen
import pandas as pd                   # Pandas zum Einlesen der Daten
import warnings
warnings.filterwarnings('ignore')     # Unterdrücke Warnungen für saubere Ausgabe

print("=" * 80)
print("NUMPY ANALYSE: BETTING PERFORMANCE CALCULATOR")
print("=" * 80)
print()

# ============================================================================
# SCHRITT 1: DATEN EINLESEN UND VORBEREITEN
# ============================================================================
print("📊 Schritt 1: Daten einlesen...")
print("-" * 80)

# CSV-Datei einlesen (nutzen Pandas für den Import, dann konvertieren zu NumPy)
df = pd.read_csv('all_raw_data_100to2000.csv', sep=';')

# Wichtige Spalten in NumPy-Arrays umwandeln
# Arrays sind wie Excel-Spalten, aber viel schneller für Berechnungen
# Nutze pd.to_numeric mit errors='coerce' um fehlerhafte Werte zu NaN zu machen
df['Odd'] = pd.to_numeric(df['Odd'], errors='coerce')
df['Real_Odd'] = pd.to_numeric(df['Real_Odd'], errors='coerce')

# Entferne Zeilen mit fehlenden kritischen Werten
df = df.dropna(subset=['Odd', 'Real_Odd', 'Lable'])

odds = df['Odd'].values                            # Wett-Quoten (z.B. 1.83)
real_odds = df['Real_Odd'].values                  # "Echte" Markt-Quoten
results = df['Lable'].values                       # Ergebnis: "WIN" oder "LOST"
profits = df['Profit'].values                      # Profit pro User

print(f"✓ Anzahl Wetten: {len(odds):,}")
print(f"✓ Daten-Format: NumPy Arrays (optimiert für Berechnungen)")
print()

# ============================================================================
# SCHRITT 2: WIN-RATE BERECHNEN (ERFOLGSQUOTE)
# ============================================================================
print("📈 Schritt 2: Win-Rate berechnen...")
print("-" * 80)

# Erstelle ein Boolean-Array: True für Gewinne, False für Verluste
# Das ist wie eine IF-Spalte in Excel, aber für 1 Million Zeilen gleichzeitig!
wins = (results == 'WIN')  

# Berechne die Gewinn-Rate (Anzahl Gewinne / Anzahl gesamt)
# .mean() auf Boolean-Array gibt uns den Prozentsatz der True-Werte
win_rate = np.mean(wins)

# Berechne separate Win-Rates für unterschiedliche Quoten-Bereiche
# Hypothese: Niedrigere Quoten (Favoriten) gewinnen häufiger
low_odds_wins = np.mean(wins[odds < 1.5])      # Favoriten (Quote < 1.5)
mid_odds_wins = np.mean(wins[(odds >= 1.5) & (odds < 2.5)])  # Mittlere Quoten
high_odds_wins = np.mean(wins[odds >= 2.5])    # Außenseiter (Quote >= 2.5)

print(f"Gesamt Win-Rate: {win_rate:.2%}")
print(f"  └─ Favoriten (Quote < 1.5):     {low_odds_wins:.2%}")
print(f"  └─ Mittelfeld (Quote 1.5-2.5):  {mid_odds_wins:.2%}")
print(f"  └─ Außenseiter (Quote > 2.5):   {high_odds_wins:.2%}")
print()

# ============================================================================
# SCHRITT 3: ROI BERECHNEN (RETURN ON INVESTMENT)
# ============================================================================
print("💰 Schritt 3: ROI berechnen (Rendite)...")
print("-" * 80)

# ROI-Logik:
# - Bei Gewinn: Profit = (Quote - 1) × Einsatz  → Bei Quote 2.0 = 100% Gewinn
# - Bei Verlust: Profit = -1 × Einsatz          → Wir verlieren den Einsatz

# np.where() ist wie IF-THEN-ELSE für Arrays
# Syntax: np.where(Bedingung, Wert_wenn_True, Wert_wenn_False)
roi_per_bet = np.where(wins, odds - 1, -1)

# Gesamtrendite berechnen
total_roi = np.sum(roi_per_bet)
average_roi = np.mean(roi_per_bet)

print(f"Total ROI über alle Wetten: {total_roi:,.2f} Einheiten")
print(f"Durchschnittlicher ROI pro Wette: {average_roi:.4f} Einheiten ({average_roi*100:.2f}%)")
print()

# Interpretation für Studierende:
if average_roi > 0:
    print("✓ POSITIVES SIGNAL: Im Durchschnitt sind die Wetten profitabel!")
else:
    print("⚠ NEGATIVES SIGNAL: Im Durchschnitt verlieren die Wetten Geld.")
print()

# ============================================================================
# SCHRITT 4: VALUE BETTING - PROFITABLE WETTEN FINDEN
# ============================================================================
print("🎯 Schritt 4: Value-Bets identifizieren...")
print("-" * 80)

# Value-Bet-Konzept:
# Wenn unsere Quote HÖHER ist als die echte Markt-Quote, haben wir einen "Edge"
# Beispiel: Wir bekommen Quote 2.0, aber echter Wert ist nur 1.8 → 11% Vorteil!

# Berechne den Vorteil (Edge) für jede Wette
edge = odds - real_odds

# Finde Value-Bets (mindestens 5% Vorteil)
value_threshold = 0.05  # 5% Mindest-Vorteil
value_bets = edge > value_threshold

# Statistiken für Value-Bets
num_value_bets = np.sum(value_bets)
pct_value_bets = np.mean(value_bets)
value_bet_winrate = np.mean(wins[value_bets])
average_edge = np.mean(edge[value_bets])

print(f"Anzahl Value-Bets (>5% Edge): {num_value_bets:,} ({pct_value_bets:.1%} aller Wetten)")
print(f"Win-Rate bei Value-Bets: {value_bet_winrate:.2%}")
print(f"Durchschnittlicher Edge: {average_edge:.4f} ({average_edge*100:.2f}%)")
print()

# Business-Empfehlung basierend auf Daten
if value_bet_winrate > win_rate:
    print("✓ STRATEGIE-EMPFEHLUNG: Value-Bets performen besser als Durchschnitt!")
    print(f"  Verbesserung: +{(value_bet_winrate - win_rate)*100:.2f} Prozentpunkte")
else:
    print("⚠ ACHTUNG: Value-Bets performen nicht besser als Durchschnitt.")
print()

# ============================================================================
# SCHRITT 5: RISIKO-ANALYSE MIT STANDARDABWEICHUNG
# ============================================================================
print("📊 Schritt 5: Risiko-Kennzahlen berechnen...")
print("-" * 80)

# Standardabweichung misst die "Schwankung" unserer Ergebnisse
# Hohe Schwankung = Hohes Risiko, Niedrige Schwankung = Stabiles Ergebnis

std_roi = np.std(roi_per_bet)           # Standardabweichung des ROI
sharpe_ratio = average_roi / std_roi    # Sharpe Ratio: Rendite pro Risiko-Einheit

print(f"Standardabweichung (Risiko): {std_roi:.4f}")
print(f"Sharpe Ratio (Rendite/Risiko): {sharpe_ratio:.4f}")
print()

# Interpretation
print("INTERPRETATION:")
if sharpe_ratio > 0.1:
    print("✓ Gutes Risiko-Rendite-Verhältnis")
elif sharpe_ratio > 0:
    print("○ Neutrales Risiko-Rendite-Verhältnis")
else:
    print("⚠ Schlechtes Risiko-Rendite-Verhältnis (Verluste bei hohem Risiko)")
print()

# ============================================================================
# SCHRITT 6: KUMULATIVE RENDITE (VERMÖGENSENTWICKLUNG)
# ============================================================================
print("📈 Schritt 6: Vermögensentwicklung simulieren...")
print("-" * 80)

# Simuliere, wie sich unser Kapital über Zeit entwickelt
# np.cumsum() = kumulative Summe (wie laufender Kontostand)

cumulative_profit = np.cumsum(roi_per_bet)

# Finde beste und schlechteste Phasen
max_profit = np.max(cumulative_profit)      # Höchster Punkt
min_profit = np.min(cumulative_profit)      # Tiefster Punkt (Drawdown)
max_drawdown = max_profit - min_profit      # Größter Kapital-Rückgang

print(f"Höchster Profit: {max_profit:,.2f} Einheiten")
print(f"Stärkster Drawdown: {max_drawdown:,.2f} Einheiten")
print(f"End-Profit: {cumulative_profit[-1]:,.2f} Einheiten")
print()

# Risiko-Warnung bei großem Drawdown
if max_drawdown > abs(cumulative_profit[-1]) * 2:
    print("⚠ ACHTUNG: Sehr hohe Schwankungen! Kapital-Management wichtig.")
print()

# ============================================================================
# SCHRITT 7: QUOTEN-STATISTIKEN
# ============================================================================
print("🎲 Schritt 7: Quoten-Analyse...")
print("-" * 80)

# Berechne verschiedene statistische Kennzahlen für die Quoten
mean_odds = np.mean(odds)           # Durchschnitt
median_odds = np.median(odds)       # Median (mittlerer Wert)
std_odds = np.std(odds)             # Standardabweichung
min_odds = np.min(odds)             # Minimum
max_odds = np.max(odds)             # Maximum

# Percentile: 25% der Wetten haben Quote <= P25, 75% <= P75
p25_odds = np.percentile(odds, 25)
p75_odds = np.percentile(odds, 75)

print(f"Durchschnitts-Quote: {mean_odds:.2f}")
print(f"Median-Quote: {median_odds:.2f}")
print(f"Standardabweichung: {std_odds:.2f}")
print(f"Spannweite: {min_odds:.2f} bis {max_odds:.2f}")
print(f"25%-75% Percentile: {p25_odds:.2f} - {p75_odds:.2f}")
print()

# ============================================================================
# SCHRITT 8: PERFORMANCE-VERGLEICH NACH QUOTEN-KATEGORIEN
# ============================================================================
print("🔍 Schritt 8: Performance nach Quoten-Kategorien...")
print("-" * 80)

# Definiere Quoten-Kategorien
categories = [
    ("Sehr niedrig (< 1.5)", odds < 1.5),
    ("Niedrig (1.5 - 2.0)", (odds >= 1.5) & (odds < 2.0)),
    ("Mittel (2.0 - 3.0)", (odds >= 2.0) & (odds < 3.0)),
    ("Hoch (3.0 - 5.0)", (odds >= 3.0) & (odds < 5.0)),
    ("Sehr hoch (>= 5.0)", odds >= 5.0)
]

print(f"{'Kategorie':<25} {'Anzahl':>10} {'Win-Rate':>12} {'Avg ROI':>12}")
print("-" * 80)

for category_name, mask in categories:
    count = np.sum(mask)
    if count > 0:
        cat_winrate = np.mean(wins[mask])
        cat_roi = np.mean(roi_per_bet[mask])
        print(f"{category_name:<25} {count:>10,} {cat_winrate:>11.1%} {cat_roi:>11.4f}")
    else:
        print(f"{category_name:<25} {count:>10,} {'N/A':>12} {'N/A':>12}")

print()

# ============================================================================
# ZUSAMMENFASSUNG UND KEY INSIGHTS
# ============================================================================
print("=" * 80)
print("📋 ZUSAMMENFASSUNG - KEY INSIGHTS")
print("=" * 80)
print()

print(f"1. ERFOLGSQUOTE:")
print(f"   └─ {win_rate:.1%} der Wetten wurden gewonnen")
print()

print(f"2. PROFITABILITÄT:")
if average_roi > 0:
    print(f"   └─ ✓ Durchschnittlich +{average_roi*100:.2f}% Rendite pro Wette")
else:
    print(f"   └─ ⚠ Durchschnittlich {average_roi*100:.2f}% Verlust pro Wette")
print()

print(f"3. VALUE-BETTING:")
print(f"   └─ {pct_value_bets:.1%} der Wetten haben einen signifikanten Edge")
print(f"   └─ Diese performen mit {value_bet_winrate:.1%} Win-Rate")
print()

print(f"4. RISIKO:")
print(f"   └─ Maximaler Drawdown: {max_drawdown:,.2f} Einheiten")
print(f"   └─ Sharpe Ratio: {sharpe_ratio:.3f}")
print()

print("=" * 80)
print("✓ NumPy-Analyse abgeschlossen!")
print("=" * 80)

"""
LERNZIELE ERREICHT:
-------------------
✓ NumPy Arrays erstellt und verwendet
✓ Vectorized Operations durchgeführt (100x schneller als Loops!)
✓ Boolean Masking für Filterung angewendet
✓ Statistische Funktionen genutzt (mean, std, percentile)
✓ Kumulative Berechnungen mit cumsum()
✓ Business-relevante KPIs berechnet

NÄCHSTE SCHRITTE:
-----------------
→ Skript 2: Pandas für Data Cleaning und Transformation
→ Skript 3: Matplotlib für Visualisierungen
→ Skript 4: Seaborn für statistische Plots
"""
