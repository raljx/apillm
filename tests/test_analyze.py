import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.menu_merger import merge_menu_payloads


def payload(dish, date="2026-08-27"):
    return {
        "etablissement_id": "ecole",
        "periode": "Août 2026",
        "jours": [{
            "date": date,
            "jour_semaine": "jeudi",
            "theme": None,
            "ferie": False,
            "tranche_age": {"petits": {
                "repas": {"dejeuner": {
                    "elements": [{"type": "entree", "contenu": [dish]}],
                    "commentaires": None,
                }},
                "allergenes": [],
                "regimes_specifiques": {},
            }},
        }],
    }


def response(data):
    return SimpleNamespace(output_text=json.dumps(data), model="test-model")


class AnalyzeFilesTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict("os.environ", {
            "AZURE_OPENAI_ENDPOINT": "https://example.invalid/openai/v1/responses",
            "AZURE_OPENAI_API_KEY": "synthetic-test-key",
            "AZURE_OPENAI_DEPLOYMENT": "test-model",
        })
        env.start()
        self.addCleanup(env.stop)
        sdk = patch("app.services.llm_client.OpenAI")
        self.create_response = sdk.start().return_value.responses.create
        self.addCleanup(sdk.stop)
        self.http = TestClient(app)
        self.addCleanup(self.http.close)

    def upload(self, count=3):
        return self.http.post("/api/v1/analyze", files=[
            ("files", (f"menu_{index}.csv", f"plat\nPlat {index}\n", "text/csv"))
            for index in range(count)
        ])

    def test_waits_for_every_response_before_merging_and_returning_json(self):
        last_started = Event()
        release_last = Event()
        returned_payloads = [payload("Carottes"), payload("Carottes"), payload("Betteraves")]
        completed = []

        def complete(**kwargs):
            index = len(completed)
            self.assertIn(f"menu_{index}.csv", kwargs["input"])
            self.assertNotIn(f"menu_{(index + 1) % 3}.csv", kwargs["input"])
            if index == 2:
                last_started.set()
                if not release_last.wait(timeout=10):
                    raise TimeoutError("Test did not release final LLM response")
            completed.append(index)
            return response(returned_payloads[index])

        def merge_after_all(payloads):
            self.assertEqual(completed, [0, 1, 2])
            self.assertEqual(payloads, returned_payloads)
            return merge_menu_payloads(payloads)

        self.create_response.side_effect = complete
        with patch("app.services.llm_client.merge_menu_payloads", side_effect=merge_after_all) as merge:
            with ThreadPoolExecutor(max_workers=1) as pool:
                request = pool.submit(self.upload)
                try:
                    self.assertTrue(last_started.wait(timeout=10))
                    self.assertFalse(request.done())
                    merge.assert_not_called()
                finally:
                    release_last.set()
                result = request.result(timeout=10)
            merge.assert_called_once()

        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["successful_files"], 3)
        self.assertEqual(body["failed_files"], 0)
        self.assertEqual(body["model"], "test-model")
        self.assertIsInstance(body["analysis"], dict)
        days = body["analysis"]["jours"]
        self.assertEqual(len(days), 1)
        elements = days[0]["tranche_age"]["petits"]["repas"]["dejeuner"]["elements"]
        self.assertEqual(elements, [{"type": "entree", "contenu": ["Carottes", "Betteraves"]}])

    def test_no_partial_menu_when_a_later_llm_call_fails(self):
        failures = [
            RuntimeError("Synthetic provider failure"),
            SimpleNamespace(output_text="invalid JSON"),
            response([]),
            response({"jours": "invalid"}),
        ]
        for failure in failures:
            with self.subTest(failure=repr(failure)):
                self.create_response.reset_mock()
                self.create_response.side_effect = [response(payload("Carottes")), failure]
                result = self.upload(count=2)
                self.assertEqual(result.status_code, 502)
                self.assertNotIn("analysis", result.json())
                self.assertEqual(self.create_response.call_count, 2)

    def test_single_file_returns_structured_analysis(self):
        self.create_response.return_value = response(payload("Carottes"))
        result = self.upload(count=1)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["analysis"], payload("Carottes"))
        self.create_response.assert_called_once()


if __name__ == "__main__":
    unittest.main()
