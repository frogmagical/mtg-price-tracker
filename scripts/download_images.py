#!/usr/bin/env python3
"""Download card images from Scryfall URLs and upload them to frontend S3."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


DEFAULT_TABLE_NAME = "mtg-cards"
DEFAULT_BUCKET_NAME = "mtg-price-frontend-571869849221"
DEFAULT_PROFILE = "myenv"
DEFAULT_REGION = "ap-northeast-1"
DEFAULT_MAX_REQUESTS_PER_SECOND = 3.0
USER_AGENT = "MTGPriceTracker/1.0"


@dataclass(frozen=True)
class CardImage:
    card_name_en: str
    image_uri: str

    @property
    def s3_key(self) -> str:
        # S3 keys are plain strings, not URLs — store as-is (card_name_en uses + for spaces).
        # CloudFront decodes %2B→+ when forwarding to S3, so keys must use raw + chars.
        return f"images/{self.card_name_en}.jpg"


@dataclass
class DownloadError:
    card_name_en: str
    image_uri: str
    message: str


class RateLimiter:
    def __init__(self, max_per_second: float) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")
        self.min_interval = 1.0 / max_per_second
        self.last_request_at = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_at = time.monotonic()


def main() -> int:
    args = parse_args()
    print(f"Scanning DynamoDB table {args.table_name}...", flush=True)

    cards = scan_cards(
        table_name=args.table_name,
        profile=args.profile,
        region=args.region,
        backend=args.backend,
    )
    if args.limit is not None:
        cards = cards[: args.limit]

    total = len(cards)
    if total == 0:
        print("No cards with image_uri found.")
        return 0

    print(f"Found {total} cards with image_uri.")
    stats, errors = process_cards(
        cards,
        bucket_name=args.bucket_name,
        profile=args.profile,
        region=args.region,
        backend=args.backend,
        force=args.force,
        max_requests_per_second=args.max_requests_per_second,
    )

    print(
        "Done: "
        f"processed={total}, uploaded={stats['uploaded']}, "
        f"skipped={stats['skipped']}, failed={len(errors)}"
    )
    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"- {error.card_name_en}: {error.message} ({error.image_uri})")
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan mtg-cards for image_uri, download images from Scryfall, "
            "and upload them to S3 under images/{card_name_en}.jpg."
        )
    )
    parser.add_argument(
        "--table-name",
        default=DEFAULT_TABLE_NAME,
        help="DynamoDB cards table name. default: %(default)s",
    )
    parser.add_argument(
        "--bucket-name",
        default=DEFAULT_BUCKET_NAME,
        help="S3 bucket for card images. default: %(default)s",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="AWS profile name. default: %(default)s",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help="AWS region. default: %(default)s",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "boto3", "aws-cli"],
        default="auto",
        help="AWS backend. default: %(default)s",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite images that already exist in S3.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only the first N cards with image_uri.",
    )
    parser.add_argument(
        "--max-requests-per-second",
        type=float,
        default=DEFAULT_MAX_REQUESTS_PER_SECOND,
        help="Maximum Scryfall image downloads per second. default: %(default)s",
    )
    return parser.parse_args()


def scan_cards(
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
    backend: str,
) -> list[CardImage]:
    if backend in {"auto", "boto3"}:
        try:
            return scan_cards_boto3(
                table_name=table_name,
                profile=profile,
                region=region,
            )
        except ModuleNotFoundError:
            if backend == "boto3":
                raise
            print("boto3 is not installed; falling back to AWS CLI.", file=sys.stderr)

    return scan_cards_aws_cli(
        table_name=table_name,
        profile=profile,
        region=region,
    )


def scan_cards_boto3(
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
) -> list[CardImage]:
    import boto3
    from boto3.dynamodb.conditions import Attr

    session = boto3.Session(profile_name=profile, region_name=region)
    table = session.resource("dynamodb").Table(table_name)
    cards: list[CardImage] = []
    scan_kwargs: dict[str, Any] = {
        "FilterExpression": Attr("image_uri").exists(),
        "ProjectionExpression": "#name, image_uri",
        "ExpressionAttributeNames": {"#name": "card_name_en"},
    }

    while True:
        response = table.scan(**scan_kwargs)
        cards.extend(card for card in iter_card_images(response.get("Items", [])))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return sorted(cards, key=lambda card: card.card_name_en)


def scan_cards_aws_cli(
    *,
    table_name: str,
    profile: str | None,
    region: str | None,
) -> list[CardImage]:
    cards: list[CardImage] = []
    exclusive_start_key: dict[str, Any] | None = None

    while True:
        cmd = [
            "aws",
            "dynamodb",
            "scan",
            "--table-name",
            table_name,
            "--filter-expression",
            "attribute_exists(image_uri)",
            "--projection-expression",
            "#name, image_uri",
            "--expression-attribute-names",
            json.dumps({"#name": "card_name_en"}),
            "--output",
            "json",
        ]
        if exclusive_start_key:
            cmd.extend(["--exclusive-start-key", json.dumps(exclusive_start_key)])
        add_aws_options(cmd, profile=profile, region=region)

        response = run_json_command(cmd)
        cards.extend(
            card
            for card in iter_card_images(
                from_dynamodb_attribute_map(item)
                for item in response.get("Items", [])
            )
        )

        exclusive_start_key = response.get("LastEvaluatedKey")
        if not exclusive_start_key:
            break

    return sorted(cards, key=lambda card: card.card_name_en)


def iter_card_images(items: Iterable[dict[str, Any]]) -> Iterable[CardImage]:
    for item in items:
        card_name_en = str(item.get("card_name_en") or "").strip()
        image_uri = str(item.get("image_uri") or "").strip()
        if card_name_en and image_uri:
            yield CardImage(card_name_en=card_name_en, image_uri=image_uri)


def process_cards(
    cards: list[CardImage],
    *,
    bucket_name: str,
    profile: str | None,
    region: str | None,
    backend: str,
    force: bool,
    max_requests_per_second: float,
) -> tuple[dict[str, int], list[DownloadError]]:
    s3_client = build_s3_client(profile=profile, region=region, backend=backend)
    rate_limiter = RateLimiter(max_requests_per_second)
    stats = {"uploaded": 0, "skipped": 0}
    errors: list[DownloadError] = []
    total = len(cards)

    for index, card in enumerate(cards, start=1):
        prefix = f"[{index}/{total}] {card.card_name_en}"
        try:
            if not force and s3_exists(s3_client, bucket_name, card.s3_key):
                stats["skipped"] += 1
                print(f"{prefix}: skipped existing s3://{bucket_name}/{card.s3_key}", flush=True)
                continue

            rate_limiter.wait()
            image = download_image(card.image_uri)
            s3_put(s3_client, bucket_name, card.s3_key, image)
            stats["uploaded"] += 1
            print(f"{prefix}: uploaded s3://{bucket_name}/{card.s3_key}", flush=True)
        except Exception as exc:  # noqa: BLE001 - continue after per-card failures.
            errors.append(
                DownloadError(
                    card_name_en=card.card_name_en,
                    image_uri=card.image_uri,
                    message=str(exc),
                )
            )
            print(f"{prefix}: failed: {exc}", flush=True)

    return stats, errors


def build_s3_client(*, profile: str | None, region: str | None, backend: str) -> Any:
    if backend in {"auto", "boto3"}:
        try:
            import boto3

            session = boto3.Session(profile_name=profile, region_name=region)
            return session.client("s3")
        except ModuleNotFoundError:
            if backend == "boto3":
                raise
            print("boto3 is not installed; falling back to AWS CLI.", file=sys.stderr)

    return AwsCliS3Client(profile=profile, region=region)


class AwsCliS3Client:
    def __init__(self, *, profile: str | None, region: str | None) -> None:
        self.profile = profile
        self.region = region


def s3_exists(s3_client: Any, bucket_name: str, key: str) -> bool:
    if isinstance(s3_client, AwsCliS3Client):
        cmd = ["aws", "s3api", "head-object", "--bucket", bucket_name, "--key", key]
        add_aws_options(cmd, profile=s3_client.profile, region=s3_client.region)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        stderr = result.stderr.lower()
        if "not found" in stderr or "404" in stderr or "nosuchkey" in stderr:
            return False
        raise RuntimeError(result.stderr.strip() or f"head-object failed for {key}")

    try:
        s3_client.head_object(Bucket=bucket_name, Key=key)
        return True
    except Exception as exc:  # noqa: BLE001 - botocore may not be importable by name.
        if is_not_found_error(exc):
            return False
        raise


def s3_put(s3_client: Any, bucket_name: str, key: str, image: bytes) -> None:
    if isinstance(s3_client, AwsCliS3Client):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as fp:
            fp.write(image)
            fp.flush()
            cmd = [
                "aws",
                "s3api",
                "put-object",
                "--bucket",
                bucket_name,
                "--key",
                key,
                "--body",
                fp.name,
                "--content-type",
                "image/jpeg",
            ]
            add_aws_options(cmd, profile=s3_client.profile, region=s3_client.region)
            run_json_command(cmd)
        return

    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=image,
        ContentType="image/jpeg",
    )


def download_image(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/*",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"download failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"download failed: {exc}") from exc


def is_not_found_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error = response.get("Error", {})
    code = str(error.get("Code", "")).lower()
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status == 404 or code in {"404", "notfound", "nosuchkey", "no such key"}


def from_dynamodb_attribute_map(attribute_map: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for key, value in attribute_map.items():
        if "S" in value:
            item[key] = value["S"]
        elif "N" in value:
            item[key] = value["N"]
        elif "BOOL" in value:
            item[key] = value["BOOL"]
        elif "NULL" in value:
            item[key] = None
    return item


def add_aws_options(cmd: list[str], *, profile: str | None, region: str | None) -> None:
    if profile:
        cmd.extend(["--profile", profile])
    if region:
        cmd.extend(["--region", region])


def run_json_command(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"command failed: {' '.join(cmd)}")
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
