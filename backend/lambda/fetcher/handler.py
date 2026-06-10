import os
import json
import urllib.request
import urllib.error
import urllib.parse
import boto3
from datetime import datetime, timedelta, timezone
from parser import parse_prices

dynamodb = boto3.resource("dynamodb")

CARDS_TABLE = os.environ["DYNAMODB_CARDS_TABLE"]
PRICES_TABLE = os.environ["DYNAMODB_PRICES_TABLE"]
BASE_URL = "https://wonder.wisdom-guild.net/price/{}/"


def lambda_handler(event, context):
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Invalid SQS record body: {e}")
            continue
        card_name = body.get("card_name_en")
        if not card_name:
            print(f"Missing card_name_en in record body")
            continue
        process_card(card_name)


def process_card(card_name_en: str):
    cards_table = dynamodb.Table(CARDS_TABLE)
    prices_table = dynamodb.Table(PRICES_TABLE)

    card_path = urllib.parse.quote(card_name_en.replace(" ", "+"), safe="+")
    url = BASE_URL.format(card_path)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MTGPriceTracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            cards_table.update_item(
                Key={"card_name_en": card_name_en},
                UpdateExpression="SET fetch_status = :s",
                ExpressionAttributeValues={":s": "not_found"},
            )
            return
        _record_error(cards_table, card_name_en)
        raise
    except Exception:
        _record_error(cards_table, card_name_en)
        raise

    prices = parse_prices(html, card_name_en, url)

    cache_mode = _get_cache_mode(cards_table, card_name_en)
    ttl = _calc_ttl(cache_mode)

    for p in prices:
        item = {**p, "TTL": ttl}
        if item["stock"] is None:
            del item["stock"]
        prices_table.put_item(Item=item)

    now = datetime.now(timezone.utc).isoformat()
    cards_table.update_item(
        Key={"card_name_en": card_name_en},
        UpdateExpression="SET last_fetched_at = :t, fetch_status = :s, fetch_error_count = :z",
        ExpressionAttributeValues={":t": now, ":s": "ok", ":z": 0},
    )
    print(f"Fetched {len(prices)} prices for {card_name_en}")


def _get_cache_mode(table, card_name_en: str) -> str:
    resp = table.get_item(
        Key={"card_name_en": card_name_en},
        ProjectionExpression="cache_mode",
    )
    return resp.get("Item", {}).get("cache_mode", "lazy")


def _calc_ttl(cache_mode: str) -> int:
    hours = 48 if cache_mode == "scheduled" else 24
    return int((datetime.now(timezone.utc) + timedelta(hours=hours)).timestamp())


def _record_error(table, card_name_en: str):
    table.update_item(
        Key={"card_name_en": card_name_en},
        UpdateExpression="SET fetch_status = :s, fetch_error_count = if_not_exists(fetch_error_count, :z) + :one",
        ExpressionAttributeValues={":s": "error", ":z": 0, ":one": 1},
    )
