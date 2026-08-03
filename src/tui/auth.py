from .. import config
from .console import console


def show_auth(client):
    console.print()
    console.print("[bold yellow]🔑 Autenticación Spotify[/bold yellow]")
    console.print()
    console.print("  1. Automático (abre navegador + captura el code solo)")
    console.print("  2. Manual (copia y pega el código)")
    console.print("  3. Cancelar")
    choice = console.input("  Selecciona una opción (1-3): ").strip()

    if choice == "3":
        console.print("[red]Cancelado[/red]")
        return None

    if choice == "1":
        return auth_auto(client)

    return auth_manual(client)


def auth_auto(client):
    return client.auth_via_browser()


def auth_manual(client):
    url = client.get_auth_url(redirect_uri=config.GOOGLE_REDIRECT_URI)
    console.print()
    console.print("[bold]Abre esta URL en tu navegador:[/bold]")
    console.print()
    console.print(f"  [link={url}]{url}[/link]")
    console.print()
    console.print("[cyan]Paso 1:[/cyan] Copia la URL de arriba y pégala en tu navegador")
    console.print("[cyan]Paso 2:[/cyan] Haz clic en 'Agree' para autorizar")
    console.print("[cyan]Paso 3:[/cyan] Serás redirigido a Google. En la barra de dirección")
    console.print(
        "       verás algo como: [dim]https://www.google.com/?code=AQDl...[/dim]"
    )
    console.print(
        "[cyan]Paso 4:[/cyan] Copia TODO lo que viene después de [bold]code=[/bold]"
    )
    console.print("       (el código largo, NO la URL completa)")
    console.print()
    code = console.input("  Pega el código aquí: ").strip()
    if not code:
        console.print("[red]Cancelado[/red]")
        return None

    if not client.exchange_code(code, redirect_uri=config.GOOGLE_REDIRECT_URI):
        console.print("[red]Error en la autenticación. Verifica el código.[/red]")
        return None

    user = client.get_user()
    if not user:
        console.print("[red]Error al obtener usuario después de autenticar.[/red]")
        return None

    name = user.get("display_name", user["id"]) if user else "?"
    console.print(f"\n[green]✓ Autenticado como: {name}[/green]")
    return user
