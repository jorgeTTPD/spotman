import json
import os
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_DIR = os.path.expanduser("~/.config/spotifymanager")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
CSV_DIR = os.path.join(BASE_DIR, "data", "csv")
TOKEN_FILE = os.path.join(CONFIG_DIR, "token.json")

OLD_TOKEN_FILE = os.path.join(BASE_DIR, ".spotify_token.json")
OLD_CACHE_DIR = os.path.join(BASE_DIR, "cache")

SPOTIFY_API = "https://api.spotify.com/v1"
SPOTIFY_AUTH = "https://accounts.spotify.com/api/token"

CLIENT_ID = ""
CLIENT_SECRET = ""




REDIRECT_URI = "http://127.0.0.1:8888/callback"

GOOGLE_REDIRECT_URI = "https://www.google.com/"
USER_AGENT_EMAIL = "user@example.com"


def migrate_old_paths():
    
    if not os.path.exists(TOKEN_FILE) and os.path.exists(OLD_TOKEN_FILE):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        shutil.copy2(OLD_TOKEN_FILE, TOKEN_FILE)
    if os.path.isdir(OLD_CACHE_DIR) and not os.path.isdir(CACHE_DIR):
        shutil.copytree(OLD_CACHE_DIR, CACHE_DIR)


def load_credentials():
    global CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, USER_AGENT_EMAIL

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        CLIENT_ID = data.get("client_id", "")
        CLIENT_SECRET = data.get("client_secret", "")
        REDIRECT_URI = data.get("redirect_uri", REDIRECT_URI)
        USER_AGENT_EMAIL = data.get("user_agent_email", USER_AGENT_EMAIL)
        return data

    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(BASE_DIR, ".env"))
        CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
        CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
        REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", REDIRECT_URI)
        USER_AGENT_EMAIL = os.getenv("SPOTIFY_USER_AGENT_EMAIL", USER_AGENT_EMAIL)
        if CLIENT_ID:
            return {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}
    except ImportError:
        pass

    return None


def save_credentials(
    client_id, client_secret="", redirect_uri=None, user_agent_email=None
):
    global CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, USER_AGENT_EMAIL

    CLIENT_ID = client_id
    CLIENT_SECRET = client_secret
    if redirect_uri:
        REDIRECT_URI = redirect_uri
    if user_agent_email:
        USER_AGENT_EMAIL = user_agent_email

    os.makedirs(CONFIG_DIR, exist_ok=True)
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "user_agent_email": USER_AGENT_EMAIL,
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def has_credentials():
    return bool(CLIENT_ID)


migrate_old_paths()
load_credentials()
