import json
import unittest

from app.services.menu_merger import merge_menu_payloads


class MenuMergerTests(unittest.TestCase):
    def test_groups_dates_and_merges_duplicate_age(self):
        first = {
            "etablissement_id": "creche",
            "periode": "Août 2026",
            "jours": [{
                "date": "2026-08-27", "jour_semaine": "jeudi", "theme": None,
                "ferie": False,
                "tranche_age": {"petits": {
                    "repas": {"dejeuner": {"elements": [
                        {"type": "entree", "contenu": ["Carottes"]}
                    ], "commentaires": "Sans sel"}},
                    "allergenes": ["lait"],
                    "regimes_specifiques": {"bio": False, "porc": False},
                }},
            }],
        }
        second = {
            "jours": [{
                "date": "2026-08-27", "jour_semaine": "jeudi", "theme": None,
                "ferie": False,
                "tranche_age": {
                    "petits": {
                        "repas": {"dejeuner": {"elements": [
                            {"type": "entree", "contenu": ["Carottes", "Betteraves"]},
                            {"type": "dessert", "contenu": ["Pomme"]},
                        ], "commentaires": "Texture mixée"}},
                        "allergenes": ["arachide", "lait"],
                        "regimes_specifiques": {"bio": True, "porc": False},
                    },
                    "moyens": {"repas": {}, "allergenes": [], "regimes_specifiques": {}},
                },
            }, {
                "date": "2026-08-28", "jour_semaine": "vendredi", "theme": None,
                "ferie": False,
                "tranche_age": {"moyens": {"repas": {}, "allergenes": [], "regimes_specifiques": {}}},
            }],
        }

        result = merge_menu_payloads([first, second])

        self.assertEqual([day["date"] for day in result["jours"]], ["2026-08-27", "2026-08-28"])
        petits = result["jours"][0]["tranche_age"]["petits"]
        self.assertEqual(petits["allergenes"], ["lait", "arachide"])
        self.assertTrue(petits["regimes_specifiques"]["bio"])
        self.assertEqual(
            petits["repas"]["dejeuner"]["elements"][0]["contenu"],
            ["Carottes", "Betteraves"],
        )
        self.assertEqual(
            petits["repas"]["dejeuner"]["commentaires"],
            "Sans sel | Texture mixée",
        )
        self.assertIn("moyens", result["jours"][0]["tranche_age"])

    def test_result_is_compact_json(self):
        result = merge_menu_payloads([{"jours": []}])
        compact = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
        self.assertNotIn("\n", compact)
        self.assertEqual(json.loads(compact), result)


if __name__ == "__main__":
    unittest.main()
