"""Fetch NEM (National Electricity Market) data from the OpenElectricity API."""

import logging
import os
import sys
from typing import TypedDict

from dotenv import load_dotenv
from openelectricity import OEClient
from openelectricity.models.timeseries import TimeSeriesResponse
from openelectricity.types import DataMetric

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NETWORK_CODE = "NEM"
METRICS = [
    DataMetric.POWER,
    DataMetric.ENERGY,
    DataMetric.EMISSIONS,
    DataMetric.MARKET_VALUE,
    DataMetric.STORAGE_BATTERY,
]
INTERVAL = "5m"
PRIMARY_GROUPING = "network_region"
SECONDARY_GROUPING = "fueltech"

# Maps each DataMetric to the column it fills in a merged row.
METRIC_COLUMNS = {
    DataMetric.POWER: "power_mw",
    DataMetric.ENERGY: "energy_mwh",
    DataMetric.EMISSIONS: "emissions_t",
    DataMetric.MARKET_VALUE: "market_value_dollars",
    DataMetric.STORAGE_BATTERY: "storage_battery_mwh",
}


class NemDataRow(TypedDict):
    network_region: str
    fueltech: str
    interval_start: str
    power_mw: float | None
    energy_mwh: float | None
    emissions_t: float | None
    market_value_dollars: float | None
    storage_battery_mwh: float | None


def fetch_nem_data(api_key: str) -> TimeSeriesResponse:
    client = OEClient(api_key=api_key)
    return client.get_network_data(
        network_code=NETWORK_CODE,
        metrics=METRICS,
        interval=INTERVAL,
        primary_grouping=PRIMARY_GROUPING,
        secondary_grouping=SECONDARY_GROUPING,
    )


def flatten_response(response: TimeSeriesResponse) -> list[NemDataRow]:
    """Flatten the grouped, multi-metric response into tidy rows.

    Each requested metric comes back as its own series block, so readings for
    the same (region, fueltech, timestamp) are merged into a single row keyed
    on that triple, with one column per metric.

    The installed SDK's parsed ``columns.network_region`` is always None (the
    raw API sends the region under a ``region`` key, which the SDK's column
    model doesn't map), so the region is recovered from ``result.name``
    instead, which is reliably formatted as ``{metric}_{region}|{fueltech}``.
    """
    rows_by_key: dict[tuple[str, str, str], NemDataRow] = {}

    for series_block in response.data:
        metric_prefix = f"{series_block.metric}_"
        column = METRIC_COLUMNS[series_block.metric]

        for result in series_block.results:
            region = result.name.removeprefix(metric_prefix).split("|")[0]
            fueltech = result.columns.fueltech

            for point in result.data:
                timestamp, value = point.root
                interval_start = timestamp.isoformat()
                key = (region, fueltech, interval_start)

                if key not in rows_by_key:
                    rows_by_key[key] = NemDataRow(
                        network_region=region,
                        fueltech=fueltech,
                        interval_start=interval_start,
                        power_mw=None,
                        energy_mwh=None,
                        emissions_t=None,
                        market_value_dollars=None,
                        storage_battery_mwh=None,
                    )
                rows_by_key[key][column] = value

    return list(rows_by_key.values())


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

    rows = flatten_response(data)
    logger.info("Flattened %d rows", len(rows))
    for row in rows[:5]:
        logger.info(row)
    if len(rows) > 5:
        logger.info("... (%d more rows)", len(rows) - 5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
