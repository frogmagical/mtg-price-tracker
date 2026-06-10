import unittest
from datetime import date

from scripts.import_scryfall_cards import (
    build_card_master,
    get_cache_mode,
    to_dynamodb_item,
    to_wisdom_card_key,
)


class ImportScryfallCardsTest(unittest.TestCase):
    def test_build_card_master_uses_latest_paper_printing_by_oracle_id(self):
        cards = [
            {
                "oracle_id": "oracle-drown",
                "name": "Drown in Sorrow",
                "released_at": "2014-02-07",
                "set": "bng",
                "games": ["paper"],
                "digital": False,
                "lang": "en",
                "set_type": "expansion",
            },
            {
                "oracle_id": "oracle-drown",
                "name": "Drown in Sorrow",
                "released_at": "2023-08-04",
                "set": "cmm",
                "games": ["paper"],
                "digital": False,
                "lang": "en",
                "set_type": "commander",
            },
            {
                "oracle_id": "oracle-drown",
                "name": "Drown in Sorrow",
                "printed_name": "悲哀まみれ",
                "released_at": "2023-08-04",
                "set": "cmm",
                "games": ["paper"],
                "digital": False,
                "lang": "ja",
                "set_type": "commander",
            },
        ]

        master = build_card_master(cards, today=date(2026, 6, 10))

        self.assertEqual(len(master), 1)
        card = master["oracle-drown"]
        self.assertEqual(card.card_name_en, "Drown+in+Sorrow")
        self.assertEqual(card.card_name_ja, "悲哀まみれ")
        self.assertEqual(card.latest_set_code, "CMM")
        self.assertEqual(card.latest_set_date, date(2023, 8, 4))

    def test_build_card_master_filters_non_paper_and_extras_by_default(self):
        cards = [
            {
                "oracle_id": "paper",
                "name": "Lightning Bolt",
                "released_at": "2024-01-01",
                "set": "clu",
                "games": ["paper"],
                "digital": False,
                "lang": "en",
                "set_type": "expansion",
            },
            {
                "oracle_id": "digital",
                "name": "Digital Card",
                "released_at": "2024-01-01",
                "set": "ymid",
                "games": ["arena"],
                "digital": True,
                "lang": "en",
                "set_type": "alchemy",
            },
            {
                "oracle_id": "token",
                "name": "Treasure Token",
                "released_at": "2024-01-01",
                "set": "otj",
                "games": ["paper"],
                "digital": False,
                "lang": "en",
                "set_type": "token",
            },
        ]

        master = build_card_master(cards, today=date(2026, 6, 10))

        self.assertEqual(set(master.keys()), {"paper"})

    def test_cache_mode_uses_latest_set_date_cutoff(self):
        today = date(2026, 6, 10)

        self.assertEqual(get_cache_mode(date(2023, 8, 4), today=today), "scheduled")
        self.assertEqual(get_cache_mode(date(1993, 8, 5), today=today), "lazy")

    def test_to_dynamodb_item_shape(self):
        master = build_card_master(
            [
                {
                    "oracle_id": "black-lotus",
                    "name": "Black Lotus",
                    "released_at": "1993-08-05",
                    "set": "lea",
                    "games": ["paper"],
                    "digital": False,
                    "lang": "en",
                    "set_type": "core",
                }
            ],
            today=date(2026, 6, 10),
        )

        item = to_dynamodb_item(
            master["black-lotus"],
            imported_at="2026-06-10T00:00:00+00:00",
            today=date(2026, 6, 10),
        )

        self.assertEqual(item["card_name_en"], "Black+Lotus")
        self.assertEqual(item["latest_set_code"], "LEA")
        self.assertEqual(item["latest_set_date"], "1993-08-05")
        self.assertEqual(item["cache_mode"], "lazy")
        self.assertEqual(item["fetch_status"], "pending")
        self.assertEqual(item["fetch_error_count"], 0)

    def test_to_wisdom_card_key_normalizes_spaces(self):
        self.assertEqual(to_wisdom_card_key(" Drown   in Sorrow "), "Drown+in+Sorrow")


if __name__ == "__main__":
    unittest.main()
