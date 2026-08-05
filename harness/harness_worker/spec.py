"""Constants and node factory for the Harness worker agent."""

from app.agents.harness.harness_worker.nodes import HarnessWorkerNode

HARNESS_WORKER_AGENT_NAME = "harness_worker"
HARNESS_WORKER_ENTRYPOINT = "harness_worker"


def create_harness_worker_node() -> HarnessWorkerNode:
    """Create the Harness worker node."""

    return HarnessWorkerNode()
