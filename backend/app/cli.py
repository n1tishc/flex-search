from __future__ import annotations

import asyncio
import logging

import typer

app = typer.Typer(help="GitHub Fixability Search batch jobs")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def _init() -> None:
    from app.db.connection import init_db
    await init_db()


async def _close() -> None:
    from app.db.connection import close_db
    await close_db()


@app.command()
def sync(csv_path: str | None = None) -> None:
    """Sync repos, issues, and comments from GitHub into the local DB."""
    async def _run() -> None:
        await _init()
        from app.services.ingestion_service import IngestionService
        svc = IngestionService()
        stats = await svc.run_full_sync(csv_path)
        typer.echo(f"Sync complete: {stats}")
        await _close()

    asyncio.run(_run())


@app.command()
def score() -> None:
    """Compute fixability scores for all dirty issues."""
    async def _run() -> None:
        await _init()
        from app.services.feature_service import score_all_dirty
        count = await score_all_dirty()
        typer.echo(f"Scored {count} issues")
        await _close()

    asyncio.run(_run())


@app.command()
def full(csv_path: str | None = None) -> None:
    """Run full pipeline: sync then score."""
    async def _run() -> None:
        await _init()
        from app.services.ingestion_service import IngestionService
        svc = IngestionService()
        stats = await svc.run_full_sync(csv_path)
        typer.echo(f"Sync complete: {stats}")

        from app.services.feature_service import score_all_dirty
        count = await score_all_dirty()
        typer.echo(f"Scored {count} issues")
        await _close()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
