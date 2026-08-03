# 🎵 spotman — TUI manager de Spotify

Gestor de Spotify desde la terminal con interfaz TUI (Textual + rich). Permite
gestionar playlists de forma masiva: editar (eliminar canciones), mover
canciones entre playlists, crear, limpiar, fusionar/dividir, ordenar,
importar/exportar y ver tops.

**TUI:** Textual + rich · **API:** Spotify Web API · **Auth:** PKCE (sin client secret)

---

## 📦 Instalación

### Desde PyPI / pip (recomendado)

```bash
pip install spotman
spotman
```

### Desde el repo (git)

```bash
git clone https://github.com/jorgeTTPD/spotman.git
cd spotman
python3 -m venv .venv && source .venv/bin/activate
pip install .
spotman
```

### Arch Linux (AUR)

```bash
yay -S spotman
```

### Sin instalar (modo desarrollo)

```bash
python3 main.py
```

---

---

## ✨ Funcionalidades

### 1. Editar Playlist
- Elige una playlist y navega sus canciones.
- **Selección múltiple** (espacio marca, `a` todo, `d` nada, `i` invertir).
- **Elimina las canciones seleccionadas** (con confirmación).
- **Deshacer con `z`** (restaura las canciones borradas).

### 2. Mover canciones a otra playlist
- Elige la playlist **origen** y selecciona canciones (espacio/`a`/`d`/`i`).
- Elige la playlist **destino** → confirma → las añade al destino y las quita del origen.
- **Deshacer con `z`** (devuelve las canciones al origen).

### 3. Crear playlist
- Crea una playlist **en blanco** (privada) escribiendo su nombre.

### 4. CSV/TXT → Playlist (importar)
- Importa archivos CSV (export de Spotify) y TXT (`Artista - Canción` o URIs `spotify:track:`).
- Resuelve URIs con búsqueda (con caché `track_uris.json`), reporta las no encontradas.
- Crea la playlist con el nombre que elijas.

### 5. Limpiar playlist (avanzado)
| Tipo | Qué hace |
|---|---|
| **Duplicados** | Detecta repetidas por URI y conserva la 1ª aparición |
| **No disponibles** | Elimina locales (`is_local`) y no reproducibles (`is_playable: false`) |
| **Podcasts** | Elimina episodios (`type: episode` o URI `spotify:episode:`) |
| **Por artista** | Lista los artistas → eliges uno → elimina todas sus canciones |
| **Por álbum** | Igual pero con álbumes |

- Confirmación siempre antes de borrar · **Deshacer con `z`** (pila de 20).

### 6. Fusionar / Dividir playlists
| Operación | Qué hace |
|---|---|
| **Fusionar playlists** | Seleccionas varias → crea una nueva con todas las canciones |
| **Fusionar sin duplicados** | Igual, deduplicando por URI (conserva la 1ª) |
| **Dividir por artista** | Agrupa por artista → crea una playlist por cada uno |
| **Dividir por álbum** | Igual, agrupando por álbum |

- Si las fuentes están vacías no crea nada · Si `add_tracks` falla, borra la playlist recién creada · **Deshacer con `z`**.

### 7. Ordenar playlist
- Criterio: Título / Artista / Álbum / Duración + orden asc/desc.
- Reordena vía remove-all + re-add, con confirmación del riesgo.

### 8. Playlist → CSV/TXT (exportar)
- Exporta una playlist a CSV (formato re-importable de Spotify) o TXT en `data/csv`.

### 9. Top artistas / canciones (Spotify)
- Top de Spotify en 3 rangos: 4 semanas / 6 meses / todo el tiempo.
- Botón para crear una playlist con ese top.

### 10. Reautenticar
- Sale de la TUI con resultado `reauth` → vuelve a ejecutar el login (para renovar scopes).

### 11. Cerrar

---

## 🔑 Autenticación

- Flujo **PKCE** (sin `client_secret`) con `client_id` de `spotify_player`.
- **Automático:** abre el navegador → Spotify redirige a `http://127.0.0.1:8888/callback`
  (servidor local que captura el code solo, sin pegar nada).
  ⚠️ El redirect URI debe estar registrado EXACTAMENTE en tu dashboard de Spotify
  (developer.spotify.com → tu app → Settings → Redirect URIs).
- **Scopes:** `playlist-read-private`, `playlist-modify-public`,
  `playlist-modify-private`, `user-top-read`.
- El token se guarda en `~/.config/spotifymanager/token.json` y se refresca solo.
- **Fallback:** si el token propio falla, usa el token de `spotify_player`/`ncspot`
  (`~/.cache/spotify-player/user_client_token.json`) como respaldo.
- **Flujo manual (respaldo):** muestra la URL de autorización y pegas el `code`
  de Google (`https://www.google.com/?code=...`).
- Si una operación de escritura falla con 403, la app avisa "re-autentícate (nuevos permisos requeridos)".

## 🗂️ Estructura

```
main.py                    ← Entry point
src/
  config.py                ← Credenciales y rutas (~/.config/spotifymanager)
  spotify_client.py        ← API calls, auth PKCE, servidor local, fallback token
  csv_handler.py           ← Lee/escribe CSV y TXT
  tui/
    app.py                 ← SpotifyManagerApp (navegación, transparencia al arrancar)
    console.py             ← Console de Rich (logs silenciables)
    auth.py                ← Menú de autenticación por consola (automático/manual)
    setup.py               ← Configuración inicial (pedir Client ID)
    transparent.py         ← Parches de transparencia/glass (fondo de la terminal)
    widgets.py             ← Helpers de borde/estilo + modales reutilizables
    screens/
      main_screen.py       ← Menú principal (11 opciones)
      edit_screen.py       ← Editar playlist (seleccionar + eliminar)
      move_screen.py       ← Mover canciones a otra playlist
      create_screen.py     ← Crear playlist en blanco
      import_screen.py     ← CSV/TXT → Playlist
      cleanup_screen.py    ← Limpieza avanzada (5 tipos)
      merge_screen.py      ← Fusionar / Dividir
      sort_screen.py       ← Ordenar playlist
      export_screen.py     ← Playlist → CSV/TXT
      top_screen.py        ← Top artistas/canciones
data/csv/                  ← CSVs/TXTs del usuario
requirements.txt           ← rich, textual, requests, python-dotenv
```

**Estilo:** todos los menús/listas/diálogos van encerrados en rectángulos con
borde y título. El fondo es el predeterminado de la terminal del sistema
(no se define un fondo oscuro propio).

## 🚀 Primer uso

Al arrancar por primera vez te pedirá tu **Client ID** de Spotify
([developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)) y
abrirá el navegador para autorizar. Configura en tu app estas **Redirect URIs**:

```
http://127.0.0.1:8888/callback
https://www.google.com/
```

## ✅ Verificación

- Compile: `python3 -m py_compile main.py src/*.py src/tui/*.py src/tui/screens/*.py`
- Los tests actuales son scripts por fase (`TEST_*_OK` en `/tmp`) con un cliente
  falso que cubren las pantallas (cleanup, merge, edit/move/create).
  Pendiente: unificar una suite en `tests/` (ver bitácora).
