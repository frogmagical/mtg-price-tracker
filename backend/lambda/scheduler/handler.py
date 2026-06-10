import hashlib
import os
import json
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta, timezone

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

CARDS_TABLE = os.environ["DYNAMODB_CARDS_TABLE"]
QUEUE_URL = os.environ["SQS_QUEUE_URL"]

ACTIVE_WINDOW_DAYS = 30


def lambda_handler(event, context):
    table = dynamodb.Table(CARDS_TABLE)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=ACTIVE_WINDOW_DAYS)).isoformat()

    cards = []
    last_key = None
    while True:
        kwargs = {
            "IndexName": "cache_mode-index",
            "KeyConditionExpression": Key("cache_mode").eq("scheduled"),
            "ProjectionExpression": "card_name_en, last_viewed_at",
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        resp = table.query(**kwargs)
        cards.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break

    # 直近 ACTIVE_WINDOW_DAYS 日以内に閲覧されたカードのみキューイング
    active = [c for c in cards if c.get("last_viewed_at", "") >= cutoff]

    print(f"Scheduled total: {len(cards)}, Active (viewed within {ACTIVE_WINDOW_DAYS}d): {len(active)}")

    enqueued = 0
    for i in range(0, len(active), 10):
        batch = active[i:i + 10]
        entries = [
            {
                "Id": str(j),
                "MessageBody": json.dumps({"card_name_en": card["card_name_en"]}),
                "MessageGroupId": "default",
                "MessageDeduplicationId": hashlib.sha256(card["card_name_en"].encode()).hexdigest(),
            }
            for j, card in enumerate(batch)
        ]
        sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=entries)
        enqueued += len(batch)

    return {"statusCode": 200, "enqueued": enqueued, "total_scheduled": len(cards)}
