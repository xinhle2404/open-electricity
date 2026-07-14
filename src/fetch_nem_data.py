"""Fetch NEM (National Electricity Market) data from the OpenElectricity API."""

import json
import logging
import os
import sys

from dotenv import load_dotenv
from openelectricity import OEClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NETWORK_CODE = "NEM"
METRICS = ["power"]
INTERVAL = "5m"


def fetch_nem_data(api_key: str) -> dict:
    client = OEClient(api_key=api_key)
    return client.get_network_data(
        network_code=NETWORK_CODE,
        metrics=METRICS,
        interval=INTERVAL,
    )


def main() -> int:
    load_dotenv()

    api_key = os.environ.get("OPENELECTRICITY_API_KEY")
    if not api_key:
        logger.error("Missing OPENELECTRICITY_API_KEY env var")
        return 1

    try:
        data = fetch_nem_data(api_key)
    except Exception:
        logger.exception("Failed to fetch NEM data")
        return 1

    logger.info("Fetched NEM data:\n%s", json.dumps(data, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
