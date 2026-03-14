"""
Spotify API Integration - Authorization Code Flow (mit User-Daten)
Abrufen von personalisierten Daten wie eigene Top Tracks, Playlists, etc.

WICHTIG: Dieses Skript benötigt einen lokalen Webserver für den OAuth-Callback.
"""

import os
import requests
import json
import base64
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

# .env-Datei laden
load_dotenv()

# Konstanten
TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTH_URL = "https://accounts.spotify.com/authorize"
API_BASE_URL = "https://api.spotify.com/v1"
REDIRECT_URI = "http://127.0.0.1:3000/callback"

# Globale Variable für Authorization Code
authorization_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    """
    HTTP-Handler für den OAuth-Callback.
    Empfängt den Authorization Code von Spotify.
    """
    
    def do_GET(self):
        global authorization_code
        
        # Parse URL und extrahiere Query-Parameter
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        if "code" in query_params:
            authorization_code = query_params["code"][0]
            
            # Erfolgsseite anzeigen
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <head><title>Spotify Auth</title></head>
                <body style="font-family: Arial; text-align: center; padding-top: 50px;">
                    <h1 style="color: #1DB954;">&#10004; Erfolgreich authentifiziert!</h1>
                    <p>Du kannst dieses Fenster jetzt schliessen.</p>
                    <p>Das Skript wird automatisch fortgesetzt...</p>
                </body>
                </html>
            """)
        elif "error" in query_params:
            error = query_params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"""
                <html>
                <body style="font-family: Arial; text-align: center; padding-top: 50px;">
                    <h1 style="color: red;">Fehler bei der Authentifizierung</h1>
                    <p>Fehler: {error}</p>
                </body>
                </html>
            """.encode())
    
    def log_message(self, format, *args):
        # Logging unterdrücken
        pass


def request_user_authorization():
    """
    Startet den Authorization Code Flow.
    Öffnet den Browser für User-Login und wartet auf Callback.
    
    Returns:
        str: Authorization Code
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    
    if not client_id:
        raise ValueError("❌ SPOTIFY_CLIENT_ID fehlt in der .env-Datei")
    
    # Scopes definieren (Berechtigungen)
    scopes = [
        "user-top-read",           # Top Tracks/Artists
        "user-read-recently-played", # Recently Played
        "user-library-read",       # Saved Tracks
        "playlist-read-private"    # Private Playlists
    ]
    
    # Authorization URL erstellen
    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(scopes),
        "show_dialog": False  # True = User muss jedes Mal zustimmen
    }
    
    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"
    
    print("=" * 60)
    print("🔐 AUTHORIZATION CODE FLOW")
    print("=" * 60)
    print("\n1. Browser wird geöffnet für Spotify-Login...")
    print("2. Bitte erlaube dem App Zugriff auf deine Daten")
    print("3. Du wirst zu 127.0.0.1:3000 weitergeleitet")
    print("\nWarte auf Authentifizierung...\n")
    
    # Browser öffnen
    webbrowser.open(auth_url)
    
    # Lokalen Server starten für Callback
    server = HTTPServer(("127.0.0.1", 3000), CallbackHandler)
    server.handle_request()  # Wartet auf genau eine Anfrage
    
    if authorization_code:
        print("✅ Authorization Code erhalten!")
        return authorization_code
    else:
        raise Exception("❌ Kein Authorization Code erhalten")


def exchange_code_for_token(auth_code):
    """
    Tauscht Authorization Code gegen Access Token.
    
    Args:
        auth_code (str): Der Authorization Code
    
    Returns:
        tuple: (access_token, refresh_token)
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise ValueError("❌ Client ID und Secret fehlen in .env")
    
    # Base64-Kodierung für Authorization Header
    auth_string = f"{client_id}:{client_secret}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI
    }
    
    try:
        response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        
        print(f"✅ Access Token erhalten (gültig für {expires_in} Sekunden)\n")
        
        # Refresh Token speichern (für spätere Verwendung)
        with open(".refresh_token", "w") as f:
            f.write(refresh_token)
        print("💾 Refresh Token gespeichert in .refresh_token\n")
        
        return access_token, refresh_token
    
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP-Fehler: {http_err}")
        print(f"Response: {response.text}")
        return None, None
    except Exception as e:
        print(f"❌ Fehler beim Token-Austausch: {e}")
        return None, None


def get_user_top_tracks(access_token, time_range="medium_term", limit=20):
    """
    Holt die Top Tracks des Users.
    
    Args:
        access_token (str): Access Token
        time_range (str): 'short_term' (~4 Wochen), 'medium_term' (~6 Monate), 'long_term' (~Jahre)
        limit (int): Anzahl der Tracks (max 50)
    
    Returns:
        list: Liste von Track-Objekten
    """
    if not access_token:
        print("❌ Kein gültiges Access Token.")
        return []
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "time_range": time_range,
        "limit": limit,
        "offset": 0
    }
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/me/top/tracks",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        tracks = data.get("items", [])
        
        time_range_display = {
            "short_term": "letzte 4 Wochen",
            "medium_term": "letzte 6 Monate",
            "long_term": "gesamte Zeit"
        }
        
        print(f"\n🎵 Deine Top {len(tracks)} Tracks ({time_range_display.get(time_range)}):")
        print("=" * 60)
        
        for idx, track in enumerate(tracks, 1):
            name = track.get("name")
            artists = ", ".join([artist["name"] for artist in track.get("artists", [])])
            album = track.get("album", {}).get("name")
            popularity = track.get("popularity")
            
            print(f"{idx}. {name}")
            print(f"   Artist(s): {artists}")
            print(f"   Album: {album}")
            print(f"   Popularität: {popularity}/100")
            print()
        
        return tracks
    
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP-Fehler: {http_err}")
        if response.status_code == 401:
            print("   → Token ist abgelaufen oder ungültig")
        elif response.status_code == 403:
            print("   → Fehlende Berechtigung (Scope: user-top-read)")
        return []
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return []


def get_user_top_artists(access_token, time_range="medium_term", limit=20):
    """
    Holt die Top Artists des Users.
    
    Args:
        access_token (str): Access Token
        time_range (str): 'short_term', 'medium_term', 'long_term'
        limit (int): Anzahl der Artists (max 50)
    
    Returns:
        list: Liste von Artist-Objekten
    """
    if not access_token:
        print("❌ Kein gültiges Access Token.")
        return []
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "time_range": time_range,
        "limit": limit
    }
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/me/top/artists",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        artists = data.get("items", [])
        
        time_range_display = {
            "short_term": "letzte 4 Wochen",
            "medium_term": "letzte 6 Monate",
            "long_term": "gesamte Zeit"
        }
        
        print(f"\n🎤 Deine Top {len(artists)} Artists ({time_range_display.get(time_range)}):")
        print("=" * 60)
        
        for idx, artist in enumerate(artists, 1):
            name = artist.get("name")
            genres = ", ".join(artist.get("genres", [])[:3]) or "Keine Genres"
            popularity = artist.get("popularity")
            followers = artist.get("followers", {}).get("total", 0)
            
            print(f"{idx}. {name}")
            print(f"   Genres: {genres}")
            print(f"   Popularität: {popularity}/100")
            print(f"   Follower: {followers:,}")
            print()
        
        return artists
    
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP-Fehler: {http_err}")
        return []
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return []


def get_current_user_profile(access_token):
    """
    Holt das User-Profil.
    
    Args:
        access_token (str): Access Token
    
    Returns:
        dict: User-Profil
    """
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/me",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        user = response.json()
        
        print("\n👤 Dein Spotify-Profil:")
        print("=" * 60)
        print(f"Name: {user.get('display_name', 'N/A')}")
        print(f"E-Mail: {user.get('email', 'N/A')}")
        print(f"Land: {user.get('country', 'N/A')}")
        print(f"Follower: {user.get('followers', {}).get('total', 0)}")
        print(f"Account-Typ: {user.get('product', 'N/A')}")
        print(f"Profil-URL: {user.get('external_urls', {}).get('spotify', 'N/A')}")
        print("=" * 60)
        
        return user
    
    except Exception as e:
        print(f"❌ Fehler beim Abrufen des Profils: {e}")
        return None


def save_to_json(data, filename="spotify_user_data.json"):
    """
    Speichert Daten als JSON.
    
    Args:
        data: Zu speichernde Daten
        filename (str): Dateiname
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Daten gespeichert: {filename}")
    except Exception as e:
        print(f"❌ Fehler beim Speichern: {e}")


def main():
    """
    Hauptfunktion - Authorization Code Flow
    """
    print("\n" + "=" * 60)
    print("🎵  SPOTIFY API - USER AUTHORIZATION FLOW  🎵")
    print("=" * 60)
    
    try:
        # Schritt 1: User Authorization
        auth_code = request_user_authorization()
        
        # Schritt 2: Token abrufen
        access_token, refresh_token = exchange_code_for_token(auth_code)
        
        if not access_token:
            print("❌ Abbruch: Token konnte nicht abgerufen werden.")
            return
        
        # Schritt 3: User-Profil abrufen
        user_profile = get_current_user_profile(access_token)
        
        # Schritt 4: Top Tracks abrufen (verschiedene Zeiträume)
        top_tracks_medium = get_user_top_tracks(
            access_token, 
            time_range="medium_term", 
            limit=20
        )
        
        # Schritt 5: Top Artists abrufen
        top_artists = get_user_top_artists(
            access_token,
            time_range="medium_term",
            limit=10
        )
        
        # Schritt 6: Als JSON speichern
        if user_profile and top_tracks_medium:
            save_to_json({
                "user_profile": user_profile,
                "top_tracks_medium_term": top_tracks_medium,
                "top_artists": top_artists
            }, filename="spotify_user_data.json")
        
        print("\n✅ Fertig! Alle Daten wurden erfolgreich abgerufen.\n")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Abgebrochen durch User.")
    except Exception as e:
        print(f"\n❌ Fehler: {e}")


if __name__ == "__main__":
    main()
