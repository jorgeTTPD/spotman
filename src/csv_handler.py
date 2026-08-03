import csv
import os


def read_csv(filepath):
    tracks = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Track Name", "").strip()
            artist = row.get("Artist Name(s)", "").strip()
            if name and artist:
                tracks.append({"name": name, "artist": artist.split(";")[0].strip()})
    return tracks


def read_txt(filepath):
    tracks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("spotify:track:"):
                continue
            parts = line.split(" - ", 1)
            if len(parts) == 2:
                artist, name = parts[0].strip(), parts[1].strip()
                if artist and name:
                    tracks.append({"name": name, "artist": artist})
    return tracks


def read_uris(filepath):
    uris = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            uri = line.strip()
            if uri.startswith("spotify:track:"):
                uris.append(uri)
    return uris


def read_tracks(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        return read_csv(filepath), "csv"
    elif ext == ".txt":
        tracks = read_txt(filepath)
        uris = read_uris(filepath)
        return tracks, "txt"
    return [], None


def sanitize_filename(name):
    """Reemplaza caracteres inválidos para nombres de archivo por `_`."""
    import re

    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _artist_field(track):
    """Artistas en formato export de Spotify (separados por `;`)."""
    return track.get("artist", "").replace(", ", "; ")


def write_csv(filepath, tracks):
    """Escribe tracks en CSV con cabeceras exactas del export de Spotify."""
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Track Name", "Artist Name(s)"])
        writer.writeheader()
        for t in tracks:
            writer.writerow(
                {"Track Name": t.get("name", ""), "Artist Name(s)": _artist_field(t)}
            )


def write_txt(filepath, tracks):
    """Escribe tracks en TXT con una línea `Artista - Canción` por track."""
    with open(filepath, "w", encoding="utf-8") as f:
        for t in tracks:
            f.write(f"{_artist_field(t)} - {t.get('name', '')}\n")
