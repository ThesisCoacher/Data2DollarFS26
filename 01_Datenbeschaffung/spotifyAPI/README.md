# Spotify API Integration

Vollständige Python-Skripte zur Interaktion mit der Spotify Web API.

## Features

### 🔓 `spotify_api.py` - Client Credentials Flow (Öffentliche Daten)
- ✅ Artist-Suche
- ✅ Artist-Details abrufen
- ✅ Top Tracks eines Artists
- ✅ Keine User-Authentifizierung nötig
- ✅ Einfacher Einstieg

### 🔐 `spotify_api_user_auth.py` - Authorization Code Flow (User-Daten)
- ✅ **Deine persönlichen Top Tracks**
- ✅ **Deine persönlichen Top Artists**
- ✅ User-Profil abrufen
- ✅ Zeiträume: 4 Wochen, 6 Monate, gesamte Zeit
- ✅ Lokaler OAuth-Webserver für Callback

### Allgemein
- ✅ JSON-Export der Ergebnisse
- ✅ Robuste Fehlerbehandlung
- ✅ Rate Limit Handling
- ✅ Sichere Credential-Verwaltung via `.env`

## Verwendete API-Endpunkte

- **Token**: `POST https://accounts.spotify.com/api/token`
- **Search**: `GET https://api.spotify.com/v1/search`
- **Artist Details**: `GET https://api.spotify.com/v1/artists/{id}`
- **Top Tracks**: `GET https://api.spotify.com/v1/artists/{id}/top-tracks`

## Installation

1. **Repository klonen / Dateien herunterladen**

2. **Virtuelle Umgebung erstellen (empfohlen)**:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

3. **Dependencies installieren**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Spotify App erstellen**:
   - Gehe zu: https://developer.spotify.com/dashboard
   - Klicke auf "Create app"
   - App Name: `My Spotify API App`
   - **Redirect URI**: `http://localhost:8888/callback` ⚠️ **Wichtig für User-Auth!**
   - API: Web API auswählen
   - Notiere dir **Client ID** und **Client Secret**

5. **.env-Datei erstellen**:
   ```bash
   copy .env.example .env  # Windows
   cp .env.example .env    # Linux/Mac
   ```

6. **Credentials eintragen**:
   Öffne `.env` und füge deine Credentials ein:
   ```
   SPOTIFY_CLIENT_ID=abc123...
   SPOTIFY_CLIENT_SECRET=xyz789...
   ```

## Ausführen

### Variante 1: Öffentliche Daten (Client Credentials)
```bash
python spotify_api.py
```
Sucht nach einem Artist und zeigt dessen Top Tracks.

### Variante 2: Persönliche Daten (User Authorization)
```bash
python spotify_api_user_auth.py
```
Öffnet Browser für Spotify-Login und zeigt **deine** Top Tracks und Artists.

## Anpassung

### Artist ändern
In der `main()`-Funktion:
```python
artist_name = "Dein Artist"  # z.B. "The Beatles", "Taylor Swift"
```

### Markt ändern (für Top Tracks)
```python
top_tracks = get_artist_top_tracks(access_token, artist_id, market="US")
```
Verfügbare Märkte: DE, US, GB, FR, etc. (ISO 3166-1 alpha-2)

### Mehr Suchergebnisse
```python
artists = search_artist(access_token, artist_name, limit=10)
```

## Code-Beispiele für eigene Anpassungen

### Top Tracks für verschiedene Zeiträume
```python
# Letzte 4 Wochen
top_tracks_short = get_user_top_tracks(access_token, time_range="short_term", limit=20)

# Letzte 6 Monate (Standard)
top_tracks_medium = get_user_top_tracks(access_token, time_range="medium_term", limit=20)

# Gesamte Zeit
top_tracks_long = get_user_top_tracks(access_token, time_range="long_term", limit=20)
```

### Mehrere Artists durchsuchen
```python
artists_to_search = ["Radiohead", "The Beatles", "Pink Floyd"]

for artist_name in artists_to_search:
    artists = search_artist(access_token, artist_name, limit=3)
    # Verarbeitung...
```

### CSV-Export statt JSON
```python
import csv
Artist-Details und Top Tracks (öffentliche Daten)
- `spotify_user_data.json`: User-Profil, persönliche Top Tracks und Artists
- `.refresh_token`: Gespeicherter Refresh Token (automatisch erstellt bei User-Auth)
def save_tracks_to_csv(tracks, filename="tracks.csv"):
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Track", "Artist", "Album", "Popularität"])
        
        for track in tracks:
            writer.writerow([
                track["name"],
                ", ".join([a["name"] for a in track["artists"]]),
                track["album"]["name"],
                track["popularity"]
            ])
    print(f"CSV gespeichert: {filename}")
```

## Typische Fehler

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `401 Unauthorized` | Token ungültig oder abgelaufen | Token neu abrufen |
| `429 Too Many Requests` | Rate Limit erreicht | Warten (meist 30 Sek.) |
| `ValueError: Credentials fehlen` | `.env` nicht korrekt | Client ID/Secret prüfen |
| `Connection Error` | Netzwerkproblem | Internetverbindung prüfen |

## Rate Limits

**Client Credentials Flow**:
- Keine offiziellen Limits dokumentiert
- Empfehlung: Max. 10 Requests/Sekunde
- Bei 429-Fehler: Retry mit exponential backoff

## Ausgabedateien

- `spotify_artist_data.json`: Enthält Artist-Details und Top Tracks

## Weitere Ressourcen

- [Spotify API Dokumentation](https://developer.spotify.com/documentation/web-api)
- [API Reference](https://developer.spotify.com/documentation/web-api/reference)
- [Authorization Guide](https://developer.spotify.com/documentation/web-api/concepts/authorization)
