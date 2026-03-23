"""
=============================================================================
SKRIPT 3: MATPLOTLIB - DATENVISUALISIERUNG GRUNDLAGEN
=============================================================================

USE CASE:
---------
"Ein Bild sagt mehr als 1000 Zahlen!" Als Business Analyst müssen wir
unsere Erkenntnisse visualisieren, um sie verständlich zu kommunizieren.
Matplotlib ist die Grundlage aller Python-Visualisierungen.

ZIELE DIESES SKRIPTS:
----------------------
1. Line Charts - Trends über Zeit zeigen
2. Bar Charts - Kategorien vergleichen
3. Histogramme - Verteilungen verstehen
4. Scatter Plots - Zusammenhänge erkennen
5. Subplots - Mehrere Grafiken kombinieren
6. Styling - Professionelle Visualisierungen erstellen

BUSINESS IMPACT:
----------------
- Management-Präsentationen mit aussagekräftigen Charts
- Schnelles Erkennen von Mustern und Anomalien
- Überzeugende Argumentation mit visuellen Beweisen
- Professionelle Reports für Stakeholder
"""

# Bibliotheken importieren
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import warnings
warnings.filterwarnings('ignore')

# Matplotlib-Einstellungen für schönere Grafiken
plt.rcParams['figure.figsize'] = (12, 6)           # Standardgröße für Plots
plt.rcParams['font.size'] = 10                     # Schriftgröße
plt.rcParams['axes.grid'] = True                   # Immer Gitternetz zeigen
plt.rcParams['grid.alpha'] = 0.3                   # Gitternetz transparent
plt.style.use('seaborn-v0_8-darkgrid')            # Professioneller Stil

print("=" * 100)
print("MATPLOTLIB VISUALISIERUNG - FROM DATA TO DOLLAR")
print("=" * 100)
print()

# ============================================================================
# DATEN VORBEREITEN
# ============================================================================
print("📂 Lade bereinigte Daten...")

# Lade die Daten (aus Skript 2)
df = pd.read_csv('all_raw_data_100to2000.csv', sep=';')

# Schnelle Datenbereinigung
df['Odd'] = pd.to_numeric(df['Odd'], errors='coerce')
df['Publish_date'] = pd.to_datetime(df['Publish_date'], format='%d/%m/%Y %H:%M', errors='coerce')
df['Win_Binary'] = (df['Lable'] == 'WIN').astype(int)
df['ROI'] = np.where(df['Win_Binary'] == 1, df['Odd'] - 1, -1)
df['Sport'].fillna('Unknown', inplace=True)
df.dropna(subset=['Odd', 'Lable'], inplace=True)

print(f"✓ {len(df):,} Wetten geladen und bereinigt")
print()

# ============================================================================
# VISUALISIERUNG 1: LINE CHART - PROFIT ÜBER ZEIT
# ============================================================================
print("📈 Visualisierung 1: Line Chart - Kumulative Profit-Entwicklung")
print("-" * 100)

# Daten vorbereiten: Gruppiere nach Tag
df_sorted = df.sort_values('Publish_date')
df_time = df_sorted.set_index('Publish_date')
daily_roi = df_time.resample('D')['ROI'].sum()
cumulative_roi = daily_roi.cumsum()

# Plot erstellen
fig, ax = plt.subplots(figsize=(14, 6))

# Hauptlinie: Kumulativer ROI
ax.plot(cumulative_roi.index, cumulative_roi.values, 
        linewidth=2.5, color='#2E86AB', label='Kumulativer ROI')

# Horizontale Linie bei 0 (Break-Even)
ax.axhline(y=0, color='red', linestyle='--', linewidth=2, 
           alpha=0.7, label='Break-Even')

# Beschriftungen und Titel
ax.set_xlabel('Datum', fontsize=14, fontweight='bold')
ax.set_ylabel('Kumulativer ROI (Einheiten)', fontsize=14, fontweight='bold')
ax.set_title('Profit-Entwicklung über Zeit: Betting Performance Tracker', 
             fontsize=16, fontweight='bold', pad=20)

# Legende
ax.legend(fontsize=12, loc='upper left')

# X-Achse formatieren (Datum schön anzeigen)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.xticks(rotation=45)

# Gitter
ax.grid(True, alpha=0.3, linestyle='--')

# Layout optimieren
plt.tight_layout()

# Speichern
plt.savefig('01_profit_timeline.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 01_profit_timeline.png")
plt.show()
print()

# ============================================================================
# VISUALISIERUNG 2: BAR CHART - WIN-RATE NACH SPORTART
# ============================================================================
print("📊 Visualisierung 2: Bar Chart - Performance nach Sportart")
print("-" * 100)

# Daten vorbereiten: Win-Rate pro Sportart (nur Top 10)
sport_winrate = df.groupby('Sport').agg({
    'Win_Binary': ['mean', 'count']
}).round(3)

sport_winrate.columns = ['Win_Rate', 'Count']
sport_winrate = sport_winrate[sport_winrate['Count'] >= 1000]  # Min. 1000 Wetten
sport_winrate = sport_winrate.sort_values('Win_Rate', ascending=False).head(10)

# Plot erstellen
fig, ax = plt.subplots(figsize=(12, 7))

# Bar Chart mit Farben basierend auf Performance
colors = ['#06A77D' if x > 0.5 else '#D32F2F' for x in sport_winrate['Win_Rate']]
bars = ax.bar(range(len(sport_winrate)), 
              sport_winrate['Win_Rate'] * 100,  # Konvertiere zu Prozent
              color=colors, 
              alpha=0.8,
              edgecolor='black',
              linewidth=1.5)

# Break-Even Linie bei 50%
ax.axhline(y=50, color='black', linestyle='--', linewidth=2, 
           alpha=0.5, label='Break-Even (50%)')

# Beschriftungen
ax.set_ylabel('Win-Rate (%)', fontsize=14, fontweight='bold')
ax.set_xlabel('Sportart', fontsize=14, fontweight='bold')
ax.set_title('Top 10 Sportarten nach Win-Rate (min. 1,000 Wetten)', 
             fontsize=16, fontweight='bold', pad=20)

# X-Achse: Sport-Namen
ax.set_xticks(range(len(sport_winrate)))
ax.set_xticklabels(sport_winrate.index, rotation=45, ha='right')

# Werte über den Balken anzeigen
for i, bar in enumerate(bars):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
            f'{height:.1f}%',
            ha='center', va='bottom', fontweight='bold', fontsize=10)

# Legende
ax.legend(fontsize=11, loc='upper right')

# Y-Achse von 0 bis 60%
ax.set_ylim(0, 60)

plt.tight_layout()
plt.savefig('02_winrate_by_sport.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 02_winrate_by_sport.png")
plt.show()
print()

# ============================================================================
# VISUALISIERUNG 3: HISTOGRAM - QUOTEN-VERTEILUNG
# ============================================================================
print("📊 Visualisierung 3: Histogramm - Verteilung der Wett-Quoten")
print("-" * 100)

# Erstelle 2 Subplots nebeneinander
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# SUBPLOT 1: Gewonnene Wetten
wins_odds = df[df['Lable'] == 'WIN']['Odd']

ax1.hist(wins_odds, bins=50, color='#4CAF50', alpha=0.7, 
         edgecolor='black', linewidth=1.2)

# Durchschnittslinie
mean_win = wins_odds.mean()
ax1.axvline(mean_win, color='red', linestyle='--', linewidth=2.5,
            label=f'Durchschnitt: {mean_win:.2f}')

ax1.set_xlabel('Quote', fontsize=13, fontweight='bold')
ax1.set_ylabel('Anzahl Wetten', fontsize=13, fontweight='bold')
ax1.set_title('Quoten-Verteilung: GEWONNENE Wetten', 
              fontsize=14, fontweight='bold', color='#4CAF50')
ax1.legend(fontsize=11)
ax1.set_xlim(1, 10)  # Fokus auf relevante Quoten

# SUBPLOT 2: Verlorene Wetten
lost_odds = df[df['Lable'] == 'LOST']['Odd']

ax2.hist(lost_odds, bins=50, color='#F44336', alpha=0.7,
         edgecolor='black', linewidth=1.2)

# Durchschnittslinie
mean_lost = lost_odds.mean()
ax2.axvline(mean_lost, color='blue', linestyle='--', linewidth=2.5,
            label=f'Durchschnitt: {mean_lost:.2f}')

ax2.set_xlabel('Quote', fontsize=13, fontweight='bold')
ax2.set_ylabel('Anzahl Wetten', fontsize=13, fontweight='bold')
ax2.set_title('Quoten-Verteilung: VERLORENE Wetten', 
              fontsize=14, fontweight='bold', color='#F44336')
ax2.legend(fontsize=11)
ax2.set_xlim(1, 10)

# Haupttitel für beide Plots
fig.suptitle('Vergleich: Werden höhere oder niedrigere Quoten gewonnen?', 
             fontsize=16, fontweight='bold', y=1.02)

plt.tight_layout()
plt.savefig('03_odds_distribution.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 03_odds_distribution.png")
plt.show()

# Insight ausgeben
print(f"\n💡 INSIGHT:")
print(f"   Durchschnitts-Quote bei Gewinnen: {mean_win:.2f}")
print(f"   Durchschnitts-Quote bei Verlusten: {mean_lost:.2f}")
if mean_win < mean_lost:
    print(f"   → Niedrigere Quoten (Favoriten) gewinnen häufiger!")
else:
    print(f"   → Höhere Quoten gewinnen häufiger (ungewöhnlich!)")
print()

# ============================================================================
# VISUALISIERUNG 4: SCATTER PLOT - FOLLOWERS VS PROFIT
# ============================================================================
print("🔍 Visualisierung 4: Scatter Plot - Korrelation Followers vs. Profit")
print("-" * 100)

# Daten vorbereiten: Aggregiere pro User
user_stats = df.groupby('Username').agg({
    '#Followers': 'first',
    'Profit': 'sum',
    'Win_Binary': 'count'
}).reset_index()

user_stats.columns = ['Username', 'Followers', 'Total_Profit', 'Num_Bets']

# Filter: Nur User mit mindestens 30 Tipps
user_stats = user_stats[user_stats['Num_Bets'] >= 30]

# Plot erstellen
fig, ax = plt.subplots(figsize=(12, 8))

# Scatter Plot mit Farbcodierung nach Profit
scatter = ax.scatter(
    user_stats['Followers'],
    user_stats['Total_Profit'],
    c=user_stats['Total_Profit'],      # Farbe basiert auf Profit
    cmap='RdYlGn',                      # Rot-Gelb-Grün Farbskala
    alpha=0.6,
    s=50,                               # Punktgröße
    edgecolors='black',
    linewidth=0.5
)

# Null-Linie (Break-Even)
ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.5)

# Beschriftungen
ax.set_xlabel('Anzahl Followers', fontsize=14, fontweight='bold')
ax.set_ylabel('Total Profit (Einheiten)', fontsize=14, fontweight='bold')
ax.set_title('Korrelation: Haben erfolgreiche Tipper mehr Followers?', 
             fontsize=16, fontweight='bold', pad=20)

# Colorbar (Legende für Farbskala)
cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('Profit', fontsize=12, fontweight='bold')

# Gitter
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('04_followers_vs_profit.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 04_followers_vs_profit.png")
plt.show()

# Korrelation berechnen
correlation = user_stats['Followers'].corr(user_stats['Total_Profit'])
print(f"\n💡 INSIGHT:")
print(f"   Korrelation Followers ↔ Profit: {correlation:.3f}")
if abs(correlation) > 0.3:
    print(f"   → {'Positive' if correlation > 0 else 'Negative'} Korrelation erkennbar!")
else:
    print(f"   → Schwache Korrelation - Followers ≠ Garantie für Erfolg")
print()

# ============================================================================
# VISUALISIERUNG 5: MULTI-SUBPLOT DASHBOARD
# ============================================================================
print("📊 Visualisierung 5: Dashboard mit 4 Key-Metrics")
print("-" * 100)

# Erstelle 2×2 Grid von Subplots
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('BETTING PERFORMANCE DASHBOARD', 
             fontsize=20, fontweight='bold', y=0.995)

# ============================================================================
# SUBPLOT 1 (oben links): Wetten pro Wochentag
# ============================================================================
df['Day_of_Week'] = pd.to_datetime(df['Publish_date']).dt.day_name()
weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
weekday_counts = df['Day_of_Week'].value_counts().reindex(weekday_order)

axes[0, 0].bar(range(len(weekday_counts)), weekday_counts.values, 
               color='#3F51B5', alpha=0.8, edgecolor='black')
axes[0, 0].set_xticks(range(len(weekday_counts)))
axes[0, 0].set_xticklabels(['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'])
axes[0, 0].set_ylabel('Anzahl Wetten', fontweight='bold')
axes[0, 0].set_title('Wetten pro Wochentag', fontweight='bold', fontsize=13)
axes[0, 0].grid(axis='y', alpha=0.3)

# ============================================================================
# SUBPLOT 2 (oben rechts): Win-Rate nach Quoten-Kategorie
# ============================================================================
df['Odds_Cat'] = pd.cut(df['Odd'], bins=[0, 1.5, 2.0, 3.0, 5.0, 100],
                        labels=['<1.5', '1.5-2.0', '2.0-3.0', '3.0-5.0', '>5.0'])
odds_winrate = df.groupby('Odds_Cat')['Win_Binary'].mean() * 100

colors_wr = ['#4CAF50' if x > 50 else '#FF9800' for x in odds_winrate.values]
axes[0, 1].bar(range(len(odds_winrate)), odds_winrate.values, 
               color=colors_wr, alpha=0.8, edgecolor='black')
axes[0, 1].axhline(y=50, color='red', linestyle='--', linewidth=2, alpha=0.7)
axes[0, 1].set_xticks(range(len(odds_winrate)))
axes[0, 1].set_xticklabels(odds_winrate.index, rotation=45)
axes[0, 1].set_ylabel('Win-Rate (%)', fontweight='bold')
axes[0, 1].set_title('Win-Rate nach Quoten-Kategorie', fontweight='bold', fontsize=13)
axes[0, 1].grid(axis='y', alpha=0.3)

# ============================================================================
# SUBPLOT 3 (unten links): Top 10 Sportarten (Volumen)
# ============================================================================
top_sports = df['Sport'].value_counts().head(10)
axes[1, 0].barh(range(len(top_sports)), top_sports.values, 
                color='#FF5722', alpha=0.8, edgecolor='black')
axes[1, 0].set_yticks(range(len(top_sports)))
axes[1, 0].set_yticklabels(top_sports.index)
axes[1, 0].set_xlabel('Anzahl Wetten', fontweight='bold')
axes[1, 0].set_title('Top 10 Sportarten (Volumen)', fontweight='bold', fontsize=13)
axes[1, 0].grid(axis='x', alpha=0.3)
axes[1, 0].invert_yaxis()  # Höchster Wert oben

# ============================================================================
# SUBPLOT 4 (unten rechts): ROI Distribution (Boxplot-Style)
# ============================================================================
roi_positive = df[df['ROI'] > 0]['ROI']
roi_negative = df[df['ROI'] < 0]['ROI']

axes[1, 1].hist(df['ROI'], bins=50, color='#9C27B0', alpha=0.7, edgecolor='black')
axes[1, 1].axvline(x=0, color='red', linestyle='--', linewidth=2.5, label='Break-Even')
axes[1, 1].axvline(x=df['ROI'].mean(), color='yellow', linestyle='--', 
                   linewidth=2.5, label=f"Ø ROI: {df['ROI'].mean():.3f}")
axes[1, 1].set_xlabel('ROI pro Wette', fontweight='bold')
axes[1, 1].set_ylabel('Häufigkeit', fontweight='bold')
axes[1, 1].set_title('ROI-Verteilung aller Wetten', fontweight='bold', fontsize=13)
axes[1, 1].legend()
axes[1, 1].set_xlim(-2, 5)

# Layout optimieren
plt.tight_layout()
plt.savefig('05_dashboard.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 05_dashboard.png")
plt.show()
print()

# ============================================================================
# ZUSAMMENFASSUNG
# ============================================================================
print("=" * 100)
print("📋 ZUSAMMENFASSUNG - ERSTELLTE VISUALISIERUNGEN")
print("=" * 100)
print()

print("✓ 5 professionelle Visualisierungen erstellt:")
print("  1️⃣ Line Chart: Profit-Entwicklung über Zeit")
print("  2️⃣ Bar Chart: Win-Rate nach Sportart")
print("  3️⃣ Histogram: Quoten-Verteilung (Win vs. Lost)")
print("  4️⃣ Scatter Plot: Followers vs. Profit Korrelation")
print("  5️⃣ Dashboard: 4-in-1 Multi-Plot Overview")
print()

print("📁 Gespeicherte Dateien:")
print("  └─ 01_profit_timeline.png")
print("  └─ 02_winrate_by_sport.png")
print("  └─ 03_odds_distribution.png")
print("  └─ 04_followers_vs_profit.png")
print("  └─ 05_dashboard.png")
print()

print("=" * 100)
print("✓ Matplotlib Visualisierung abgeschlossen!")
print("=" * 100)

"""
LERNZIELE ERREICHT:
-------------------
✓ Line Charts für Zeitreihen
✓ Bar Charts für kategorische Daten
✓ Histogramme für Verteilungen
✓ Scatter Plots für Korrelationen
✓ Subplots und Layouts
✓ Professionelles Styling (Farben, Beschriftungen, Legenden)
✓ Speichern von hochauflösenden Grafiken

NÄCHSTE SCHRITTE:
-----------------
→ Skript 4: Seaborn für statistische Visualisierungen
"""
