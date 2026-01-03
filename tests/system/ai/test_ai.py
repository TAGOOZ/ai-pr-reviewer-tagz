"""AI pipeline tests."""

from typing import Tuple

from ..config import TestConfig
from ..issue_collector import IssueCollector


async def run_all(config: TestConfig, collector: IssueCollector) -> Tuple[int, int, int]:
    """Run all AI pipeline tests."""
    # Placeholder - AI tests require running AI service
    collector.add_log("AI pipeline tests placeholder - requires AI service")
    return 0, 0, 1  # 1 skipped
