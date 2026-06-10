#!/usr/bin/env python3
"""Enrich card_name_ja in DynamoDB by fetching Japanese card names from Scryfall.

Uses the Scryfall search API (paginated) to get all Japanese-language cards,
then updates DynamoDB items that are missing card_name_ja.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_TABLE_NAME = "mtg-cards"
DEFAULT_PROFILE = "myenv"
DEFAULT_REGION = "ap-northeast-1"
SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"
USER_AGENT = "MTGPriceTracker/1.0"
REQUEST_DELAY = 0.2  # 5 req/s to stay safely under Scryfall's 10 req/s limit


def main() -> int:
    args = parse_args()

    print("Fetching Japanese card names from Scryfall...", flush=True)
    ja_names = fetch_all_japanese_names()
    print(f"Found {len(ja_names)} unique Japanese card mappings.", flush=True)

    if args.dry_run:
        for en, ja in list(ja_names.items())[:10]:
            print(f"  {en!r} -> {ja!r}")
        return 0

    print("Updating DynamoDB...", flush=True)
    updated = update_dynamodb(
        ja_names,
        table_name=args.table_name,
        profile=args.profile,
        region=args.region,
    )
    print(f"Updated {updated} cards with Japanese names.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Japanese names from Scryfall and populate card_name_ja in DynamoDB."
    )
    parser.add_argument("--table-name", default=DEFAULT_TABLE_NAME)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--dry-run", action="store_true", help="Print first 10 mappings, no DB write.")
    return parser.parse_args()


def fetch_all_japanese_names() -> dict[str, str]:
    """Return {en_wisdom_key: ja_printed_name} for all Japanese paper cards."""
    # unique=prints gives one result per printing; lang:ja filters to Japanese only.
    # We request all paper cards, sorted by name for stable pagination.
    base_params = {
        "q": "lang:ja game:paper",
        "unique": "prints",
        "order": "name",
        "page": "1",
    }
    ja_names: dict[str, str] = {}
    page = 1

    while True:
        base_params["page"] = str(page)
        url = f"{SCRYFALL_SEARCH_URL}?{urllib.parse.urlencode(base_params)}"
        data = request_json(url)

        for card in data.get("data", []):
            en_name = card.get("name", "")
            printed_name = card.get("printed_name", "")
            if en_name and printed_name:
                key = to_wisdom_card_key(en_name)
                if key not in ja_names:
                    ja_names[key] = printed_name

        print(f"  Page {page}: {len(data.get('data', []))} cards (total so far: {len(ja_names)})", flush=True)

        if not data.get("has_more", False):
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return ja_names


def request_json(url: str, *, retry: int = 3) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    for attempt in range(retry):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                return {"data": [], "has_more": False}
            if exc.code == 429 and attempt < retry - 1:
                wait = 65 * (attempt + 1)
                print(f"  Rate limited (429). Waiting {wait}s before retry {attempt + 2}/{retry}...", flush=True)
                time.sleep(wait)
                continue
            raise SystemExit(f"Scryfall API error {exc.code}: {body[:300]}") from exc
    raise SystemExit("Exceeded retries")


def to_wisdom_card_key(name: str) -> str:
    return " ".join(name.strip().split()).replace(" ", "+")


def update_dynamodb(
    ja_names: dict[str, str],
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
) -> int:
    try:
        import boto3
        return _update_boto3(ja_names, table_name=table_name, profile=profile, region=region)
    except ModuleNotFoundError:
        return _update_cli(ja_names, table_name=table_name, profile=profile, region=region)


def _update_boto3(
    ja_names: dict[str, str],
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
) -> int:
    import boto3
    from boto3.dynamodb.conditions import Attr

    session = boto3.Session(profile_name=profile, region_name=region)
    table = session.resource("dynamodb").Table(table_name)

    updated = 0
    # Scan for cards with empty card_name_ja
    scan_kwargs: dict[str, Any] = {
        "FilterExpression": Attr("card_name_ja").eq(""),
        "ProjectionExpression": "card_name_en",
    }

    while True:
        resp = table.scan(**scan_kwargs)
        cards = resp.get("Items", [])
        print(f"  Batch: {len(cards)} cards missing Japanese name...", flush=True)

        for card in cards:
            en = str(card.get("card_name_en", ""))
            ja = ja_names.get(en, "")
            if not ja:
                continue
            table.update_item(
                Key={"card_name_en": en},
                UpdateExpression="SET card_name_ja = :ja",
                ExpressionAttributeValues={":ja": ja},
            )
            updated += 1

        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return updated


def _update_cli(
    ja_names: dict[str, str],
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
) -> int:
    import subprocess

    updated = 0
    for en, ja in ja_names.items():
        cmd = [
            "aws", "dynamodb", "update-item",
            "--table-name", table_name,
            "--key", json.dumps({"card_name_en": {"S": en}}),
            "--condition-expression", "card_name_ja = :empty",
            "--update-expression", "SET card_name_ja = :ja",
            "--expression-attribute-values", json.dumps({":ja": {"S": ja}, ":empty": {"S": ""}}),
        ]
        if profile:
            cmd.extend(["--profile", profile])
        if region:
            cmd.extend(["--region", region])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            updated += 1
        elif "ConditionalCheckFailedException" not in result.stderr:
            print(f"  Warning: failed to update {en}: {result.stderr[:100]}", file=sys.stderr)

    return updated


if __name__ == "__main__":
    raise SystemExit(main())
