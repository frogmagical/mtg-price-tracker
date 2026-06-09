# DynamoDB テーブル定義

## テーブル一覧

| テーブル名 | 用途 | 課金モード |
|---|---|---|
| `mtg-cards` | 管理対象カードのメタ情報 | オンデマンド |
| `mtg-prices` | 収集した価格データ | オンデマンド |

---

## `mtg-cards` テーブル

### キー設計

```
PK: card_name_en (String)   例: "Drown+in+Sorrow"
```

ソートキーなし（カード名は一意）。

### 属性

| 属性名 | 型 | 必須 | 説明 |
|---|---|---|---|
| `card_name_en` | S | ✓ | URLエンコード形式の英語カード名 |
| `card_name_ja` | S | | 日本語カード名 |
| `latest_set_code` | S | ✓ | 最新収録セットのコード (例: "CMM") |
| `latest_set_date` | S | ✓ | 最新収録セットの発売日 (YYYY-MM-DD) |
| `cache_mode` | S | ✓ | "scheduled" または "lazy" |
| `last_fetched_at` | S | | 最終fetch日時 (ISO8601) |
| `fetch_error_count` | N | | 連続エラー回数 |
| `fetch_status` | S | | "ok" / "error" / "not_found" / "pending" |
| `registered_at` | S | ✓ | 登録日時 (ISO8601) |

### GSI（グローバルセカンダリインデックス）

**`cache_mode-index`**
- PK: `cache_mode`
- SK: `last_fetched_at`
- 用途: Schedulerが `cache_mode = "scheduled"` のカードを全件取得するため

---

## `mtg-prices` テーブル

### キー設計

```
PK: card_name_en (String)   例: "Drown+in+Sorrow"
SK: price_id     (String)   例: "晴れる屋#BNG#JPN#NM#foil"
```

price_id の構成: `{shop}#{set_code}#{language}#{condition}#{flag}`
- flag: "normal" / "foil" / "promo" / "played" / "foil_promo" など

### 属性

| 属性名 | 型 | 必須 | 説明 |
|---|---|---|---|
| `card_name_en` | S | ✓ | PK |
| `price_id` | S | ✓ | SK |
| `shop` | S | ✓ | ショップ名 |
| `price` | N | ✓ | 価格（円、税込） |
| `set_code` | S | | セットコード (例: "BNG", "CMM") |
| `language` | S | | 言語 ("JPN"/"ENG"/"ITA"等) |
| `stock` | N | | 在庫数（null=在庫なし） |
| `condition` | S | | カード状態 ("NM"/"EX"/"GD"等) |
| `foil` | BOOL | ✓ | FOIL版か |
| `promo` | BOOL | ✓ | プロモカードか |
| `played` | BOOL | ✓ | プレイド品か |
| `source_url` | S | | データ取得元URL |
| `fetched_at` | S | ✓ | fetch日時 (ISO8601) |
| `updated_at` | S | | WG記載の最終更新日時 |
| `TTL` | N | ✓ | Unix timestamp（自動削除用） |

### TTL設定

```python
from datetime import datetime, timedelta

def calc_ttl(cache_mode: str) -> int:
    hours = 48 if cache_mode == "scheduled" else 24
    return int((datetime.utcnow() + timedelta(hours=hours)).timestamp())
```

### アクセスパターン

| パターン | 操作 | 条件 |
|---|---|---|
| カードの全価格を取得 | Query | PK = card_name_en |
| 特定ショップの価格を取得 | Query + FilterExpression | PK = card_name_en, shop = "晴れる屋" |
| 在庫ありのみ取得 | Query + FilterExpression | stock > 0 |
| FOILのみ取得 | Query + FilterExpression | foil = true |
