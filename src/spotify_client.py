import base64
import hashlib
import http.server
import json
import os
import queue
import secrets
import socketserver
import threading
import time
import webbrowser
from urllib.parse import parse_qs, quote, urlparse

import requests

from . import config
from .tui.console import console


def _generate_code_verifier():
    return secrets.token_urlsafe(64)[:128]


def _pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class _AuthHandler(http.server.BaseHTTPRequestHandler):
    """Captura el code que Spotify redirige a http://127.0.0.1:8989/login."""

    queue = queue.Queue()

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        code = params.get("code", [None])[0]
        if code:
            # Primero respondemos al navegador, luego encolamos el code
            # (evita que el shutdown del server corte la respuesta).
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                (
                    "<html><head><meta charset='utf-8'></head>"
                    "<body style='font-family:sans-serif;background:#191414;color:#1db954;"
                    "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
                    "<h1>✓ Autenticación exitosa. Ya puedes cerrar esta pestaña.</h1>"
                    "</body></html>"
                ).encode()
            )
            self.wfile.flush()
            _AuthHandler.queue.put(code)
        else:
            error = params.get("error", ["desconocido"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h1>Error: {error}</h1>".encode())
            self.wfile.flush()
            _AuthHandler.queue.put(f"__error__:{error}")

    def log_message(self, *args):
        pass


class _AuthServer(socketserver.ThreadingTCPServer):
    """Servidor local reutilizable (permite rearrancar tras TIME_WAIT)."""

    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False


class SpotifyClient:
    def __init__(self):
        self._token = None
        self._fallback_token = None
        self._token_file = config.TOKEN_FILE
        self._code_verifier = None
        self.silent = False  # True durante la TUI: no imprimir a stdout

    def _log(self, message):
        if not self.silent:
            console.print(message)

    def _auth_header(self, token):
        return {"Authorization": f"Bearer {token}"}

    def _api_call(self, method, url, data=None, retries=5, _retried_auth=False):
        token = self._token
        if not token:
            return None
        headers = self._auth_header(token)
        if data is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(retries):
            try:
                timeout = 15
                if method == "GET":
                    r = requests.get(url, headers=headers, timeout=timeout)
                elif method == "POST":
                    r = requests.post(
                        url, headers=headers, data=json.dumps(data), timeout=timeout
                    )
                elif method == "DELETE":
                    r = requests.delete(url, headers=headers, timeout=timeout)
                elif method == "PUT":
                    r = requests.put(
                        url,
                        headers=headers,
                        data=json.dumps(data) if data else None,
                        timeout=timeout,
                    )
                else:
                    return None
                if r.status_code == 429:
                    wait = min(int(r.headers.get("Retry-After", 5)), 10)
                    self._log(
                        f"[yellow]⏳ Rate limit, esperando {wait}s...[/yellow]"
                    )
                    time.sleep(wait)
                    continue
                if r.status_code == 401 and not _retried_auth:
                    new_token = self.refresh_token()
                    if new_token:
                        self._token = new_token
                        return self._api_call(
                            method, url, data, retries, _retried_auth=True
                        )
                    self._token = None
                    return None
                if (
                    r.status_code == 403
                    and self._fallback_token
                    and token != self._fallback_token
                ):
                    self._log(
                        "[yellow]⚠️  Token sin permisos, usando fallback (spotify_player)...[/yellow]"
                    )
                    self._token = self._fallback_token
                    return self._api_call(
                        method, url, data, retries, _retried_auth=True
                    )
                return r
            except requests.exceptions.Timeout:
                self._log(
                    f"[yellow]⏱ Timeout ({timeout}s), reintento {attempt + 1}/{retries}[/yellow]"
                )
                time.sleep(2**attempt)
            except requests.RequestException:
                time.sleep(2**attempt)
        return None

    def _load_token(self):
        if os.path.exists(self._token_file):
            with open(self._token_file) as f:
                info = json.load(f)
            return info.get("access_token")
        return None

    def _load_fallback_token(self):
        paths = [
            os.path.expanduser("~/.cache/spotify-player/user_client_token.json"),
            os.path.expanduser("~/.cache/ncspot/rspotify_token.json"),
        ]
        for path in paths:
            if os.path.exists(path):
                with open(path) as f:
                    info = json.load(f)
                token = info.get("access_token")
                if token:
                    return token
        return None

    def _save_token(self, access_token, refresh_token=None, expires_in=3600):
        info = {"access_token": access_token, "expires_in": expires_in}
        if refresh_token:
            info["refresh_token"] = refresh_token
        else:
            if os.path.exists(self._token_file):
                with open(self._token_file) as f:
                    old = json.load(f)
                info["refresh_token"] = old.get("refresh_token")
        with open(self._token_file, "w") as f:
            json.dump(info, f)

    def refresh_token(self):
        if not os.path.exists(self._token_file):
            return None
        with open(self._token_file) as f:
            info = json.load(f)
        rt = info.get("refresh_token")
        if not rt:
            return None
        data = {
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": config.CLIENT_ID,
        }
        r = requests.post(config.SPOTIFY_AUTH, data=data)
        if r.status_code == 200:
            d = r.json()
            self._save_token(
                d["access_token"], d.get("refresh_token"), d.get("expires_in", 3600)
            )
            self._token = d["access_token"]
            return d["access_token"]
        return None

    def exchange_code(self, code, redirect_uri=None):
        if not self._code_verifier:
            console.print(
                "[red]Error: no hay code_verifier (reintenta la autenticación)[/red]"
            )
            return False

        r = requests.post(
            config.SPOTIFY_AUTH,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri or config.REDIRECT_URI,
                "client_id": config.CLIENT_ID,
                "code_verifier": self._code_verifier,
            },
        )

        if r.status_code == 200:
            d = r.json()
            granted = d.get("scope", "")
            console.print(f"\n  Scopes otorgados por Spotify: [bold]{granted}[/bold]")
            expected = {"playlist-read-private"}
            if not expected.intersection(granted.split()):
                console.print("  [red]⚠️  No se otorgaron los scopes necesarios.[/red]")
                console.print(
                    "  [yellow]En el navegador, asegúrate de marcar TODOS los checkboxes.[/yellow]"
                )
            self._save_token(
                d["access_token"], d.get("refresh_token"), d.get("expires_in", 3600)
            )
            self._token = d["access_token"]
            self._code_verifier = None
            return True
        console.print(
            f"  [red]Error al intercambiar código: {r.status_code} {r.text[:200]}[/red]"
        )
        return False

    def get_auth_url(self, redirect_uri=None):
        self._code_verifier = _generate_code_verifier()
        challenge = _pkce_challenge(self._code_verifier)
        scopes = (
            "playlist-read-private "
            "playlist-modify-public playlist-modify-private user-top-read"
        )
        params = {
            "client_id": config.CLIENT_ID,
            "response_type": "code",
            "redirect_uri": redirect_uri or config.REDIRECT_URI,
            "scope": scopes,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        return "https://accounts.spotify.com/authorize?" + "&".join(
            f"{k}={quote(v, safe='')}" for k, v in params.items()
        )

    def auth_via_browser(self):
        """Flujo automático: abre el navegador y captura el code solo.

        Spotify redirige al redirect_uri registrado (servidor local),
        que captura el code automáticamente. Sin pegar nada en la terminal.
        """
        redirect_uri = config.REDIRECT_URI

        # El servidor local escucha en el host/puerto del redirect_uri registrado
        parsed = urlparse(redirect_uri)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8989

        try:
            server = _AuthServer((host, port), _AuthHandler)
        except OSError as e:
            console.print(f"[red]Error: puerto {port} en uso ({e}).[/red]")
            console.print("[red]Cierra el proceso que lo ocupe y reintenta.[/red]")
            return None

        _AuthHandler.queue = queue.Queue()
        threading.Thread(target=server.serve_forever, daemon=True).start()

        try:
            url = self.get_auth_url(redirect_uri=redirect_uri)

            console.print()
            console.print(
                "[bold yellow]🔑 Abriendo navegador para autenticación...[/bold yellow]"
            )
            console.print(
                "[dim]Autoriza la app en Spotify (Agree). La captura es automática.[/dim]"
            )
            console.print(
                f"[dim]Redirect URI activo: {redirect_uri}[/dim]"
            )
            console.print(
                f"[dim]Client ID activo: {config.CLIENT_ID}[/dim]"
            )
            console.print(
                "[dim]Si Spotify dice 'redirect_uri: Not matching configuration', "
                "registra ESTA URI exacta en el dashboard de Spotify "
                f"(developer.spotify.com → la app con client_id {config.CLIENT_ID} "
                "→ Settings → Redirect URIs).[/dim]"
            )
            console.print()
            webbrowser.open(url)
            console.print("[dim]Si no se abrió el navegador, abre esta URL:[/dim]")
            console.print(f"  [link={url}]{url}[/link]")
            console.print()

            if parsed.path not in ("", "/"):
                console.print(
                    f"[dim]El servidor local está escuchando en "
                    f"http://{host}:{port}{parsed.path} (debe coincidir con el "
                    f"redirect_uri registrado).[/dim]"
                )

            try:
                result = _AuthHandler.queue.get(timeout=300)
            except queue.Empty:
                console.print(
                    "[red]⏱ Timeout (5 min) esperando la autorización de Spotify.[/red]"
                )
                return None

            if isinstance(result, str) and result.startswith("__error__:"):
                console.print(
                    f"[red]Spotify rechazó la autorización: {result.split(':', 1)[1]}[/red]"
                )
                return None

            console.print(
                "[green]✓ Código capturado automáticamente, intercambiando por token...[/green]"
            )

            if not self.exchange_code(result, redirect_uri=redirect_uri):
                console.print("[red]Error al intercambiar el código.[/red]")
                return None

            user = self.get_user()
            if not user:
                console.print(
                    "[red]Error al obtener usuario después de autenticar.[/red]"
                )
                return None

            name = user.get("display_name", user["id"])
            console.print(f"\n[green]✓ Autenticado como: {name}[/green]")
            return user
        finally:
            server.shutdown()
            server.server_close()

    def authenticate(self):
        self._token = self._load_token()
        self._fallback_token = self._load_fallback_token()
        if self._token:
            r = self._api_call("GET", f"{config.SPOTIFY_API}/me")
            if r and r.status_code == 200:
                return r.json()
            self.refresh_token()
            if self._token:
                r = self._api_call("GET", f"{config.SPOTIFY_API}/me")
                if r and r.status_code == 200:
                    return r.json()
        if self._fallback_token:
            self._token = self._fallback_token
            r = self._api_call("GET", f"{config.SPOTIFY_API}/me")
            if r and r.status_code == 200:
                console.print(
                    "[green]✓ Usando token de spotify_player (fallback)[/green]"
                )
                return r.json()
        return None

    def get_user(self):
        r = self._api_call("GET", f"{config.SPOTIFY_API}/me")
        if r and r.status_code == 200:
            return r.json()
        return None

    def get_user_id(self):
        user = self.get_user()
        return user["id"] if user else None

    def get_playlists(self, limit=50):
        playlists = []
        url = f"{config.SPOTIFY_API}/me/playlists?limit={limit}"
        while url:
            r = self._api_call("GET", url)
            if not r or r.status_code != 200:
                break
            data = r.json()
            playlists.extend(data.get("items", []))
            url = data.get("next")
        return playlists

    def _simplify_track(self, t):
        """Normaliza un objeto track/episode de la API a nuestro dict interno."""
        album_name = ""
        if t.get("album"):
            album_name = t["album"].get("name", "")
        artists_list = [a.get("name", "") for a in t.get("artists", [])]
        return {
            "name": t["name"],
            "artist": ", ".join(artists_list),
            "artists_list": artists_list,
            "album": album_name,
            "uri": t.get("uri", ""),
            "type": t.get("type", "track"),
            "is_local": bool(t.get("is_local")),
            "is_playable": t.get("is_playable", True),
            "duration_ms": t.get("duration_ms", 0),
        }

    def get_playlist_tracks(self, playlist_id):
        """Lee los tracks de una playlist.

        Spotify renombró el endpoint (2025): /playlists/{id}/tracks ahora
        devuelve 403 y el nuevo es /playlists/{id}/items, con la canción
        en el campo 'item' (antes 'track').
        """
        tracks = []
        url = f"{config.SPOTIFY_API}/playlists/{playlist_id}/items?limit=100"
        while url:
            r = self._api_call("GET", url)
            if not r or r.status_code != 200:
                break
            data = r.json()
            for item in data.get("items", []):
                t = item.get("item") or item.get("track")
                if t and t.get("name"):
                    track = self._simplify_track(t)
                    track["added_at"] = item.get("added_at", "")
                    tracks.append(track)
            url = data.get("next")
        return tracks

    # ------------------------------------------------------------------
    # v2: escritura, búsqueda y top
    # ------------------------------------------------------------------

    def _load_track_cache(self):
        path = os.path.join(config.CACHE_DIR, "track_uris.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_track_cache(self, cache):
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        path = os.path.join(config.CACHE_DIR, "track_uris.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f)

    def create_playlist(self, name, public=False):
        user_id = self.get_user_id()
        if not user_id:
            return None
        url = f"{config.SPOTIFY_API}/users/{user_id}/playlists"
        r = self._api_call(
            "POST",
            url,
            data={"name": name, "public": public, "description": ""},
        )
        if r and r.status_code in (200, 201):
            return r.json().get("id")
        return None

    def search_track(self, artist, name):
        cache = self._load_track_cache()
        key = f"{name.lower()}|{artist.lower()}"
        cached = cache.get(key)
        if cached:
            return cached

        uri = self._search_first(f"track:{name} artist:{artist}")
        if not uri:
            uri = self._search_first(f"track:{name}")
        if uri:
            cache[key] = uri
            self._save_track_cache(cache)
        return uri

    def _search_first(self, query):
        url = f"{config.SPOTIFY_API}/search?q={quote(query)}&type=track&limit=1"
        r = self._api_call("GET", url)
        if r and r.status_code == 200:
            items = r.json().get("tracks", {}).get("items", [])
            if items:
                return items[0].get("uri")
        return None

    def add_tracks(self, playlist_id, uris):
        for i in range(0, len(uris), 100):
            batch = uris[i : i + 100]
            r = self._api_call(
                "POST",
                f"{config.SPOTIFY_API}/playlists/{playlist_id}/items",
                data={"uris": batch},
            )
            if not r or r.status_code not in (200, 201):
                return False
        return True

    def remove_tracks(self, playlist_id, uris):
        for i in range(0, len(uris), 100):
            batch = uris[i : i + 100]
            r = self._api_call(
                "DELETE",
                f"{config.SPOTIFY_API}/playlists/{playlist_id}/items",
                data={"uris": batch},
            )
            if not r or r.status_code != 200:
                return False
        return True

    # ------------------------------------------------------------------
    # Gestión de playlists (renombrar, privacidad, eliminar, duplicar)
    # ------------------------------------------------------------------

    def rename_playlist(self, playlist_id, name):
        r = self._api_call(
            "PUT",
            f"{config.SPOTIFY_API}/playlists/{playlist_id}",
            data={"name": name},
        )
        return bool(r and r.status_code == 200)

    def set_playlist_visibility(self, playlist_id, public):
        r = self._api_call(
            "PUT",
            f"{config.SPOTIFY_API}/playlists/{playlist_id}",
            data={"public": bool(public)},
        )
        return bool(r and r.status_code == 200)

    def delete_playlist(self, playlist_id):
        r = self._api_call(
            "DELETE",
            f"{config.SPOTIFY_API}/playlists/{playlist_id}",
        )
        return bool(r and r.status_code == 200)

    def duplicate_playlist(self, source_id, new_name, public=False):
        """Crea una copia con las mismas canciones y visibilidad de la original."""
        tracks = self.get_playlist_tracks(source_id)
        uris = [t["uri"] for t in tracks if t.get("uri")]
        new_id = self.create_playlist(new_name, public=bool(public))
        if not new_id:
            return None
        if uris and not self.add_tracks(new_id, uris):
            # Limpiamos la copia vacía para no dejar basura en la cuenta
            self.delete_playlist(new_id)
            return None
        return new_id

    def get_top(self, kind, time_range, limit=20):
        items = []
        offset = 0
        page = min(50, limit)
        while len(items) < limit:
            url = (
                f"{config.SPOTIFY_API}/me/top/{kind}?time_range={time_range}"
                f"&limit={page}&offset={offset}"
            )
            r = self._api_call("GET", url)
            if not r or r.status_code != 200:
                break
            data = r.json()
            items.extend(data.get("items", []))
            if not data.get("next"):
                break
            offset += page
        return items[:limit]
