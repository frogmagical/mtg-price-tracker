# AWS アーキテクチャ詳細

## リージョン

`ap-northeast-1`（東京）固定。

## コンポーネント一覧

### 収集レイヤー

| サービス | リソース名 | 設定 |
|---|---|---|
| EventBridge Scheduler | `mtg-daily-scheduler` | cron(0 2 * * ? *)  JST 11:00 |
| Lambda | `mtg-scheduler` | Python 3.12, 128MB, timeout 60s |
| SQS FIFO | `mtg-fetch-queue.fifo` | visibility timeout 300s, DLQ付き |
| Lambda | `mtg-fetcher` | Python 3.12, 256MB, timeout 30s, concurrency 5 |
| SQS DLQ | `mtg-fetch-dlq.fifo` | 3回失敗でDLQ送り |

### 配信レイヤー

| サービス | リソース名 | 設定 |
|---|---|---|
| S3 | `mtg-price-frontend-{account_id}` | 静的ウェブサイトホスティング |
| CloudFront | `mtg-price-cdn` | S3オリジン, HTTPS強制 |
| API Gateway | `mtg-price-api` | HTTP API (REST APIより70%安い) |
| Lambda | `mtg-api` | Python 3.12, 256MB, timeout 30s |

### ストレージ

| サービス | テーブル名 | 課金 |
|---|---|---|
| DynamoDB | `mtg-cards` | オンデマンド + TTL有効 |
| DynamoDB | `mtg-prices` | オンデマンド + TTL有効 |

## API エンドポイント設計

```
GET /prices/{cardNameEn}
  → カードの全価格リストを返す
  → キャッシュなし or TTL切れの場合はWGから即時fetch（lazyモード）

GET /cards
  → 管理対象カード一覧（検索・オートコンプリート用）

POST /cards
  → カードを管理対象に追加
  → Scryfallから latest_set_date を自動取得して cache_mode を決定

DELETE /cards/{cardNameEn}
  → 管理対象から削除
```

## IAM ポリシー方針

各Lambdaに最小権限を付与する。

**mtg-scheduler:**
- `dynamodb:Query` on mtg-cards (cache_mode-index)
- `sqs:SendMessage` on mtg-fetch-queue.fifo

**mtg-fetcher:**
- `sqs:ReceiveMessage`, `sqs:DeleteMessage` on mtg-fetch-queue.fifo
- `dynamodb:PutItem`, `dynamodb:UpdateItem` on mtg-prices
- `dynamodb:UpdateItem` on mtg-cards (last_fetched_at, fetch_error_count更新)

**mtg-api:**
- `dynamodb:Query` on mtg-prices
- `dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:Scan`, `dynamodb:PutItem`, `dynamodb:DeleteItem`, `dynamodb:UpdateItem` on mtg-cards
- `lambda:InvokeFunction` on mtg-fetcher (lazyモード・陳腐化データの同期呼び出し)

## デプロイ方法

```bash
# インフラ
cd infra/
terraform init
terraform plan
terraform apply

# Lambda デプロイ（各関数）
cd backend/lambda/fetcher/
pip install -r requirements.txt -t ./package/
cd package && zip -r ../function.zip . && cd ..
zip -g function.zip handler.py parser.py
aws lambda update-function-code \
  --function-name mtg-fetcher \
  --zip-file fileb://function.zip

# フロントエンド
cd frontend/
npm run build
aws s3 sync dist/ s3://mtg-price-frontend-{account_id}/
aws cloudfront create-invalidation --distribution-id {id} --paths "/*"
```
