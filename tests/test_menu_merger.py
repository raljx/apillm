import json
import unittest
from copy import deepcopy

from app.services.menu_merger import merge_menu_payloads


class MenuMergerTests(unittest.TestCase):
    def test_deduplication_keeps_distinct_comments_and_separate_menus(self):
        age = {
            "repas": {"dejeuner": {
                "elements": [{"type": "dessert", "contenu": ["Pomme", "Pomme"]}],
                "commentaires": "Sans sel",
            }},
        }
        day = {
            "date": "2026-08-27",
            "tranche_age": {"petits": deepcopy(age), "moyens": deepcopy(age)},
        }
        next_day = deepcopy(day)
        next_day["date"] = "2026-08-28"
        first = {"jours": [day, next_day]}
        second = deepcopy(first)
        second["jours"][0]["tranche_age"]["petits"]["repas"]["dejeuner"]["commentaires"] = "Texture mixée"

        result = merge_menu_payloads([first, second, first, second])

        self.assertEqual(len(result["jours"]), 2)
        for merged_day in result["jours"]:
            self.assertEqual(set(merged_day["tranche_age"]), {"petits", "moyens"})
            for age_key, merged_age in merged_day["tranche_age"].items():
                meal = merged_age["repas"]["dejeuner"]
                self.assertEqual(meal["elements"], [{"type": "dessert", "contenu": ["Pomme"]}])
                expected_comment = (
                    "Sans sel | Texture mixée"
                    if merged_day["date"] == "2026-08-27" and age_key == "petits"
                    else "Sans sel"
                )
                self.assertEqual(meal["commentaires"], expected_comment)

    def test_deduplicates_meals_and_metadata_without_mutating_inputs(self):
        first = {
            "periode": "Août 2026",
            "jours": [{
                "date": "2026-08-27", "theme": "Local",
                "tranche_age": {"petits": {
                    "repas": {"gouter": {
                        "elements": [
                            {"type": "gouter", "contenu": ["Pomme", "Pomme"]},
                            {"type": "gouter", "contenu": ["Pain"]},
                        ],
                        "commentaires": "Sans sel",
                    }},
                    "allergenes": ["gluten"],
                    "regimes_specifiques": {"bio": True},
                }},
            }],
        }
        second = deepcopy(first)
        second["periode"] = "Septembre 2026"
        second["jours"][0]["theme"] = "Bio"
        inputs = [first, second, first]
        original = deepcopy(inputs)

        result = merge_menu_payloads(inputs)

        self.assertEqual(inputs, original)
        self.assertEqual(result["periode"], "Août 2026 | Septembre 2026")
        day = result["jours"][0]
        self.assertEqual(day["theme"], "Local | Bio")
        age = day["tranche_age"]["petits"]
        self.assertEqual(age["allergenes"], ["gluten"])
        self.assertTrue(age["regimes_specifiques"]["bio"])
        meal = age["repas"]["gouter"]
        self.assertEqual(meal["elements"], [{
            "type": "gouter",
            "contenu": ["Pomme", "Pain"],
        }])
        self.assertEqual(meal["commentaires"], "Sans sel")
        meal["elements"][0]["contenu"].append("Lait")
        self.assertEqual(inputs, original)

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
