"""
Spotify API Integration - Client Credentials Flow
Abrufen von öffentlichen Daten (Artist-Suche, Track-Info)
"""

import os
import requests
import json
import base64
from dotenv import load_dotenv

# .env-Datei laden
load_dotenv()

# Konstanten
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE_URL = "https://api.spotify.com/v1"


def get_access_token():
    """
    Authentifizierung via Client Credentials Flow.
    Liefert ein Access Token für den Zugriff auf öffentliche Spotify-Daten.
    
    Returns:
        str: Access Token oder None bei Fehler
    """
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    # Überprüfung auf fehlende Credentials
    if not client_id or not client_secret:
        raise ValueError(
            "❌ Fehler: SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET müssen in der .env-Datei gesetzt sein.\n"
            "Erstelle eine App auf: https://developer.spotify.com/dashboard"
        )
    
    # Base64-Kodierung für Basic Auth
    auth_string = f"{client_id}:{client_secret}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()
    
    # Request-Header
    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Request-Body
    data = {
        "grant_type": "client_credentials"
    }
    
    try:
        response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")
        
        print(f"✅ Access Token erfolgreich abgerufen (gültig für {expires_in} Sekunden)")
        return access_token
    
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP-Fehler bei Token-Anfrage: {http_err}")
        print(f"Response: {response.text}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"❌ Netzwerkfehler: {req_err}")
        return None
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        return None


def search_artist(access_token, artist_name, limit=5):
    """
    Sucht nach einem Artist auf Spotify.
    
    Args:
        access_token (str): Das Access Token
        artist_name (str): Name des Artists
        limit (int): Maximale Anzahl der Ergebnisse (default: 5)
    
    Returns:
        list: Liste von Artist-Objekten
    """
    if not access_token:
        print("❌ Kein gültiges Access Token vorhanden.")
        return []
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "q": artist_name,
        "type": "artist",
        "limit": limit
    }
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/search",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        artists = data.get("artists", {}).get("items", [])
        
        print(f"\n🔍 Gefundene Artists für '{artist_name}':")
        print("-" * 60)
        
        for idx, artist in enumerate(artists, 1):
            name = artist.get("name", "N/A")
            popularity = artist.get("popularity", "N/A")
            followers = artist.get("followers", {}).get("total", 0)
            genres = ", ".join(artist.get("genres", []))[:50] or "Keine Genres"
            spotify_url = artist.get("external_urls", {}).get("spotify", "N/A")
            
            print(f"{idx}. {name}")
            print(f"   Popularität: {popularity}/100")
            print(f"   Follower: {followers:,}")
            print(f"   Genres: {genres}")
            print(f"   URL: {spotify_url}")
            print()
        
        return artists
    
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP-Fehler: {http_err}")
        if response.status_code == 401:
            print("   → Token ist abgelaufen oder ungültig.")
        elif response.status_code == 429:
            print("   → Rate Limit erreicht. Bitte warten.")
        return []
    except requests.exceptions.RequestException as req_err:
        print(f"❌ Netzwerkfehler: {req_err}")
        return []
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        return []


def get_artist_details(access_token, artist_id):
    """
    Holt detaillierte Informationen zu einem Artist.
    
    Args:
        access_token (str): Das Access Token
        artist_id (str): Spotify Artist ID
    
    Returns:
        dict: Artist-Details
    """
    if not access_token:
        print("❌ Kein gültiges Access Token vorhanden.")
        return None
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/artists/{artist_id}",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        artist = response.json()
        
        print(f"\n🎵 Artist-Details:")
        print("=" * 60)
        print(f"Name: {artist.get('name')}")
        print(f"Popularität: {artist.get('popularity')}/100")
        print(f"Follower: {artist.get('followers', {}).get('total', 0):,}")
        print(f"Genres: {', '.join(artist.get('genres', []))}")
        print(f"Spotify URL: {artist.get('external_urls', {}).get('spotify')}")
        print("=" * 60)
        
        return artist
    
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP-Fehler: {http_err}")
        return None
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Artist-Details: {e}")
        return None


def get_artist_top_tracks(access_token, artist_id, market="DE"):
    """
    Holt die Top Tracks eines Artists.
    
    Args:
        access_token (str): Das Access Token
        artist_id (str): Spotify Artist ID
        market (str): ISO 3166-1 alpha-2 country code (default: DE)
    
    Returns:
        list: Liste von Track-Objekten
    """
    if not access_token:
        print("❌ Kein gültiges Access Token vorhanden.")
        return []
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "market": market
    }
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/artists/{artist_id}/top-tracks",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        tracks = data.get("tracks", [])
        
        print(f"\n🎵 Top Tracks:")
        print("-" * 60)
        
        for idx, track in enumerate(tracks[:10], 1):
            name = track.get("name")
            album = track.get("album", {}).get("name")
            popularity = track.get("popularity")
            duration_ms = track.get("duration_ms")
            duration_min = duration_ms // 60000
            duration_sec = (duration_ms % 60000) // 1000
            
            print(f"{idx}. {name}")
            print(f"   Album: {album}")
            print(f"   Popularität: {popularity}/100")
            print(f"   Dauer: {duration_min}:{duration_sec:02d}")
            print()
        
        return tracks
    
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP-Fehler: {http_err}")
        return []
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Top Tracks: {e}")
        return []


def save_to_json(data, filename="spotify_data.json"):
    """
    Speichert Daten als JSON-Datei.
    
    Args:
        data: Die zu speichernden Daten
        filename (str): Name der Ausgabedatei
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Daten erfolgreich gespeichert: {filename}")
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Datei: {e}")


def main():
    """
    Hauptfunktion - Beispiel-Workflow
    """
    print("=" * 60)
    print("🎵  SPOTIFY API - CLIENT CREDENTIALS FLOW  🎵")
    print("=" * 60)
    
    # Schritt 1: Access Token abrufen
    access_token = get_access_token()
    
    if not access_token:
        print("\n❌ Abbruch: Token konnte nicht abgerufen werden.")
        return
    
    # Schritt 2: Artist suchen
    artist_name = "Radiohead"  # Änderbar - per Input oder Variable
    artists = search_artist(access_token, artist_name, limit=5)
    
    if not artists:
        print("\n❌ Keine Artists gefunden.")
        return
    
    # Schritt 3: Details zum ersten Artist
    first_artist = artists[0]
    artist_id = first_artist.get("id")
    
    artist_details = get_artist_details(access_token, artist_id)
    
    # Schritt 4: Top Tracks des Artists
    top_tracks = get_artist_top_tracks(access_token, artist_id, market="DE")
    
    # Schritt 5: Ergebnisse als JSON speichern
    if artist_details and top_tracks:
        save_to_json({
            "artist": artist_details,
            "top_tracks": top_tracks
        }, filename="spotify_artist_data.json")
    
    print("\n✅ Fertig!")


if __name__ == "__main__":
    main()
