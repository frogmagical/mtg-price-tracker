# REMINDER

## Current State

- React SPA, API Gateway, Lambda, DynamoDB, SQS, EventBridge Scheduler, S3, CloudFront are implemented.
- Terraform root is `infra/environments/dev`.
- Terraform backend is `s3://mkhookah-terraform/mtg-price-tracker/backend/dev/terraform.tfstate`.
- AWS profile is `myenv`.
- Frontend was deployed to CloudFront and confirmed working before cost-saving destroy.
- Price fetch was confirmed with `Drown+in+Sorrow`.
- Frontend price list hides rows where `stock` is missing or `stock <= 0`.
- Fetcher currently fetches only the first Wisdom Guild price page for each registered card.
- Dev AWS resources managed by Terraform were destroyed on 2026-06-10 for cost reduction.
- Remote Terraform state bucket `mkhookah-terraform` is intentionally retained.

## Important Caveats

- The scheduled crawler does not discover card names by itself.
- Scheduler only queries `mtg-cards` where `cache_mode = scheduled`, then enqueues those card names.
- If `mtg-cards` is empty, scheduled fetching does nothing.
- Card master initialization is required before scheduled collection is useful.
- Fetcher does not crawl pagination or follow links. It fetches one URL per card:
  `https://wonder.wisdom-guild.net/price/{card_name}/`

## Concern 1: Master Data And Latest Set Logic

Need to implement card master generation.

Desired logic:

```text
For each card:
  Find all paper printings.
  Pick the newest released_at.
  If newest released_at > today - 10 years:
    cache_mode = scheduled
  Else:
    cache_mode = lazy
```

Examples:

- `Drown in Sorrow`
  - Initial print: BNG 2014
  - Latest print: CMM 2023
  - Expected: `scheduled`
- Leyline cycle originally from Zendikar 2009
  - Latest relevant print: 2XM 2020
  - Expected: `scheduled`
- `Lightning Bolt`
  - Initial print: 1993
  - Latest print: recent reprint
  - Expected: `scheduled`
- `Black Lotus`
  - No modern paper reprint
  - Expected: `lazy`

Recommended implementation:

- Use Scryfall Bulk Data, not per-card repeated search requests.
- Prefer bulk `default_cards` or `all_cards`, grouped by a stable card identity.
- Use `oracle_id` where possible, but preserve English card name for Wisdom Guild URL generation.
- Filter to paper cards:
  - `games` contains `paper`
  - `digital == false`
  - `released_at` exists
- Store:
  - `card_name_en`
  - `card_name_ja` when available
  - `latest_set_code`
  - `latest_set_date`
  - `cache_mode`
  - `fetch_status`
  - `fetch_error_count`

Open questions:

- Whether Japanese names should come from Scryfall printed names or another source.
- Whether extras such as tokens, art series, memorabilia, minigames, and digital-only variants should be excluded.
- Whether mechanically identical split-faced names need special handling for Wisdom Guild URL format.

## Concern 2: Crawling Loop / Fetched Page Detection

Current implementation has no external page crawling loop.

- Fetcher fetches exactly one URL per card.
- It does not follow `next` links.
- It does not request `?page=N`.
- It does not maintain `visited_urls` because no page traversal exists.

If pagination is implemented later, add loop protection:

- `visited_urls` set
- `MAX_PAGES` hard limit
- same-host-only URL validation
- stop if next URL is absent
- stop if next URL was already visited
- stop if parsed row count is 0
- stop if page number does not increase
- total Lambda time budget check

Note:

- Wisdom Guild `?page=N` is currently considered session-dependent and unreliable.
- The MVP should continue using page 1 only unless a better official/tooling route is obtained.

## Backend Tasks

- Implement Scryfall Bulk Data import Lambda or local/admin script.
- Add idempotent upsert for `mtg-cards`.
- Recalculate `cache_mode` during master import.
- Add manual command/runbook for master import.
- Re-test scheduled path:
  - Insert scheduled card.
  - Invoke `mtg-scheduler`.
  - Confirm SQS enqueue.
  - Confirm Fetcher execution.
  - Confirm `mtg-prices` rows.
  - Confirm DLQ is empty.
- Consider changing Fetcher back to batch writes after IAM behavior is understood, or keep `PutItem` loop for MVP.
- Add stale price cleanup strategy if WG no longer returns an old `price_id`.
- Improve `POST /cards`:
  - require `latest_set_date`, or
  - resolve via Scryfall.
- Add API error responses when Fetcher fails during lazy fetch.
- Add API validation for malformed card names.
- Add tests for:
  - Wisdom Guild parser
  - URL generation with spaces and plus signs
  - cache mode calculation
  - API card-name normalization

## Frontend Tasks

- Improve empty state when no cards are registered.
- Improve empty state when all prices are out of stock.
- Add loading/error UI for price fetch failures.
- Add card add/resolve flow later, if on-demand registration is desired.
- Add a visible "in stock only" indicator or toggle if needed.
- Improve table layout for mobile.
- Add better Japanese labels and shop-link behavior.
- Review npm audit warnings.

## Infra / Operations Tasks

- Resource names currently do not include `env`.
  - Consider `mtg-dev-*` and `mtg-prod-*` before creating prod.
- Confirm `terraform destroy` leaves the remote state bucket intact.
- Consider `force_destroy = true` for the frontend S3 bucket in dev only, or keep the current safer default and empty the bucket before destroy.
- Documented deploy caveat:
  - `terraform apply` creates infrastructure only.
  - frontend build/S3 sync/CloudFront invalidation are separate.
  - card master import/test data insertion is separate.
  - scheduled fetching does nothing until `mtg-cards` has `cache_mode = scheduled` rows.
- Add Makefile or scripts:
  - `terraform init/plan/apply/destroy`
  - frontend build
  - S3 sync
  - CloudFront invalidation
- Add CloudWatch alarms:
  - Fetcher errors
  - Scheduler errors
  - DLQ messages
- Add logs/runbook for common failures.
- Consider CloudFront price class reduction for cost.
- Consider S3 lifecycle settings for frontend artifacts if needed.

## Mobile / Product Tasks

- Decide whether App Store release is still in scope.
- Add native feature for App Store review:
  - push notifications, or
  - local watchlist.
- Design watchlist and price-change notification flow.

## Useful Commands

Terraform root:

```bash
cd /home/tokium/Git/MyProject/mtg-price-tracker/infra/environments/dev
terraform init -reconfigure
terraform plan
terraform apply
terraform destroy
```

Frontend deploy:

```bash
cd /home/tokium/Git/MyProject/mtg-price-tracker/frontend
npm install
npm run build
aws s3 sync dist/ s3://mtg-price-frontend-571869849221/ --delete --profile myenv
aws cloudfront create-invalidation --distribution-id E22MAYUA815TXG --paths '/*' --profile myenv
```

API smoke test:

```bash
curl https://le9br77mf6.execute-api.ap-northeast-1.amazonaws.com/cards
curl https://le9br77mf6.execute-api.ap-northeast-1.amazonaws.com/prices/Drown%2Bin%2BSorrow
```
