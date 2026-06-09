# Wisdom Guild スクレイピング仕様

## 対象URL

```
https://wonder.wisdom-guild.net/price/{英語カード名}/
例: https://wonder.wisdom-guild.net/price/Drown+in+Sorrow/
```

カード名はスペースを `+` に置換したもの（URLエンコード形式）。

## 利用規約上の制約

- 1日1回のキャッシュ取得: **承諾不要・明示OK**
- ユーザー入力をリアルタイムでWGに投げるプロキシ: **禁止（要承諾）**
- 同時アクセス・高頻度アクセス: **禁止**

Lambda Fetcherのmax concurrency=5、SQS batch size=1 で遵守する。

## ページ構造（1ページ目）

ステートレスにアクセスすると価格の安い順で約19件が返る。
`?page=N` はセッション依存のため不可。1ページ目で十分。

### サマリーエリア（テーブル外）

```html
最安値: 30 円
トリム平均: 64 円
在庫（通常）: 321 枚
データ数: 25 件/ 147 件
```

### 価格テーブル（`#ptable` 以降の `<table>`）

各行の構造:

```html
<tr>
  <td><a href="/shop/{shop_id}/">{ショップ名}</a></td>
  <td><strong>{価格}</strong> 円</td>
  <td>{セットコード}</td>
  <td>{言語}</td>
  <td>{在庫数} 枚  or  なし</td>
  <td>
    <!-- FOILの場合 -->
    <img src="http://www.wisdom-guild.net/image/icon/foil.png" title="FOIL">
    <!-- プロモの場合 -->
    <img src="http://www.wisdom-guild.net/image/icon/promo.png" title="プロモーションカード">
    <!-- プレイドの場合 -->
    <img src="http://www.wisdom-guild.net/image/icon/played.png" title="プレイド">
  </td>
  <td>{状態: NM / EX / GD 等、または空}</td>
  <td><a href="/link.php?s={shop_id}&t={item_id}">売り場</a></td>
  <td>{最終更新: 26/05/20 08:51}</td>
  <td>{最終チェック: 26/06/09 08:56}</td>
</tr>
```

## パースロジック（Python / BeautifulSoup）

```python
from bs4 import BeautifulSoup
import re
from datetime import datetime

def parse_prices(html: str, card_name_en: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # 価格テーブルを特定（複数tableがあるため#ptableの後のtableを取る）
    ptable = soup.find("a", {"name": "ptable"})
    if not ptable:
        return results
    table = ptable.find_next("table")
    if not table:
        return results

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 9:
            continue

        shop_link = cells[0].find("a")
        if not shop_link:
            continue
        shop = shop_link.get_text(strip=True)

        price_tag = cells[1].find("strong")
        if not price_tag:
            continue
        try:
            price = int(price_tag.get_text(strip=True).replace(",", ""))
        except ValueError:
            continue

        set_code = cells[2].get_text(strip=True)
        language = cells[3].get_text(strip=True)

        stock_text = cells[4].get_text(strip=True)
        stock = None
        if stock_text != "なし" and stock_text != "":
            m = re.search(r"(\d+)", stock_text)
            if m:
                stock = int(m.group(1))

        icons = cells[5].find_all("img")
        icon_titles = [img.get("title", "") for img in icons]
        foil   = "FOIL" in icon_titles
        promo  = "プロモーションカード" in icon_titles
        played = "プレイド" in icon_titles

        condition = cells[6].get_text(strip=True)

        updated_at = cells[8].get_text(strip=True) if len(cells) > 8 else ""

        # SK: ショップ・セット・言語・状態・種別の組み合わせ
        flags = []
        if foil:   flags.append("foil")
        if promo:  flags.append("promo")
        if played: flags.append("played")
        flag_str = "_".join(flags) if flags else "normal"
        price_id = f"{shop}#{set_code}#{language}#{condition}#{flag_str}"

        results.append({
            "card_name_en": card_name_en,
            "price_id": price_id,
            "shop": shop,
            "price": price,
            "set_code": set_code,
            "language": language,
            "stock": stock,
            "condition": condition,
            "foil": foil,
            "promo": promo,
            "played": played,
            "source_url": source_url,
            "updated_at": updated_at,
            "fetched_at": datetime.utcnow().isoformat(),
        })

    return results
```

## 収録セット一覧エリア

カードデータページ (`whisper.wisdom-guild.net/card/{name}/`) の
「再録」フィールドからセットコードを取得することで `latest_set_date` を
確定できる。ただし初期はScryfallで代替可能（後述）。

## エラーハンドリング

- 404: カードが存在しない → `cards.fetch_status = "not_found"` として記録
- 接続タイムアウト: `fetch_error_count` をインクリメント、3回超でアラート
- 価格テーブルが空: 在庫なし状態として保存（pricesレコードを削除しない）
