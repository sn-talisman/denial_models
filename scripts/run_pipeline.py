#!/usr/bin/env python3
"""CLI entry point for pipeline execution."""

import asyncio
import os
import sys
from pathlib import Path
from datetime import date, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from dotenv import load_dotenv
import structlog

from src.data_access.factory import get_repository
from src.pipelines.pipeline_runner import PipelineRunner
from src.utils.logging_config import configure_logging

app = typer.Typer()
logger = structlog.get_logger(__name__)

# Load environment variables
load_dotenv()


@app.command()
def ingest(
    practice_id: str = typer.Option(None, help="Filter by practice ID"),
    payer_id: str = typer.Option(None, help="Filter by payer ID"),
    days_back: int = typer.Option(30, help="Number of days back to fetch"),
    limit: int = typer.Option(1000, help="Maximum number of claims"),
):
    """Run data ingestion pipeline."""
    configure_logging()
    logger.info("Starting ingestion pipeline", practice_id=practice_id, payer_id=payer_id)
    
    async def run():
        repository = get_repository()
        try:
            date_from = date.today() - timedelta(days=days_back)
            date_to = date.today()
            
            runner = PipelineRunner(repository)
            df = await runner.run_full_pipeline(
                practice_id=practice_id,
                payer_id=payer_id,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )
            
            logger.info("Pipeline completed", rows=len(df))
            print(f"Ingested {len(df)} claims")
            
        finally:
            await repository.close()
    
    asyncio.run(run())


if __name__ == "__main__":
    app()

