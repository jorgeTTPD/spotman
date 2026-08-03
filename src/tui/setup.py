import re
from rich.panel import Panel
from .. import config

SETUP_TEXT = """\
[bold]Necesitas tu Client ID de Spotify (sin Client Secret, usamos PKCE).[/bold]

Obténlo desde [link]https://developer.spotify.com/dashboard[/link]:
  [cyan]1.[/cyan] Abre el Dashboard y selecciona tu app
  [cyan]2.[/cyan] Copia el [bold]Client ID[/bold] (NO necesitas Client Secret)
  [cyan]3.[/cyan] En tu app, agrega estas [bold]2 Redirect URIs[/bold]:
       [green]http://127.0.0.1:8888/callback[/green]   (flujo automático)
       [green]https://www.google.com/[/green]          (respaldo manual)

El flujo automático abre el navegador, Spotify redirige a tu localhost
y la app captura el código sola (sin pegar nada en la terminal)."""


def _clean(value):
    return re.sub(r"[^a-zA-Z0-9\-]", "", value)


def run_setup(console):
    console.print(
        Panel(SETUP_TEXT, title="🎵 Configuración Inicial", border_style="cyan")
    )
    console.print()

    console.print("[bold]Pega tu Client ID:[/bold]")
    console.print(
        "  [dim]Si no sabes cuál es, revisa https://developer.spotify.com/dashboard[/dim]"
    )
    client_id = _clean(input("  > ").strip())
    if not client_id:
        console.print("[red]Cancelado[/red]")
        return False

    config.save_credentials(
        client_id,
        client_secret="",
        redirect_uri="http://127.0.0.1:8888/callback",
    )
    console.print(f"\n[green]✓ Client ID guardado en {config.CONFIG_FILE}[/green]")
    console.print(
        "[yellow]Login automático: localhost captura el code solo; manual: Google[/yellow]"
    )
    return True
