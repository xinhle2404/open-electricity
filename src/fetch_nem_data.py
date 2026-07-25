"""Fetch NEM (National Electricity Market) data from the OpenElectricity API."""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from dotenv import load_dotenv
from openelectricity import OEClient
from openelectricity.models.timeseries import TimeSeriesResponse
from openelectricity.types import DataMetric
from supabase import Client, PostgrestAPIError, create_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NEM_DATA_TABLE = "nem_data"
UPSERT_CONFLICT_COLUMNS = "network_region,fueltech,interval_start"

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

# How far back to fetch on each run. Wider than the cron cadence so a missed
# or failed run still gets fully backfilled by the next one; the upsert key
# makes re-fetching the overlap harmless.
LOOKBACK = timedelta(hours=1)

# NEM runs on a fixed UTC+10 "market time" year-round (no daylight saving),
# and the API requires date_start as a timezone-naive datetime already
# expressed in that timezone - confirmed via a direct API call, since the
# SDK's own error message ("400 Bad Request") doesn't surface the API's
# actual detail message.
NETWORK_TIMEZONE = timezone(timedelta(hours=10))

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
        date_start=(datetime.now(timezone.utc) - LOOKBACK)
        .astimezone(NETWORK_TIMEZONE)
        .replace(tzinfo=None),
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


def upsert_rows(client: Client, rows: list[NemDataRow]) -> int:
    """Upsert rows, falling back to row-by-row on batch failure.

    The whole batch is sent as one request first (fast path, one round trip).
    If Postgres rejects it - e.g. an undocumented ``fueltech`` code violating
    the FK constraint - that one bad row would otherwise roll back the entire
    batch's transaction. Falling back to individual upserts isolates the
    failure to just the offending row(s), so every other region/fueltech in
    this interval still gets written instead of being silently lost.

    Returns the number of rows that failed to upsert (0 on full success).
    """
    table = client.table(NEM_DATA_TABLE)

    try:
        table.upsert(rows, on_conflict=UPSERT_CONFLICT_COLUMNS).execute()
        return 0
    except PostgrestAPIError as e:
        logger.warning(
            "Batch upsert of %d rows failed (%s), retrying row-by-row",
            len(rows),
            e.message,
        )

    failed = 0
    for row in rows:
        try:
            table.upsert(row, on_conflict=UPSERT_CONFLICT_COLUMNS).execute()
        except PostgrestAPIError as e:
            failed += 1
            logger.error("Failed to upsert row %s: %s", row, e.message)

    logger.info("Row-by-row upsert: %d succeeded, %d failed", len(rows) - failed, failed)
    return failed


def main() -> int:
    load_dotenv()

    dry_run = "--dry-run" in sys.argv

    api_key = os.environ.get("OPENELECTRICITY_API_KEY")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    required = [("OPENELECTRICITY_API_KEY", api_key)]
    if not dry_run:
        required += [("SUPABASE_URL", supabase_url), ("SUPABASE_KEY", supabase_key)]

    missing = [name for name, value in required if not value]
    if missing:
        logger.error("Missing required env var(s): %s", ", ".join(missing))
        return 1

    try:
        data = fetch_nem_data(api_key)
    except Exception:
        logger.exception("Failed to fetch NEM data")
        return 1

    rows = flatten_response(data)
    logger.info("Flattened %d rows", len(rows))
    if rows:
        starts = [row["interval_start"] for row in rows]
        logger.info("Interval range: %s to %s", min(starts), max(starts))

    if dry_run:
        logger.info("Dry run: skipping upsert")
        return 0

    client = create_client(supabase_url, supabase_key)
    failed = upsert_rows(client, rows)
    if failed:
        logger.error("%d row(s) failed to upsert", failed)
        return 1

    logger.info("Upserted %d rows into %s", len(rows), NEM_DATA_TABLE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
