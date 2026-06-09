import re
from datetime import datetime, timezone
from html.parser import HTMLParser


class WisdomGuildPriceTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.seen_price_anchor = False
        self.in_price_table = False
        self.table_depth = 0
        self.finished = False
        self.rows = []
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        if self.finished:
            return

        attr_map = dict(attrs)
        if tag == "a" and attr_map.get("name") == "ptable":
            self.seen_price_anchor = True
            return

        if (
            tag == "table"
            and self.seen_price_anchor
            and "table-main" in attr_map.get("class", "").split()
        ):
            self.in_price_table = True
            self.table_depth += 1
            return

        if not self.in_price_table:
            return

        if tag == "table":
            self.table_depth += 1
        elif tag == "tr":
            self.current_row = []
        elif tag == "td":
            self.current_cell = {"text": [], "icons": []}
        elif tag == "img" and self.current_cell is not None:
            icon = " ".join(
                value
                for key, value in attr_map.items()
                if key in {"title", "alt", "src"} and value
            )
            self.current_cell["icons"].append(icon)

    def handle_endtag(self, tag):
        if self.finished or not self.in_price_table:
            return

        if tag == "td" and self.current_cell is not None and self.current_row is not None:
            self.current_cell["text"] = _normalize_text("".join(self.current_cell["text"]))
            self.current_row.append(self.current_cell)
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_price_table = False
                self.finished = True

    def handle_data(self, data):
        if self.in_price_table and self.current_cell is not None:
            self.current_cell["text"].append(data)


def parse_prices(html: str, card_name_en: str, source_url: str) -> list[dict]:
    parser = WisdomGuildPriceTableParser()
    parser.feed(html)

    results = []
    for cells in parser.rows:
        if len(cells) < 9:
            continue

        shop = cells[0]["text"]
        if not shop:
            continue

        price_match = re.search(r"(\d[\d,]*)", cells[1]["text"])
        if not price_match:
            continue
        price = int(price_match.group(1).replace(",", ""))

        set_code = cells[2]["text"]
        language = cells[3]["text"]

        stock_text = cells[4]["text"]
        stock = None
        if stock_text not in {"なし", ""}:
            stock_match = re.search(r"(\d+)", stock_text)
            if stock_match:
                stock = int(stock_match.group(1))

        icon_text = " ".join(cells[5]["icons"])
        foil = "FOIL" in icon_text or "foil" in icon_text
        promo = "プロモーションカード" in icon_text or "promo" in icon_text
        played = "プレイド" in icon_text or "played" in icon_text

        condition = cells[6]["text"]
        updated_at = cells[8]["text"]

        flags = []
        if foil:
            flags.append("foil")
        if promo:
            flags.append("promo")
        if played:
            flags.append("played")
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
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })

    return results


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
