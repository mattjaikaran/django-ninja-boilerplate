"""Rich console utilities for beautiful terminal output."""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

# Global console instance
console = Console()


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue][INFO][/blue] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green][SUCCESS][/green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow][WARNING][/yellow] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red][ERROR][/red] {message}")


def print_step(message: str) -> None:
    """Print a step message."""
    console.print(f"[cyan][STEP][/cyan] {message}")


def print_header(title: str) -> None:
    """Print a header panel."""
    panel = Panel(
        Text(title, justify="center"),
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(panel)


def create_progress() -> Progress:
    """Create a progress bar with spinner."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )


def create_table(title: str, columns: list[str]) -> Table:
    """Create a styled table."""
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for col in columns:
        table.add_column(col)
    return table


def print_key_value(key: str, value: str, key_style: str = "cyan") -> None:
    """Print a key-value pair."""
    console.print(f"  [{key_style}]{key}:[/{key_style}] {value}")


def confirm(message: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    from rich.prompt import Confirm

    return Confirm.ask(message, default=default)


def prompt(message: str, default: str = "") -> str:
    """Ask for text input."""
    from rich.prompt import Prompt

    return Prompt.ask(message, default=default)
