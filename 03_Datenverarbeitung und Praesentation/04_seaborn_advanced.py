"""
=============================================================================
SKRIPT 4: SEABORN - STATISTISCHE VISUALISIERUNGEN
=============================================================================

USE CASE:
---------
Seaborn ist die "professionelle" Version von Matplotlib. Es erstellt
automatisch schöne, statistische Visualisierungen mit weniger Code.
Perfekt für Datenanalysen, die statistische Insights zeigen sollen.

ZIELE DIESES SKRIPTS:
----------------------
1. Distribution Plots - Verteilungen mit statistischen Infos
2. Categorical Plots - Vergleiche zwischen Kategorien
3. Correlation Heatmap - Zusammenhänge auf einen Blick
4. Pair Plots - Multi-variable Beziehungen
5. FacetGrid - Mehrere Dimensionen gleichzeitig
6. Professionelle Styling-Optionen

BUSINESS IMPACT:
----------------
- Statistische Evidenz für Entscheidungen
- Professionelle Präsentationen für C-Level
- Schnelles Erkennen von Multi-variaten Mustern
- Publication-ready Grafiken
"""

# Bibliotheken importieren
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

# Seaborn Styling aktivieren
sns.set_theme(style="whitegrid")           # Moderner, sauberer Stil
sns.set_palette("husl")                     # Schöne Farbpalette
plt.rcParams['figure.figsize'] = (12, 6)

print("=" * 100)
print("SEABORN ADVANCED VISUALIZATIONS - STATISTICAL INSIGHTS")
print("=" * 100)
print()

# ============================================================================
# DATEN VORBEREITEN
# ============================================================================
print("📂 Lade und bereite Daten vor...")

df = pd.read_csv('all_raw_data_100to2000.csv', sep=';')

# Schnelle Datenbereinigung
df['Odd'] = pd.to_numeric(df['Odd'], errors='coerce')
df['Publish_date'] = pd.to_datetime(df['Publish_date'], format='%d/%m/%Y %H:%M', errors='coerce')
df['Win_Binary'] = (df['Lable'] == 'WIN').astype(int)
df['ROI'] = np.where(df['Win_Binary'] == 1, df['Odd'] - 1, -1)
df['Sport'].fillna('Unknown', inplace=True)
df['Hour_Published'] = df['Publish_date'].dt.hour
df['Day_of_Week'] = df['Publish_date'].dt.day_name()
df.dropna(subset=['Odd', 'Lable'], inplace=True)

# Weitere Features für Analyse
df['Odds_Category'] = pd.cut(df['Odd'], 
                              bins=[0, 1.5, 2.0, 3.0, 5.0, 100],
                              labels=['Sehr niedrig', 'Niedrig', 'Mittel', 'Hoch', 'Sehr hoch'])

print(f"✓ {len(df):,} Wetten bereit für Visualisierung")
print()

# ============================================================================
# VISUALISIERUNG 1: DISTRIBUTION PLOTS (KDE + HISTOGRAM)
# ============================================================================
print("📊 Visualisierung 1: Distribution Plots - Profit-Verteilungen")
print("-" * 100)

# Erstelle 2×2 Subplot Grid
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('PROFIT & ODDS DISTRIBUTIONS - Statistische Analyse', 
             fontsize=18, fontweight='bold', y=0.995)

# ============================================================================
# SUBPLOT 1: Histplot mit KDE für ROI
# ============================================================================
sns.histplot(data=df, x='ROI', hue='Lable', kde=True, 
             bins=50, alpha=0.6, ax=axes[0, 0])
axes[0, 0].set_title('ROI-Verteilung: Win vs. Lost (mit KDE)', 
                     fontsize=13, fontweight='bold')
axes[0, 0].set_xlabel('ROI pro Wette', fontweight='bold')
axes[0, 0].axvline(x=0, color='red', linestyle='--', linewidth=2)
axes[0, 0].set_xlim(-2, 5)

# ============================================================================
# SUBPLOT 2: Violin Plot für Profit nach Top-Sportarten
# ============================================================================
top_sports = df['Sport'].value_counts().head(3).index
df_top_sports = df[df['Sport'].isin(top_sports)]

sns.violinplot(data=df_top_sports, x='Sport', y='Profit', 
               hue='Lable', split=True, ax=axes[0, 1])
axes[0, 1].set_title('Profit-Verteilung nach Top-3 Sportarten', 
                     fontsize=13, fontweight='bold')
axes[0, 1].set_ylabel('Profit', fontweight='bold')
axes[0, 1].set_ylim(-100, 200)

# ============================================================================
# SUBPLOT 3: Box Plot für Quoten nach Ergebnis
# ============================================================================
sns.boxplot(data=df, x='Lable', y='Odd', palette='Set2', ax=axes[1, 0])
axes[1, 0].set_title('Quoten-Verteilung: Gewonnen vs. Verloren', 
                     fontsize=13, fontweight='bold')
axes[1, 0].set_ylabel('Quote', fontweight='bold')
axes[1, 0].set_xlabel('Ergebnis', fontweight='bold')
axes[1, 0].set_ylim(1, 6)

# ============================================================================
# SUBPLOT 4: Strip Plot für Followers (Sample)
# ============================================================================
# Sample nur 10,000 Punkte für bessere Performance
df_sample = df[df['Sport'].isin(top_sports)].sample(min(10000, len(df)))

sns.stripplot(data=df_sample, x='Sport', y='#Followers', 
              hue='Lable', alpha=0.3, ax=axes[1, 1])
axes[1, 1].set_title('Followers-Verteilung nach Sport', 
                     fontsize=13, fontweight='bold')
axes[1, 1].set_ylabel('Anzahl Followers (log scale)', fontweight='bold')
axes[1, 1].set_yscale('log')  # Logarithmische Skala für bessere Sichtbarkeit

plt.tight_layout()
plt.savefig('06_seaborn_distributions.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 06_seaborn_distributions.png")
plt.show()
print()

# ============================================================================
# VISUALISIERUNG 2: CORRELATION HEATMAP
# ============================================================================
print("🔥 Visualisierung 2: Correlation Heatmap - Welche Faktoren hängen zusammen?")
print("-" * 100)

# Wähle numerische Spalten für Korrelation
numeric_cols = ['Odd', 'Real_Odd', '#Followers', 'Profit', 
                'Account_Age_Tipp_published', 'Same_Country', 
                'Win_Binary', 'ROI', 'Hour_Published']

# Berechne Korrelationsmatrix
corr_matrix = df[numeric_cols].corr()

# Erstelle Heatmap
fig, ax = plt.subplots(figsize=(12, 10))

sns.heatmap(corr_matrix, 
            annot=True,              # Zeige Korrelations-Werte
            fmt='.2f',               # 2 Dezimalstellen
            cmap='coolwarm',         # Blau (negativ) bis Rot (positiv)
            center=0,                # 0 ist weiß (neutral)
            square=True,             # Quadratische Zellen
            linewidths=1,            # Trennlinien
            cbar_kws={'label': 'Korrelation'},
            vmin=-1, vmax=1,         # Farb-Skala von -1 bis +1
            ax=ax)

ax.set_title('KORRELATIONS-MATRIX: Welche KPIs beeinflussen sich?', 
             fontsize=16, fontweight='bold', pad=20)

# Drehe Y-Achsen-Labels für bessere Lesbarkeit
plt.yticks(rotation=0)

plt.tight_layout()
plt.savefig('07_correlation_heatmap.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 07_correlation_heatmap.png")
plt.show()

# Finde stärkste Korrelationen
print("\n💡 TOP KORRELATIONEN:")
# Erstelle Korrelations-Paare (ohne Diagonale und Duplikate)
corr_pairs = []
for i in range(len(corr_matrix.columns)):
    for j in range(i+1, len(corr_matrix.columns)):
        corr_pairs.append({
            'Var1': corr_matrix.columns[i],
            'Var2': corr_matrix.columns[j],
            'Correlation': corr_matrix.iloc[i, j]
        })

corr_df = pd.DataFrame(corr_pairs)
corr_df['Abs_Corr'] = corr_df['Correlation'].abs()
top_corr = corr_df.nlargest(5, 'Abs_Corr')

for idx, row in top_corr.iterrows():
    print(f"   {row['Var1']:30} ↔ {row['Var2']:30} : {row['Correlation']:6.3f}")
print()

# ============================================================================
# VISUALISIERUNG 3: COUNT PLOT - KATEGORISCHE ANALYSEN
# ============================================================================
print("📊 Visualisierung 3: Count Plots - Kategorische Verteilungen")
print("-" * 100)

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('KATEGORISCHE ANALYSEN - Wetten-Verteilungen', 
             fontsize=18, fontweight='bold')

# ============================================================================
# SUBPLOT 1: Wetten nach Top-Sportarten
# ============================================================================
top_10_sports = df['Sport'].value_counts().head(10).index
df_top_10 = df[df['Sport'].isin(top_10_sports)]

sns.countplot(data=df_top_10, y='Sport', hue='Lable', 
              order=top_10_sports, palette='Set2', ax=axes[0, 0])
axes[0, 0].set_title('Anzahl Wetten nach Top-10 Sportarten', 
                     fontsize=13, fontweight='bold')
axes[0, 0].set_xlabel('Anzahl Wetten', fontweight='bold')
axes[0, 0].set_ylabel('Sportart', fontweight='bold')

# ============================================================================
# SUBPLOT 2: Wetten nach Wochentag
# ============================================================================
weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                 'Friday', 'Saturday', 'Sunday']

sns.countplot(data=df, x='Day_of_Week', hue='Lable',
              order=weekday_order, palette='viridis', ax=axes[0, 1])
axes[0, 1].set_title('Wetten nach Wochentag', fontsize=13, fontweight='bold')
axes[0, 1].set_xlabel('Wochentag', fontweight='bold')
axes[0, 1].set_ylabel('Anzahl Wetten', fontweight='bold')
axes[0, 1].tick_params(axis='x', rotation=45)

# ============================================================================
# SUBPLOT 3: Verified Users Performance
# ============================================================================
sns.countplot(data=df, x='Verified', hue='Lable', 
              palette='coolwarm', ax=axes[1, 0])
axes[1, 0].set_title('Performance: Verifizierte vs. Nicht-Verifizierte User', 
                     fontsize=13, fontweight='bold')
axes[1, 0].set_xlabel('Verifiziert', fontweight='bold')
axes[1, 0].set_ylabel('Anzahl Wetten', fontweight='bold')

# ============================================================================
# SUBPLOT 4: Quoten-Kategorien
# ============================================================================
sns.countplot(data=df, x='Odds_Category', hue='Lable',
              palette='Spectral', ax=axes[1, 1])
axes[1, 1].set_title('Wetten nach Quoten-Kategorie', 
                     fontsize=13, fontweight='bold')
axes[1, 1].set_xlabel('Quoten-Kategorie', fontweight='bold')
axes[1, 1].set_ylabel('Anzahl Wetten', fontweight='bold')
axes[1, 1].tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.savefig('08_categorical_analysis.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 08_categorical_analysis.png")
plt.show()
print()

# ============================================================================
# VISUALISIERUNG 4: JOINT PLOT - BIVARIATE ANALYSE
# ============================================================================
print("🔍 Visualisierung 4: Joint Plot - Followers vs. Profit (inkl. Distributionen)")
print("-" * 100)

# Aggregiere User-Daten
user_stats = df.groupby('Username').agg({
    '#Followers': 'first',
    'Profit': 'sum',
    'Win_Binary': 'count'
}).reset_index()

user_stats.columns = ['Username', 'Followers', 'Total_Profit', 'Num_Bets']
user_stats = user_stats[user_stats['Num_Bets'] >= 30]

# Prüfe ob genug Daten vorhanden
if len(user_stats) > 10:
    # Erstelle Joint Plot (Scatter + Histogramme an den Rändern)
    g = sns.jointplot(data=user_stats, 
                      x='Followers', 
                      y='Total_Profit',
                      kind='scatter',        # Scatter statt hex für Robustheit
                      color='steelblue',
                      height=10,
                      alpha=0.5)

    g.fig.suptitle('BIVARIATE ANALYSE: Followers ↔ Profit\n(inkl. Rand-Verteilungen)', 
                   fontsize=16, fontweight='bold', y=1.02)

    # Korrelationslinie hinzufügen
    g.plot_joint(sns.regplot, scatter=False, color='red', line_kws={'linewidth': 2})
else:
    # Fallback: Einfacher Scatter Plot
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(user_stats['Followers'], user_stats['Total_Profit'], alpha=0.5)
    ax.set_xlabel('Followers')
    ax.set_ylabel('Total Profit')
    ax.set_title('Followers vs. Profit (wenige User mit 30+ Tipps)')
    g = plt.gcf()

plt.tight_layout()
plt.savefig('09_jointplot_followers_profit.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 09_jointplot_followers_profit.png")
plt.show()
print()

# ============================================================================
# VISUALISIERUNG 5: PAIR PLOT - MULTIVARIATE ANALYSE
# ============================================================================
print("🎯 Visualisierung 5: Pair Plot - Alle wichtigen KPIs auf einmal")
print("-" * 100)

# Sample für Performance (Pair Plot ist rechenintensiv)
df_sample = df.sample(min(2000, len(df)))

# Wähle wichtige numerische Variablen
pair_cols = ['Odd', 'Real_Odd', '#Followers', 'Profit', 'ROI']
df_pair = df_sample[pair_cols + ['Lable']].copy()

print("Erstelle Pair Plot (kann einige Sekunden dauern)...")

# Erstelle Pair Plot
g = sns.pairplot(df_pair, 
                 hue='Lable',              # Farbe nach Win/Lost
                 diag_kind='kde',          # KDE auf Diagonale
                 plot_kws={'alpha': 0.6},  # Transparenz
                 palette='Set1',
                 height=3)

g.fig.suptitle('MULTIVARIATE ANALYSE: Alle KPIs im Überblick', 
               fontsize=16, fontweight='bold', y=1.01)

plt.tight_layout()
plt.savefig('10_pairplot_multivariate.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 10_pairplot_multivariate.png")
plt.show()
print()

# ============================================================================
# VISUALISIERUNG 6: FACET GRID - MEHRDIMENSIONALE VERGLEICHE
# ============================================================================
print("🎨 Visualisierung 6: FacetGrid - Quoten-Analyse nach Sport und Ergebnis")
print("-" * 100)

# Fokus auf Top-3 Sportarten für Übersichtlichkeit
top_3_sports = df['Sport'].value_counts().head(3).index
df_facet = df[df['Sport'].isin(top_3_sports)].copy()

# Erstelle FacetGrid: Eine Spalte pro Sportart
g = sns.FacetGrid(df_facet, 
                  col='Sport',           # Spalten nach Sport
                  hue='Lable',           # Farbe nach Win/Lost
                  col_wrap=3,            # Max 3 Spalten
                  height=5,
                  aspect=1.2)

# Füge Histogramme hinzu
g.map(sns.histplot, 'Odd', kde=True, bins=30, alpha=0.6)

# Füge Legende hinzu
g.add_legend(title='Ergebnis')

# Haupttitel
g.fig.suptitle('FACET ANALYSE: Quoten-Verteilung nach Sport und Ergebnis', 
               fontsize=16, fontweight='bold', y=1.02)

plt.tight_layout()
plt.savefig('11_facetgrid_sport_odds.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 11_facetgrid_sport_odds.png")
plt.show()
print()

# ============================================================================
# VISUALISIERUNG 7: ADVANCED REGRESSION PLOT
# ============================================================================
print("📈 Visualisierung 7: Regression Plot - Profit Trend über Zeit")
print("-" * 100)

# Erstelle numerischen Zeitindex
df_time = df.sort_values('Publish_date').reset_index(drop=True)
df_time['Bet_Number'] = range(len(df_time))
df_time['Cumulative_ROI'] = df_time['ROI'].cumsum()

# Sample für bessere Performance
df_reg = df_time.sample(min(10000, len(df_time)))

# Erstelle Regression Plot
fig, ax = plt.subplots(figsize=(14, 7))

sns.regplot(data=df_reg, 
            x='Bet_Number', 
            y='Cumulative_ROI',
            scatter_kws={'alpha': 0.3, 's': 10},
            line_kws={'color': 'red', 'linewidth': 3},
            ax=ax)

ax.axhline(y=0, color='black', linestyle='--', linewidth=2, alpha=0.5)
ax.set_xlabel('Fortlaufende Wetten-Nummer', fontsize=13, fontweight='bold')
ax.set_ylabel('Kumulativer ROI', fontsize=13, fontweight='bold')
ax.set_title('TREND-ANALYSE: Ist die Betting-Strategie langfristig profitabel?', 
             fontsize=16, fontweight='bold', pad=20)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('12_regression_roi_trend.png', dpi=300, bbox_inches='tight')
print("✓ Gespeichert: 12_regression_roi_trend.png")
plt.show()
print()

# ============================================================================
# ZUSAMMENFASSUNG
# ============================================================================
print("=" * 100)
print("📋 ZUSAMMENFASSUNG - SEABORN VISUALISIERUNGEN")
print("=" * 100)
print()

print("✓ 7 fortgeschrittene statistische Visualisierungen erstellt:")
print()
print("  1️⃣ Distribution Plots (4-in-1):")
print("     └─ Histplot, Violin Plot, Box Plot, Strip Plot")
print()
print("  2️⃣ Correlation Heatmap:")
print("     └─ Alle numerischen Zusammenhänge auf einen Blick")
print()
print("  3️⃣ Categorical Analysis (4-in-1):")
print("     └─ Count Plots für Sport, Wochentag, Verified, Quoten")
print()
print("  4️⃣ Joint Plot:")
print("     └─ Bivariate Analyse mit Rand-Verteilungen")
print()
print("  5️⃣ Pair Plot:")
print("     └─ Multivariate Analyse aller KPIs")
print()
print("  6️⃣ FacetGrid:")
print("     └─ Mehrdimensionale Vergleiche nach Sport")
print()
print("  7️⃣ Regression Plot:")
print("     └─ Trend-Analyse mit Konfidenz-Intervall")
print()

print("📁 Gespeicherte Dateien:")
print("  └─ 06_seaborn_distributions.png")
print("  └─ 07_correlation_heatmap.png")
print("  └─ 08_categorical_analysis.png")
print("  └─ 09_jointplot_followers_profit.png")
print("  └─ 10_pairplot_multivariate.png")
print("  └─ 11_facetgrid_sport_odds.png")
print("  └─ 12_regression_roi_trend.png")
print()

print("=" * 100)
print("✓ ALLE 4 SKRIPTE ABGESCHLOSSEN - FROM DATA 2 DOLLAR!")
print("=" * 100)
print()

print("🎓 LERNREISE KOMPLETT:")
print("  ✓ NumPy    → Mathematische Grundlagen & Performance")
print("  ✓ Pandas   → Data Cleaning & Transformation")
print("  ✓ Matplotlib → Basis-Visualisierungen")
print("  ✓ Seaborn  → Statistische Analysen & Profi-Plots")
print()


"""
ALLE LERNZIELE ERREICHT! 🎉
===========================

NUMPY:
✓ Arrays, Vectorization, Statistiken

PANDAS:
✓ Data Cleaning, Grouping, Time-Series

MATPLOTLIB:
✓ Line, Bar, Scatter, Histograms, Subplots

SEABORN:
✓ Distributions, Correlations, Categories
✓ Multi-variate Plots, FacetGrids
✓ Publication-ready Visualizations

"""
