"""Trigger a Fabric Data Pipeline and stream status to the caller."""
from __future__ import annotations

from .fabric_api import FabricClient


def run_pipeline_and_wait(client: FabricClient, pipeline_id: str, *,
                          timeout_s: int = 1800,
                          parameters: dict | None = None):
    """Run pipeline, poll until terminal state, yield (elapsed_s, status) tuples."""
    status_url = client.run_pipeline(pipeline_id, parameters=parameters)
    progress: list[tuple[int, str]] = []

    def on_tick(elapsed, status):
        progress.append((elapsed, status))

    final = client.poll_job(status_url, timeout_s=timeout_s, on_tick=on_tick)
    return status_url, progress, final
