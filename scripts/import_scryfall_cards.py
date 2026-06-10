#!/usr/bin/env python3
"""Import Scryfall bulk card data into the mtg-cards DynamoDB table."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SCRYFALL_BULK_DATA_API = "https://api.scryfall.com/bulk-data"
DEFAULT_TABLE_NAME = "mtg-cards"
DEFAULT_BULK_TYPE = "default_cards"


@dataclass
class CardAggregate:
    oracle_id: str
    card_name_en: str
    card_name_ja: str
    latest_set_code: str
    latest_set_date: date
    image_uri: str = ""


def main() -> int:
    args = parse_args()
    bulk_path = resolve_bulk_path(args)
    imported_at = datetime.now(timezone.utc).isoformat()
    today = parse_date(args.today) if args.today else date.today()

    aggregates = build_card_master(
        iter_json_array(bulk_path),
        today=today,
        include_extras=args.include_extras,
    )

    items = [
        to_dynamodb_item(aggregate, imported_at=imported_at, today=today)
        for aggregate in sorted(aggregates.values(), key=lambda item: item.card_name_en)
    ]
    if args.limit is not None:
        items = items[: args.limit]

    print_summary(items, dry_run=args.dry_run, table_name=args.table_name)

    if args.dry_run:
        for item in items[: args.preview]:
            print(json.dumps(item, ensure_ascii=False, sort_keys=True))
        return 0

    if not items:
        print("No items to import.", file=sys.stderr)
        return 1

    upsert_items(
        items,
        table_name=args.table_name,
        profile=args.profile,
        region=args.region,
        writer=args.writer,
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build mtg-cards master data from Scryfall bulk JSON and upsert it "
            "into DynamoDB."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--bulk-json",
        type=Path,
        help="Path to a Scryfall bulk JSON file. .gz files are supported.",
    )
    source.add_argument(
        "--download",
        action="store_true",
        help="Download the latest Scryfall bulk data before importing.",
    )
    parser.add_argument(
        "--bulk-type",
        default=DEFAULT_BULK_TYPE,
        help="Scryfall bulk type to download. default: %(default)s",
    )
    parser.add_argument(
        "--table-name",
        default=DEFAULT_TABLE_NAME,
        help="DynamoDB cards table name. default: %(default)s",
    )
    parser.add_argument("--profile", help="AWS profile name, e.g. myenv.")
    parser.add_argument("--region", help="AWS region, e.g. ap-northeast-1.")
    parser.add_argument(
        "--writer",
        choices=["auto", "boto3", "aws-cli"],
        default="auto",
        help="DynamoDB writer backend. default: %(default)s",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build items and print a preview without writing to DynamoDB.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Import only the first N sorted cards. Useful for smoke tests.",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="Number of dry-run items to print. default: %(default)s",
    )
    parser.add_argument(
        "--today",
        help="Override today's date for deterministic tests. Format: YYYY-MM-DD.",
    )
    parser.add_argument(
        "--include-extras",
        action="store_true",
        help="Include Scryfall extras such as tokens, art series, and memorabilia.",
    )
    return parser.parse_args()


def resolve_bulk_path(args: argparse.Namespace) -> Path:
    if args.bulk_json:
        return args.bulk_json

    metadata = read_json_url(SCRYFALL_BULK_DATA_API)
    records = metadata.get("data", [])
    record = next((item for item in records if item.get("type") == args.bulk_type), None)
    if not record:
        raise SystemExit(f"Scryfall bulk type not found: {args.bulk_type}")

    download_uri = record.get("download_uri")
    if not download_uri:
        raise SystemExit(f"Scryfall bulk type has no download_uri: {args.bulk_type}")

    suffix = ".json.gz" if download_uri.endswith(".gz") else ".json"
    output_path = Path(tempfile.gettempdir()) / f"scryfall-{args.bulk_type}{suffix}"
    print(f"Downloading {args.bulk_type} bulk data to {output_path}", file=sys.stderr)
    urllib.request.urlretrieve(download_uri, output_path)
    return output_path


def read_json_url(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MTGPriceTracker/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Scryfall API error {exc.code}: {body}") from exc


def iter_json_array(path: Path) -> Iterable[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fp:
        decoder = json.JSONDecoder()
        buffer = ""
        saw_array_start = False

        while True:
            chunk = fp.read(1024 * 1024)
            if not chunk and not buffer.strip():
                break
            buffer += chunk

            while True:
                buffer = buffer.lstrip()
                if not saw_array_start:
                    if not buffer:
                        break
                    if buffer[0] != "[":
                        raise ValueError("Bulk file must contain a JSON array")
                    buffer = buffer[1:]
                    saw_array_start = True
                    continue

                buffer = buffer.lstrip()
                if buffer.startswith("]"):
                    return
                if buffer.startswith(","):
                    buffer = buffer[1:].lstrip()

                try:
                    value, index = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    if not chunk:
                        raise
                    break

                if not isinstance(value, dict):
                    raise ValueError("Bulk array item must be a JSON object")
                yield value
                buffer = buffer[index:]


def build_card_master(
    cards: Iterable[dict[str, Any]],
    *,
    today: date,
    include_extras: bool = False,
) -> dict[str, CardAggregate]:
    aggregates: dict[str, CardAggregate] = {}

    for card in cards:
        if not is_supported_paper_card(card, include_extras=include_extras):
            continue

        oracle_id = card["oracle_id"]
        released_at = parse_date(card["released_at"])
        name = to_wisdom_card_key(card["name"])
        set_code = str(card.get("set") or "").upper()
        printed_name = get_japanese_printed_name(card)
        image_uri = get_image_uri(card)

        current = aggregates.get(oracle_id)
        if current is None:
            aggregates[oracle_id] = CardAggregate(
                oracle_id=oracle_id,
                card_name_en=name,
                card_name_ja=printed_name,
                latest_set_code=set_code,
                latest_set_date=released_at,
                image_uri=image_uri,
            )
            continue

        if printed_name and not current.card_name_ja:
            current.card_name_ja = printed_name

        if released_at > current.latest_set_date:
            current.latest_set_date = released_at
            current.latest_set_code = set_code
            current.card_name_en = name
            if image_uri:
                current.image_uri = image_uri

    return aggregates


def is_supported_paper_card(card: dict[str, Any], *, include_extras: bool) -> bool:
    if not card.get("oracle_id"):
        return False
    if not card.get("name"):
        return False
    if not card.get("released_at"):
        return False
    if card.get("digital") is True:
        return False
    if "paper" not in card.get("games", []):
        return False
    if not include_extras and card.get("set_type") in {
        "alchemy",
        "archenemy",
        "memorabilia",
        "minigame",
        "token",
        "vanguard",
    }:
        return False
    return True


def get_japanese_printed_name(card: dict[str, Any]) -> str:
    if card.get("lang") == "ja":
        return str(card.get("printed_name") or "")
    return ""


def get_image_uri(card: dict[str, Any]) -> str:
    # Regular card
    uris = card.get("image_uris")
    if uris:
        return str(uris.get("small") or uris.get("normal") or "")
    # Double-faced card
    faces = card.get("card_faces") or []
    if faces:
        face_uris = faces[0].get("image_uris") or {}
        return str(face_uris.get("small") or face_uris.get("normal") or "")
    return ""


def to_wisdom_card_key(name: str) -> str:
    return " ".join(name.strip().split()).replace(" ", "+")


def to_dynamodb_item(
    aggregate: CardAggregate,
    *,
    imported_at: str,
    today: date,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "card_name_en": aggregate.card_name_en,
        "card_name_ja": aggregate.card_name_ja,
        "latest_set_code": aggregate.latest_set_code,
        "latest_set_date": aggregate.latest_set_date.isoformat(),
        "cache_mode": get_cache_mode(aggregate.latest_set_date, today=today),
        "fetch_status": "pending",
        "fetch_error_count": 0,
        "registered_at": imported_at,
        "last_fetched_at": "1970-01-01T00:00:00+00:00",
    }
    if aggregate.image_uri:
        item["image_uri"] = aggregate.image_uri
    return item


def get_cache_mode(latest_set_date: date, *, today: date) -> str:
    cutoff = today - timedelta(days=365 * 10)
    return "scheduled" if latest_set_date > cutoff else "lazy"


def upsert_items(
    items: list[dict[str, Any]],
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
    writer: str,
) -> None:
    if writer in {"auto", "boto3"}:
        try:
            upsert_items_boto3(
                items,
                table_name=table_name,
                profile=profile,
                region=region,
            )
            return
        except ModuleNotFoundError:
            if writer == "boto3":
                raise
            print("boto3 is not installed; falling back to AWS CLI.", file=sys.stderr)

    upsert_items_aws_cli(
        items,
        table_name=table_name,
        profile=profile,
        region=region,
    )


def upsert_items_boto3(
    items: list[dict[str, Any]],
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
) -> None:
    import boto3

    session = boto3.Session(profile_name=profile, region_name=region)
    table = session.resource("dynamodb").Table(table_name)

    with table.batch_writer(overwrite_by_pkeys=["card_name_en"]) as batch:
        for item in items:
            batch.put_item(Item=item)

    print(f"Upserted {len(items)} cards into {table_name}.")


def upsert_items_aws_cli(
    items: list[dict[str, Any]],
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
) -> None:
    # Deduplicate by card_name_en — batch-write-item rejects duplicate keys in one batch.
    # Multiple oracle_ids can share the same Wisdom Guild card key; keep the last occurrence.
    seen: dict[str, dict] = {}
    for item in items:
        seen[item["card_name_en"]] = item
    pending = [
        {"PutRequest": {"Item": to_dynamodb_attribute_map(item)}} for item in seen.values()
    ]
    written = 0

    while pending:
        chunk = pending[:25]
        pending = pending[25:]
        response = run_batch_write(
            {table_name: chunk},
            profile=profile,
            region=region,
        )
        unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])

        written += len(chunk) - len(unprocessed)
        if unprocessed:
            pending = unprocessed + pending
            time.sleep(1)

    print(f"Upserted {written} cards into {table_name}.")


def run_batch_write(
    request: dict[str, Any],
    *,
    profile: str | None,
    region: str | None,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as fp:
        json.dump(request, fp, ensure_ascii=False)
        fp.flush()

        cmd = [
            "aws",
            "dynamodb",
            "batch-write-item",
            "--request-items",
            f"file://{fp.name}",
        ]
        if profile:
            cmd.extend(["--profile", profile])
        if region:
            cmd.extend(["--region", region])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"batch-write-item failed (rc={result.returncode}): {result.stderr[:500]}", file=sys.stderr)
            result.check_returncode()
    return json.loads(result.stdout or "{}")


def to_dynamodb_attribute_map(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    attribute_map = {}
    for key, value in item.items():
        if isinstance(value, bool):
            attribute_map[key] = {"BOOL": value}
        elif isinstance(value, int):
            attribute_map[key] = {"N": str(value)}
        else:
            attribute_map[key] = {"S": str(value)}
    return attribute_map


def print_summary(
    items: list[dict[str, Any]],
    *,
    dry_run: bool,
    table_name: str,
) -> None:
    scheduled = sum(1 for item in items if item["cache_mode"] == "scheduled")
    lazy = len(items) - scheduled
    action = "Would upsert" if dry_run else "Upserting"
    print(f"{action} {len(items)} cards into {table_name}.")
    print(f"cache_mode: scheduled={scheduled}, lazy={lazy}")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


if __name__ == "__main__":
    raise SystemExit(main())
