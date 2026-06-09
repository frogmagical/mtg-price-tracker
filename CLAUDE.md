# MTG Price Tracker — プロジェクト仕様書

> Claude Code はこのファイルをセッション開始時に必ず読むこと。
> ここまでの設計議論の結論をすべて記載している。コードを書く前に全体を把握すること。

---

## プロジェクト概要

MTGシングルカードの価格を複数ショップにわたって一覧表示するWebアプリ＋スマートフォンアプリ。

- データソース: **Wisdom Guild** (`wonder.wisdom-guild.net`)
- 対象ショップ: 晴れる屋・BIGWEB・Cardshop Serra・ENNDAL GAMES 他（Wisdom Guild掲載の全ショップ）
- インフラ: **AWS (ap-northeast-1)**、サーバーレス構成
- フロントエンド: **React SPA** (Web) + **Capacitor** でラップしてAppStore/GooglePlayにも配布

---

## データソースの選定経緯と制約（重要）

### なぜ晴れる屋を直接スクレイピングしないのか

晴れる屋 (`hareruyamtg.com`) の検索結果はXHRで動的ロードされるSPAのため、
サーバーサイドHTMLに結果が含まれない。個別商品ページ (`/ja/products/detail/{id}`) は
SSRだが、検索結果からIDを取得する手段がない（ブラウザ実行環境が必要）。
3万カード×7IDの21万req/日はIPブロックリスクが高く、現実的でない。

### Wisdom Guildを使う理由

Wisdom Guildは各ショップの**了承のもと**データフィードを受け取っており、
晴れる屋を含む国内主要MTG ECの価格359万件以上をすでに集約済み。

**利用規約（`https://www.wisdom-guild.net/welcome/`）の明示的許可範囲:**
- 「１日１回Wisdom Guildからカード名のリストをすべて取得し、
  それを自分で用意したデータベースに格納して利用する」→ **承諾不要・明示OK**
- 管理者に連絡すれば「開発ツールの提供が可能」とも記載あり
  （スケール時に連絡予定。連絡先: `webmaster@wisdom-guild.net`）

**禁止されていること:**
- ユーザー入力をその都度Wisdom Guildに送り結果を返すリアルタイムプロキシ
- サーバーへの著しい負荷

### Wisdom Guildのデータ取得仕様

```
URL形式: https://wonder.wisdom-guild.net/price/{英語カード名}/
例:      https://wonder.wisdom-guild.net/price/Drown+in+Sorrow/

- SSRのため、fetchで直接HTMLが取得できる（Cookieやセッション不要）
- 1ページ目はステートレスにアクセス可能（最安値順で約19件が返る）
- ?page=N はセッション依存のため、ステートレスアクセスでは機能しない
  （常に最終ページが返ってくる）
- 1ページ目で最安値〜の主要価格は取得できるため実用上は十分
```

取得できるフィールド（HTMLパース）:
- ショップ名、価格(円)、セットコード、言語、在庫数、状態(NM/EX/GD等)、
  FOIL有無、プロモ有無、プレイド有無、最終更新日時、最終チェック日時

---

## AWS アーキテクチャ

```
【収集レイヤー - 1日1回】
EventBridge Scheduler
  → Lambda: Scheduler
      → DynamoDB: cards テーブルから scheduled カードを取得
      → SQS FIFO キューにエンキュー

SQS FIFO
  → Lambda: Fetcher（コンシューマー）
      → Wisdom Guild /price/{card_name}/ をfetch
      → BeautifulSoup でHTMLパース
      → DynamoDB: prices テーブルにupsert

【配信レイヤー - リクエスト時】
React SPA（S3 + CloudFront）
  → API Gateway (HTTP API)
      → Lambda: API
          → DynamoDB: prices テーブルをクエリ
          → キャッシュなし or TTL切れなら Fetcher を同期呼び出し（都度Fetch）
          → JSON レスポンス返却 + 非同期でDB書き込み
```

### コスト概算（月額）

- 管理3万カード名・1日1回収集・APIリクエスト5,000回/日の想定
- Lambda: 無料枠内 ≈ $0
- DynamoDB: $2〜5
- SQS: 無料枠内 ≈ $0
- API Gateway (HTTP API): $0.10 以下
- S3 + CloudFront: $1 以下
- **合計: $3〜8/月**

---

## データモデル

詳細は `docs/data-model.md` を参照。

### `cards` テーブル（管理対象カードのメタ情報）

```
PK: card_name_en  (String)  例: "Drown+in+Sorrow"
Attributes:
  card_name_ja:      "悲哀まみれ"
  latest_set_code:   "CMM"
  latest_set_date:   "2023-08-04"   ← 10年判定に使用
  cache_mode:        "scheduled"    ← "scheduled" | "lazy"
  last_fetched_at:   ISO8601 timestamp
  fetch_error_count: Number
```

### `prices` テーブル（収集した価格データ）

```
PK: card_name_en  (String)  例: "Drown+in+Sorrow"
SK: price_id      (String)  例: "晴れる屋#BNG#JPN#NM#foil"
Attributes:
  shop:         String   例: "晴れる屋"
  price:        Number   例: 600
  set_code:     String   例: "BNG"
  language:     String   例: "JPN" | "ENG" | ...
  stock:        Number   (null = 在庫なし)
  condition:    String   例: "NM" | "EX" | "GD" | ...
  foil:         Boolean
  promo:        Boolean
  played:       Boolean
  source_url:   String
  fetched_at:   ISO8601 timestamp
  updated_at:   String   例: "26/05/20 08:51"  ← WG記載の更新日時
  TTL:          Number   ← scheduled: 48h, lazy: 24h (Unix timestamp)
```

---

## キャッシュ戦略（2モード）

### モード判定ロジック

```python
def get_cache_mode(latest_set_date: str) -> str:
    """
    カードの最新収録セット発売日を基準に収集モードを決定する。
    「カード名」単位ではなく「最新収録セット」単位で判定することで、
    再録により現役流通しているカードをキャッシュ対象に含める。

    例: 悲哀まみれ(初出2014年)でも統率者マスターズ(2023年)に再録されていれば scheduled
    例: Black Lotus(初出1993年、再録なし)は lazy
    """
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=365 * 10)
    release = datetime.strptime(latest_set_date, "%Y-%m-%d")
    return "scheduled" if release > cutoff else "lazy"
```

### scheduledモード（10年以内）

- Lambda: Scheduler が毎日1回、対象カード全件をSQSに積む
- Lambda: Fetcher がSQSから消費し、Wisdom Guildから取得してDBに保存
- TTL: 48時間（1日1回更新なので余裕を持たせる）

### lazyモード（10年超）

- ユーザーがAPIを叩いたとき初めてWisdom Guildへfetchする
- 結果はDynamoDBに保存（次回以降はキャッシュから返す）
- TTL: 24時間（旧カードの価格変動は少ないが古すぎるキャッシュも避ける）
- 初回アクセス時のみレスポンスが遅くなる（フロントでローディング表示）

---

## ディレクトリ構成

```
mtg-price-tracker/
├── CLAUDE.md                  ← このファイル（常に最新に保つこと）
├── docs/
│   ├── architecture.md        ← AWS構成図・詳細設計
│   ├── data-model.md          ← DynamoDBテーブル定義（詳細）
│   └── wisdom-guild.md        ← WGスクレイピング仕様・HTMLパターン
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── dynamodb.tf
│   ├── lambda.tf
│   ├── sqs.tf
│   ├── apigateway.tf
│   ├── eventbridge.tf
│   ├── s3_cloudfront.tf
│   └── iam.tf
├── backend/
│   └── lambda/
│       ├── scheduler/
│       │   ├── handler.py     ← EventBridge → SQSエンキュー
│       │   └── requirements.txt
│       ├── fetcher/
│       │   ├── handler.py     ← SQS → WGフェッチ → DynamoDB書き込み
│       │   ├── parser.py      ← Wisdom GuildのHTMLパーサー
│       │   └── requirements.txt
│       └── api/
│           ├── handler.py     ← API Gateway → DynamoDBクエリ
│           └── requirements.txt
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   ├── hooks/
    │   └── api/
    ├── capacitor.config.ts    ← iOS/Android ビルド設定
    ├── package.json
    └── vite.config.ts
```

---

## 実装上の注意事項

### Wisdom GuildのHTMLパース

`wonder.wisdom-guild.net/price/{card_name}/` から取得するHTMLの
価格テーブル構造については `docs/wisdom-guild.md` を参照。
BeautifulSoupで `<table>` 内の `<tr>` を走査する。

FOILはimgタグ `<img src=".../icon/foil.png">` の有無で判定。
プロモは `<img src=".../icon/promo.png">`、プレイドは `<img src=".../icon/played.png">`。

在庫「なし」は文字列 "なし" で表示される。数字のみの場合が在庫あり。

### SQSのレート制御

Wisdom Guildへの負荷を抑えるため、Lambda Fetcherの同時実行数を制限する。
SQSのバッチサイズ=1、最大同時実行数=5 を基本設定とする。
（1秒に最大5リクエスト程度。3万件なら約1.7時間で完了）

### AppStore審査対策

WebViewベースのアプリ（Capacitor）はAppStoreで「Webと同内容」として
却下されるリスクがある。以下のネイティブ機能を最低1つ実装すること:
- プッシュ通知（ウォッチリストカードの価格変動通知）← 推奨
- ウォッチリスト（端末ローカル保存）

### Terraform

`ap-northeast-1` リージョンを前提。
Lambda関数はZIPデプロイ（Dockerイメージは不要）。
環境変数 `DYNAMODB_CARDS_TABLE`、`DYNAMODB_PRICES_TABLE`、`SQS_QUEUE_URL` を
各Lambda関数に渡すこと。

---

## 実装優先順位

1. `infra/` — Terraform でDynamoDB・SQS・Lambda・API Gateway・S3/CloudFrontを定義
2. `backend/lambda/fetcher/` — WGパーサーとDynamoDB書き込みのコア実装
3. `backend/lambda/api/` — クエリエンドポイント（2モード対応）
4. `backend/lambda/scheduler/` — EventBridge→SQSエンキュー
5. `frontend/` — React SPA、価格一覧UI
6. Capacitorでラップ → AppStore/GooglePlay配布

---

## 未解決事項・将来対応

- [ ] Wisdom Guild管理者への連絡（スケール後。開発ツール提供の申し出あり）
- [ ] ページネーション対応（WGの?page=Nはセッション依存。管理者連絡で解決見込み）
- [ ] カードリスト初期投入（Scryfall APIから全カード名+最新セット日付を取得する方針）
- [ ] プッシュ通知実装（AppStore審査対策を兼ねる）
