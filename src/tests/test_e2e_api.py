import unittest
import requests
import json
import os
import sqlite3
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"
GENERATION_ENDPOINT = f"{BASE_URL}/generate/narrative_outline"
DB_NAME = "novel_mvp.db"

class TestNarrativeApiE2E(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("======================================================================")
        print("IMPORTANT: These E2E tests require the FastAPI server to be running.")
        print(f"Please ensure the server is started (e.g., uvicorn src.api.main:app --reload)")
        print(f"and is accessible at {BASE_URL}.")
        print(f"These tests will interact with the database: '{DB_NAME}'.")
        # For CI/CD or more robust testing, manage DB state explicitly (e.g., use a test-specific DB file)
        # For this script, we assume 'novel_mvp.db' is the target for the running API.
        # It's good to clean up this DB before a test suite run if possible.
        if os.path.exists(DB_NAME):
            print(f"Attempting to clean up existing database: {DB_NAME}")
            # Best effort to delete. If server is using it, this might fail.
            # Ideally, server should use a configurable DB path for testing.
            try:
                os.remove(DB_NAME)
                print(f"Removed existing {DB_NAME} for a cleaner test run.")
            except OSError as e:
                print(f"Could not remove {DB_NAME} (may be in use or permission issue): {e}")
                print("Tests will proceed with the existing database.")
        else:
            print(f"{DB_NAME} does not exist, will be created by the API.")
        print("======================================================================")


    def _verify_db_record(self, narrative_id: int, expected_theme: str, expect_worldview: bool = True) -> bool:
        """Helper to verify a record in the database. Now also checks worldview."""
        if narrative_id is None:
            print("DB Verify: Narrative ID is None, skipping DB check.")
            return False
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            # Updated query to include generated_worldview
            cursor.execute("SELECT user_theme, generated_outline, generated_worldview FROM narratives WHERE id = ?", (narrative_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                db_theme, db_outline, db_worldview = row
                self.assertEqual(db_theme, expected_theme, "Theme mismatch in DB.")
                self.assertTrue(db_outline, "Outline is empty in DB.")
                if expect_worldview:
                    self.assertIsNotNone(db_worldview, "Worldview is None in DB when it was expected.")
                    self.assertTrue(len(db_worldview) > 0, "Worldview is empty in DB when it was expected.")
                else:
                    self.assertIsNone(db_worldview, "Worldview is present in DB when it was NOT expected.")
                print(f"DB Verify: Record ID {narrative_id} verified successfully (Worldview expected: {expect_worldview}).")
                return True
            else:
                print(f"DB Verify: No record found for ID {narrative_id}.")
                return False
        except sqlite3.Error as e:
            print(f"DB Verify: Database verification error for ID {narrative_id}: {e}")
            return False
        except AssertionError as ae:
            print(f"DB Verify: Assertion error during verification for ID {narrative_id}: {ae}")
            return False # Or re-raise if test should hard fail here

    def test_1_generate_narrative_success_with_worldview(self): # Renamed for clarity
        """Test successful narrative and worldview generation and persistence."""
        payload = {
            "theme": "A city where music is forbidden, and a young rebel rediscovers it",
            "style_preferences": "dystopian, hopeful, YA"
        }
        print(f"\n[TEST] test_1_generate_narrative_success_with_worldview: Sending payload: {payload}")

        try:
            response = requests.post(GENERATION_ENDPOINT, json=payload, timeout=90) # Longer timeout
        except requests.exceptions.ConnectionError:
            self.fail(f"Connection Error: Could not connect to API at {GENERATION_ENDPOINT}. Server running?")
            return

        self.assertEqual(response.status_code, 200, f"Response: {response.text}")
        data = response.json()
        print(f"[TEST] ...success_with_worldview: Received response data: {data}")

        self.assertIsNone(data.get("error_message"), f"API returned error: {data.get('error_message')}")
        self.assertIsNotNone(data.get("narrative_id"))
        self.assertIsInstance(data.get("narrative_id"), int)
        self.assertIsNotNone(data.get("narrative_outline"))
        self.assertTrue(len(data.get("narrative_outline", "")) > 0)

        # Assertions for worldview_data
        self.assertIsNotNone(data.get("worldview_data"), "worldview_data is missing from API response.")
        self.assertIsInstance(data.get("worldview_data"), str, "worldview_data should be a string.")
        self.assertTrue(len(data.get("worldview_data", "")) > 0, "worldview_data is empty in API response.")

        self.assertIsNotNone(data.get("history"))
        self.assertTrue(len(data.get("history", [])) > 0)

        narrative_id = data.get("narrative_id")
        self.assertTrue(
            self._verify_db_record(narrative_id, payload["theme"], expect_worldview=True),
            f"Database verification failed for narrative ID: {narrative_id}"
        )
        print(f"[TEST] ...success_with_worldview: DB verification successful for ID {narrative_id}.")

    def test_2_generate_narrative_missing_theme(self):
        """Test narrative generation with missing theme (expecting an error message)."""
        # This test remains largely the same, as worldview generation shouldn't be reached.
        payload = {"style_preferences": "sci-fi"}
        print(f"\n[TEST] test_2_generate_narrative_missing_theme: Sending payload: {payload}")

        try:
            response = requests.post(GENERATION_ENDPOINT, json=payload, timeout=10)
        except requests.exceptions.ConnectionError:
            self.fail(f"Connection Error: Could not connect to API at {GENERATION_ENDPOINT}. Server running?")
            return

        self.assertEqual(response.status_code, 200, f"Response: {response.text}")
        data = response.json()
        print(f"[TEST] ...missing_theme: Received response data: {data}")

        self.assertIsNotNone(data.get("error_message"))
        # Check for Pydantic v1 or v2 style error message for missing field
        error_msg = data.get("error_message", "")
        is_pydantic_v1_error = "field required" in error_msg.lower() and "body -> theme" in error_msg.lower()
        # Pydantic V2 can raise a different error if the payload doesn't match the model at all (e.g. if theme is the ONLY field)
        # A more robust check for Pydantic V2 might involve checking for a 422 status if strict parsing in API leads to it,
        # but here we assume the current API setup returns 200 with error in body.
        is_pydantic_v2_error = "Input should be a valid dictionary or instance of NarrativeRequestPayload" in error_msg
        is_workflow_error = "User input with 'theme' is required" in error_msg # Error from workflow node

        self.assertTrue(is_pydantic_v1_error or is_pydantic_v2_error or is_workflow_error, f"Unexpected error message: {error_msg}")

        self.assertIsNone(data.get("narrative_id"))
        self.assertIsNone(data.get("narrative_outline"))
        self.assertIsNone(data.get("worldview_data")) # Should also be None here
        self.assertIsNotNone(data.get("history"))

if __name__ == "__main__":
    print("Running E2E API tests. Ensure the FastAPI server (uvicorn src.api.main:app --reload) is running.")
    unittest.main()
