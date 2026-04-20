from __future__ import annotations

import json

import typer

from .env import load_project_dotenv

load_project_dotenv()

from .client import ZillowBlockedError, ZillowEstimateAgent

app = typer.Typer(help="Fetch the current Zillow Zestimate for a US address.")


@app.command()
def get(
    address: str = typer.Argument(..., help="US property address"),
    timeout_ms: int = typer.Option(30000, help="Navigation timeout in milliseconds"),
    proxy_server: str = typer.Option("", help="Optional proxy server URL"),
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
) -> None:
    agent = ZillowEstimateAgent(
        timeout_ms=timeout_ms,
        proxy_server=proxy_server or None,
        headless=headless,
    )
    try:
        result = agent.get_zestimate(address)
    except ZillowBlockedError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    typer.echo(
        json.dumps(
            {
                "address": result.address,
                "zestimate": result.zestimate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
