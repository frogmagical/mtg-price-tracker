# MTG Price Tracker

MTGシングルカードの国内価格を Wisdom Guild から取得し、複数ショップの価格を一覧表示するWebアプリです。

サーバーレス構成で日次収集を行い、React SPAからAPI Gateway経由で価格データを参照します。

## Current Status

- AWSインフラは Terraform module 構成で実装済みです。
- Terraform root は `infra/environments/dev` です。
- AWS profile は `myenv`、region は `ap-northeast-1` を使用します。
- Terraform remote state は `s3://mkhookah-terraform/mtg-price-tracker/backend/dev/terraform.tfstate` です。
- React SPA、API Gateway、Lambda、DynamoDB、SQS、EventBridge Scheduler、S3、CloudFront は実装済みです。
- 価格一覧画面では在庫なしデータを非表示にします。
- コスト削減のため、2026-06-10 時点で dev 環境のAWSリソースは `terraform destroy` 済みです。

詳細な設計・実装メモは [CLAUDE.md](./CLAUDE.md) を参照してください。
残タスクは [REMINDER.md](./REMINDER.md) にまとめています。

## Architecture

```text
EventBridge Scheduler
  -> Lambda Scheduler
  -> SQS FIFO
  -> Lambda Fetcher
  -> Wisdom Guild
  -> DynamoDB

React SPA
  -> CloudFront / S3
  -> API Gateway
  -> Lambda API
  -> DynamoDB
```

## Directory

```text
.
├── backend/lambda/
│   ├── api/
│   ├── fetcher/
│   └── scheduler/
├── frontend/
│   └── src/
├── infra/
│   ├── environments/dev/
│   └── modules/
│       ├── compute/
│       ├── frontend_hosting/
│       └── storage/
├── docs/
├── CLAUDE.md
└── REMINDER.md
```

## Deploy

`terraform apply` だけではアプリ公開まで完結しません。

Terraformで作成するのはAWSインフラまでです。React SPAのビルド、S3へのアップロード、CloudFront invalidation、カードマスタ投入は別作業です。

### 1. Infrastructure

```bash
cd /home/tokium/Git/MyProject/mtg-price-tracker/infra/environments/dev
terraform init -reconfigure
terraform plan
terraform apply
```

apply 後に Terraform output で以下を確認します。

- API endpoint
- frontend S3 bucket
- CloudFront distribution ID/domain

### 2. Frontend

`frontend/.env.production` の `VITE_API_BASE_URL` を最新の API endpoint に合わせます。

```bash
cd /home/tokium/Git/MyProject/mtg-price-tracker/frontend
npm install
npm run build
aws s3 sync dist/ s3://<frontend_bucket>/ --delete --profile myenv
aws cloudfront create-invalidation --distribution-id <distribution_id> --paths '/*' --profile myenv
```

### 3. Initial Data

定時取得は `mtg-cards` に登録済み、かつ `cache_mode = scheduled` のカードだけを対象にします。

そのため、`mtg-cards` が空の場合は EventBridge Scheduler が動いても取得対象は0件です。

Scryfall Bulk Data からカードマスタを投入するには、まずdry-runで内容を確認します。

```bash
cd /home/tokium/Git/MyProject/mtg-price-tracker
python3 scripts/import_scryfall_cards.py --download --dry-run
```

dev環境へ少数カードだけ投入して確認する場合:

```bash
python3 scripts/import_scryfall_cards.py \
  --download \
  --limit 100 \
  --table-name mtg-cards \
  --profile myenv \
  --region ap-northeast-1
```

全件投入する場合は `--limit` を外します。既存カードは `card_name_en` をキーにupsertされます。

## Destroy

dev 環境を停止してコストを抑える場合:

```bash
cd /home/tokium/Git/MyProject/mtg-price-tracker/infra/environments/dev
terraform destroy
```

frontend S3 bucket にオブジェクトが残っていると bucket 削除に失敗します。その場合は空にしてから再実行します。

```bash
aws s3 rm s3://<frontend_bucket> --recursive --profile myenv
terraform destroy
```

remote state bucket `mkhookah-terraform` はTerraform管理対象外として残します。

## Main Remaining Tasks

- Scryfall Bulk Data を使ったカードマスタ初期投入
- 最新収録セット発売日による `scheduled` / `lazy` 判定
- 定時取得ルートのE2E確認
- Wisdom Guildページネーション対応方針の整理
- Fetcherの無限ループ対策設計、ページ巡回を実装する場合のみ
- フロントエンドの空状態、エラー表示、モバイル表示改善
- App Store 審査を見据えたネイティブ機能検討
