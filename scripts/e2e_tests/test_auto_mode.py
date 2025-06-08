import sys
import os
import time # For potential cleanup delays or waits if needed in future
import unittest

# Add scripts directory to path to import common
# This assumes the script is run from the root of the project or `scripts/e2e_tests`
# For more robust path handling, consider using absolute paths or a proper test runner setup
current_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.dirname(current_dir) # This should be 'scripts/'
project_root = os.path.dirname(scripts_dir) # This should be the project root
sys.path.insert(0, project_root) # Add project root to allow `from src...`
sys.path.insert(0, scripts_dir) # Add scripts dir to find `common`

from e2e_tests.common import post_api, poll_status, count_db_records, query_db, DB_PATH # type: ignore

class TestAutoModeE2E(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n======================================================================")
        print("IMPORTANT: These E2E tests require the FastAPI server to be running.")
        print(f"Please ensure the server is started (e.g., uvicorn src.api.main:app --reload)")
        print(f"and is accessible at http://localhost:8000.")
        print(f"These tests will interact with the database: '{DB_PATH}'.")
        # Optional: Clean up DB before test suite run
        # if os.path.exists(DB_PATH):
        #     print(f"Attempting to clean up existing database: {DB_PATH}")
        #     try:
        #         os.remove(DB_PATH)
        #         print(f"Removed existing {DB_PATH} for a cleaner test run.")
        #     except OSError as e:
        #         print(f"Could not remove {DB_PATH} (may be in use or permission issue): {e}")
        print("======================================================================")
        time.sleep(2) # Give a moment for user to read, or server to fully start if run concurrently

    def test_auto_mode_full_run_am1(self):
        print("\n--- Running E2E Test: Auto-Mode Full Successful Run (AM-1) ---")

        novel_payload = {
            "theme": "A space explorer discovers a sentient plant on a remote planet.",
            "style_preferences": "Hard sci-fi, sense of wonder",
            "chapters": 2,
            "words_per_chapter": 150,
            "mode": "auto" # Ensure this matches the API's expected value for auto_mode
        }

        print(f"Starting novel generation with payload: {novel_payload}")
        start_response = post_api("/novels/", novel_payload)
        novel_id = start_response.get("novel_id")
        print(f"Novel generation task started. Novel ID: {novel_id}, Initial API Status: {start_response.get('status')}")

        self.assertIsNotNone(novel_id, "Novel ID not received from /novels/ endpoint")
        self.assertEqual(start_response.get("status"), "pending", f"Initial status was not 'pending', got: {start_response.get('status')}")

        # Poll for completion
        # Increased timeout for full workflow, even with fewer chapters/words
        final_status_data = poll_status(novel_id, expected_final_status="completed", timeout_secs=600, poll_interval_secs=15)
        self.assertEqual(final_status_data.get("status"), "completed", f"Final status not 'completed'. Full status data: {final_status_data}")

        # Database Verifications
        print(f"Verifying database records for novel_id {novel_id}...")

        novel_record_rows = query_db("SELECT * FROM novels WHERE id = ?", (novel_id,))
        self.assertEqual(len(novel_record_rows), 1, "Novel record not found in DB")
        novel_record = novel_record_rows[0]

        self.assertEqual(novel_record["workflow_status"], "completed", f"Novel status in DB not 'completed', got: {novel_record['workflow_status']}")

        self.assertIsNotNone(novel_record["active_outline_id"], "Active outline ID not set in DB")
        self.assertIsNotNone(novel_record["active_worldview_id"], "Active worldview ID not set in DB")
        self.assertIsNotNone(novel_record["active_plot_id"], "Active plot ID not set in DB")

        outline_count = count_db_records("outlines", "novel_id", novel_id)
        self.assertGreaterEqual(outline_count, 1, f"Expected at least 1 outline, found {outline_count}")

        worldview_count = count_db_records("worldviews", "novel_id", novel_id)
        self.assertGreaterEqual(worldview_count, 1, f"Expected at least 1 worldview, found {worldview_count}")

        plot_count = count_db_records("plots", "novel_id", novel_id)
        self.assertGreaterEqual(plot_count, 1, f"Expected at least 1 plot, found {plot_count}")

        character_count = count_db_records("characters", "novel_id", novel_id)
        self.assertGreater(character_count, 0, f"Expected at least 1 character, found {character_count}")

        chapter_count = count_db_records("chapters", "novel_id", novel_id)
        self.assertEqual(chapter_count, novel_payload["chapters"], f"Expected {novel_payload['chapters']} chapters, found {chapter_count}")

        kb_entry_count = count_db_records("knowledge_base_entries", "novel_id", novel_id)
        # Expected KB entries: outline, worldview, plot (summary of all chapters), N chars, M chapters (content + summary)
        # This is a loose check; exact count depends on agent behavior (e.g. how many distinct KB entries are made from plot details)
        min_expected_kb_entries = 1 + 1 + 1 + character_count + chapter_count
        self.assertGreaterEqual(kb_entry_count, min_expected_kb_entries,
                                f"Expected at least {min_expected_kb_entries} KB entries (outline, worldview, plot, chars, chapters), found {kb_entry_count}")

        print(f"Database verifications passed for novel_id {novel_id}.")
        print("--- E2E Test AM-1 Completed Successfully ---")

    def test_auto_mode_conflict_path_am3(self):
        print("\n--- Running E2E Test: Auto-Mode Conflict Detection/Resolution Path (AM-3) ---")

        # Theme designed to potentially introduce mild, detectable inconsistencies or need for KB lookup
        novel_payload = {
            "theme": "A historian discovers an ancient map detailing a lost city that supposedly vanished due to a magical cataclysm. His notes say the city was coastal, but the map places it deep in a mountain range. He decides to investigate the mountains.",
            "style_preferences": "Adventure mystery with elements of ancient lore.",
            "chapters": 1, # Keep low for faster test, focus on first chapter's potential conflict
            "words_per_chapter": 150, # Keep low
            "mode": "auto"
        }

        print(f"Starting novel generation with potentially conflicting theme: {novel_payload['theme']}")
        # Using print_json if available from common, otherwise just print
        # print_json(novel_payload, "Novel payload for AM-3:")
        print(f"Novel payload for AM-3: {novel_payload}")

        start_response = post_api("/novels/", novel_payload)
        novel_id = start_response.get("novel_id")

        # Using print_json if available
        # print_json(start_response, "Start novel response for AM-3:")
        print(f"Start novel response for AM-3: {start_response}")

        self.assertIsNotNone(novel_id, "Novel ID not received for AM-3")
        self.assertEqual(start_response.get("status"), "pending", "Initial status not 'pending' for AM-3")

        # Poll for completion
        # This path includes conflict detection and auto-resolution attempts.
        # The primary assertion is that it completes without runtime errors.
        try:
            final_status_data = poll_status(novel_id, expected_final_status="completed", timeout_secs=400) # Increased timeout slightly
            self.assertEqual(final_status_data.get("status"), "completed",
                f"AM-3 Final status not 'completed'. Got: {final_status_data.get('status')}, Full: {final_status_data}")
            print(f"Novel {novel_id} (AM-3) completed successfully.")
            print("Verification of this test primarily relies on the absence of errors during the run,")
            print("implying the conflict detection/resolution path was exercised without breaking the flow.")
            print("Deeper analysis of whether conflicts were truly found and resolved would require log inspection.")
        except Exception as e:
            print(f"ERROR during AM-3 E2E test for novel_id {novel_id}: {e}")
            # If poll_status raises an exception (e.g. timeout or 'failed' status), this will catch it.
            # We also need to fetch the final status from DB if possible to understand why it failed.
            try:
                status_from_db = query_db("SELECT workflow_status, error_message FROM novels WHERE id = ?", (novel_id,))
                if status_from_db:
                    print(f"Novel {novel_id} status from DB on error: {status_from_db[0]}")
            except Exception as db_e:
                print(f"Could not fetch novel status from DB after error: {db_e}")
            self.fail(f"AM-3 test failed for novel_id {novel_id} due to: {e}")


        print("--- E2E Test AM-3 Completed ---")

if __name__ == "__main__":
    print("Running E2E tests for Auto-Mode scenarios...")
    print(f"Make sure the API server is running at {common.API_BASE_URL} and using DB: {common.DB_PATH}")

    # Example of how to run specific tests if needed, or just use unittest.main()
    # suite = unittest.TestSuite()
    # suite.addTest(TestAutoModeE2E('test_auto_mode_full_run_am1'))
    # runner = unittest.TextTestRunner()
    # runner.run(suite)
    unittest.main(verbosity=2)

# Empty __init__.py for scripts/e2e_tests/
# This file can remain empty. It signals to Python that this directory
# should be treated as a package, allowing for imports like:
# from e2e_tests.common import some_function
# when the 'scripts' directory is in PYTHONPATH or the script is run from 'scripts'.
# For the current setup where test_auto_mode.py adds paths, it's less critical
# but good practice for structure.
