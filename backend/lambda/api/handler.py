import os
import json
import boto3
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

CARDS_TABLE = os.environ["DYNAMODB_CARDS_TABLE"]
PRICES_TABLE = os.environ["DYNAMODB_PRICES_TABLE"]
FETCHER_FUNCTION_NAME = os.environ["FETCHER_FUNCTION_NAME"]


def lambda_handler(event, context):
    method = event["requestContext"]["http"]["method"]
    path = event.get("rawPath", "")
    params = event.get("pathParameters") or {}

    if method == "GET" and path.startswith("/prices/"):
        return get_prices(params["cardNameEn"])
    if method == "GET" and path == "/cards":
        return get_cards()
    if method == "POST" and path == "/cards":
        body = json.loads(event.get("body") or "{}")
        return post_card(body)
    if method == "DELETE" and path.startswith("/cards/"):
        return delete_card(params["cardNameEn"])
    return _resp(404, {"error": "Not Found"})


def get_prices(card_name_en: str):
    prices_table = dynamodb.Table(PRICES_TABLE)
    cards_table = dynamodb.Table(CARDS_TABLE)

    card_name_en = _resolve_card_name(cards_table, card_name_en)
    card_resp = cards_table.get_item(Key={"card_name_en": card_name_en})
    card = card_resp.get("Item")

    prices_resp = prices_table.query(
        KeyConditionExpression=Key("card_name_en").eq(card_name_en)
    )
    items = prices_resp.get("Items", [])

    # lazyモード: キャッシュがなければ即時fetch
    if not items and card and card.get("cache_mode") == "lazy":
        lambda_client.invoke(
            FunctionName=FETCHER_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "Records": [{"body": json.dumps({"card_name_en": card_name_en})}]
            }),
        )
        prices_resp = prices_table.query(
            KeyConditionExpression=Key("card_name_en").eq(card_name_en)
        )
        items = prices_resp.get("Items", [])

    return _resp(200, {"prices": [_to_native(i) for i in items]})


def _resolve_card_name(cards_table, card_name_en: str) -> str:
    resp = cards_table.get_item(
        Key={"card_name_en": card_name_en},
        ProjectionExpression="card_name_en",
    )
    if "Item" in resp:
        return card_name_en

    plus_name = card_name_en.replace(" ", "+")
    if plus_name == card_name_en:
        return card_name_en

    resp = cards_table.get_item(
        Key={"card_name_en": plus_name},
        ProjectionExpression="card_name_en",
    )
    return plus_name if "Item" in resp else card_name_en


def get_cards():
    cards_table = dynamodb.Table(CARDS_TABLE)
    items = []
    last_key = None
    while True:
        kwargs = {
            "ProjectionExpression": "card_name_en, card_name_ja, cache_mode, latest_set_code"
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        resp = cards_table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
    return _resp(200, {"cards": items})


def post_card(body: dict):
    card_name_en = body.get("card_name_en")
    if not card_name_en:
        return _resp(400, {"error": "card_name_en is required"})

    latest_set_date = body.get("latest_set_date", "2000-01-01")
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * 10)
    release = datetime.fromisoformat(latest_set_date).replace(tzinfo=timezone.utc)
    cache_mode = "scheduled" if release > cutoff else "lazy"

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "card_name_en": card_name_en,
        "card_name_ja": body.get("card_name_ja", ""),
        "latest_set_code": body.get("latest_set_code", ""),
        "latest_set_date": latest_set_date,
        "cache_mode": cache_mode,
        "fetch_status": "pending",
        "fetch_error_count": 0,
        "registered_at": now,
    }
    dynamodb.Table(CARDS_TABLE).put_item(Item=item)
    return _resp(201, {"card": item})


def delete_card(card_name_en: str):
    dynamodb.Table(CARDS_TABLE).delete_item(Key={"card_name_en": card_name_en})
    return _resp(204, {})


def _to_native(obj):
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(i) for i in obj]
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def _resp(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }
