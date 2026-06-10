import hashlib
import os
import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

CARDS_TABLE = os.environ["DYNAMODB_CARDS_TABLE"]
QUEUE_URL = os.environ["SQS_QUEUE_URL"]


def lambda_handler(event, context):
    table = dynamodb.Table(CARDS_TABLE)

    cards = []
    last_key = None
    while True:
        kwargs = {
            "IndexName": "cache_mode-index",
            "KeyConditionExpression": Key("cache_mode").eq("scheduled"),
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        resp = table.query(**kwargs)
        cards.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break

    print(f"Enqueuing {len(cards)} cards")

    enqueued = 0
    for i in range(0, len(cards), 10):
        batch = cards[i:i + 10]
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

    return {"statusCode": 200, "enqueued": enqueued}
