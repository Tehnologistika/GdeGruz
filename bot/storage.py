import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_FILE = Path("data/points.csv")


async def save_point(user_id: int, lat: float, lon: float, ts: datetime) -> None:
    """Persist the location to a CSV file."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{ts.isoformat()},{user_id},{lat},{lon}\n")
    logger.info("Saved point for %s", user_id)
