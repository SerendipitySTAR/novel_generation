import sys
import os
import time
import unittest # Import unittest for structure, though not strictly using its runner here for E2E
import json
import requests # For requests.exceptions.HTTPError

# Add scripts directory to path to import common
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common import post_api, get_api, poll_status, query_db, count_db_records, API_BASE_URL # type: ignore

# Helper to print JSON nicely
def print_json(data, message=""):
    if message:
        print(message)
    print(json.dumps(data, indent=2, ensure_ascii=False))

class TestHumanModeAPI_HM1(unittest.TestCase): # Using unittest.TestCase for structure

    def test_human_mode_full_lifecycle_hm1(self):
        print("\n--- Running E2E Test: Human-Mode Full Lifecycle (HM-1) ---")

        novel_payload = {
            "theme": "A historian time-travels to verify a controversial theory about a lost library, but the timeline fights back.",
            "style_preferences": "Philosophical thriller with detailed historical settings",
            "chapters": 1, # Focus on decision points for one chapter
            "words_per_chapter": 100, # Keep low for speed
            "mode": "human",
            "interaction_mode": "api" # Crucial for API-driven human mode
        }

        # 1. Start Novel
        print_json(novel_payload, "Starting novel generation with payload:")
        start_response = post_api("/novels/", novel_payload)
        novel_id = start_response.get("novel_id")
        print_json(start_response, "Start novel response:")
        self.assertIsNotNone(novel_id, "Novel ID not received")
        self.assertEqual(start_response.get("status"), "pending", "Initial status not 'pending'")

        # --- Outline Selection ---
        print("\n--- Waiting for Outline Selection Pause ---")
        status_data = poll_status(novel_id, expected_final_status="paused_for_outline_selection", timeout_secs=120)
        self.assertTrue(status_data.get("workflow_status", "").startswith("paused_for_outline_selection"))

        decision_prompt = get_api(f"/novels/{novel_id}/decisions/next")
        print_json(decision_prompt, "Outline selection prompt:")
        self.assertEqual(decision_prompt.get("decision_type"), "outline_selection")
        self.assertIsNotNone(decision_prompt.get("options"), "No outline options provided")
        self.assertTrue(len(decision_prompt["options"]) > 0, "Outline options list is empty")

        chosen_outline_id = decision_prompt["options"][0]["id"] # Select the first outline (0-based index as string)
        outline_decision_payload = {"action": "select_outline_option", "selected_id": chosen_outline_id} # Action name for clarity
        print_json(outline_decision_payload, f"Submitting outline decision (choosing option {chosen_outline_id}):")
        submit_response = post_api(f"/novels/{novel_id}/decisions/outline_selection", outline_decision_payload)
        print_json(submit_response, "Submit outline decision response:")
        self.assertTrue(submit_response.get("status_after_resume_trigger", "").startswith("resuming_with_decision"))

        # --- Worldview Selection ---
        print("\n--- Waiting for Worldview Selection Pause ---")
        status_data = poll_status(novel_id, expected_final_status="paused_for_worldview_selection", timeout_secs=120)
        self.assertTrue(status_data.get("workflow_status", "").startswith("paused_for_worldview_selection"))

        decision_prompt = get_api(f"/novels/{novel_id}/decisions/next")
        print_json(decision_prompt, "Worldview selection prompt:")
        self.assertEqual(decision_prompt.get("decision_type"), "worldview_selection")
        self.assertIsNotNone(decision_prompt.get("options"), "No worldview options provided")
        self.assertTrue(len(decision_prompt["options"]) > 0, "Worldview options list is empty")

        chosen_worldview_id = decision_prompt["options"][0]["id"] # Select the first worldview
        worldview_decision_payload = {"action": "select_worldview_option", "selected_id": chosen_worldview_id}
        print_json(worldview_decision_payload, f"Submitting worldview decision (choosing option {chosen_worldview_id}):")
        submit_response = post_api(f"/novels/{novel_id}/decisions/worldview_selection", worldview_decision_payload)
        print_json(submit_response, "Submit worldview decision response:")
        self.assertTrue(submit_response.get("status_after_resume_trigger", "").startswith("resuming_with_decision"))

        # --- Conflict Review (Chapter 1) ---
        print("\n--- Waiting for Conflict Review Pause (Chapter 1) ---")
        # This might take longer as chapter generation, conflict detection etc. happen here
        status_data = poll_status(novel_id, expected_final_status=f"paused_for_conflict_review_ch_1", timeout_secs=300)
        self.assertTrue(status_data.get("workflow_status", "").startswith("paused_for_conflict_review_ch_1"))

        decision_prompt = get_api(f"/novels/{novel_id}/decisions/next")
        print_json(decision_prompt, "Conflict review prompt (initial):")
        self.assertEqual(decision_prompt.get("decision_type"), "conflict_review")

        conflicts = decision_prompt.get("options", [])
        if not conflicts:
            print("No conflicts detected for Chapter 1, skipping conflict interaction steps.")
        else:
            print(f"Detected {len(conflicts)} conflicts for Chapter 1.")

            # Action 1: Apply a suggestion for the first conflict (if suggestions exist)
            first_conflict = conflicts[0]
            conflict_id_1 = first_conflict.get("id")
            suggestions_1 = first_conflict.get("full_data", {}).get("llm_suggestions", [])

            if conflict_id_1 and suggestions_1:
                apply_sugg_payload = {"action": "apply_suggestion", "conflict_id": conflict_id_1, "suggestion_index": 0}
                print_json(apply_sugg_payload, f"Submitting 'apply_suggestion' for conflict {conflict_id_1}:")
                submit_response = post_api(f"/novels/{novel_id}/decisions/conflict_review", apply_sugg_payload)
                print_json(submit_response, "Apply suggestion response:")
                self.assertTrue(submit_response.get("status_after_resume_trigger", "").startswith("resuming_with_decision"))

                print("\n--- Waiting for re-pause after applying suggestion ---")
                status_data = poll_status(novel_id, expected_final_status=f"paused_for_conflict_review_ch_1", timeout_secs=180)
                self.assertTrue(status_data.get("workflow_status", "").startswith("paused_for_conflict_review_ch_1"))

                # Fetch updated conflicts
                decision_prompt_after_apply = get_api(f"/novels/{novel_id}/decisions/next")
                print_json(decision_prompt_after_apply, "Conflict review prompt (after apply_suggestion):")
                conflicts = decision_prompt_after_apply.get("options", []) # Refresh conflicts list
            else:
                print(f"Skipping 'apply_suggestion' as conflict {conflict_id_1} has no suggestions or ID.")

            # Action 2: Ignore the next available conflict (if any unresolved remain)
            # Find an unresolved conflict to ignore
            conflict_to_ignore = None
            for c in conflicts:
                if c.get("full_data", {}).get("resolution_status") != "applied_suggestion":
                    conflict_to_ignore = c
                    break

            if conflict_to_ignore and conflict_to_ignore.get("id"):
                conflict_id_2 = conflict_to_ignore.get("id")
                ignore_payload = {"action": "ignore_conflict", "conflict_id": conflict_id_2}
                print_json(ignore_payload, f"Submitting 'ignore_conflict' for conflict {conflict_id_2}:")
                submit_response = post_api(f"/novels/{novel_id}/decisions/conflict_review", ignore_payload)
                print_json(submit_response, "Ignore conflict response:")
                self.assertTrue(submit_response.get("status_after_resume_trigger", "").startswith("resuming_with_decision"))

                print("\n--- Waiting for re-pause after ignoring conflict ---")
                status_data = poll_status(novel_id, expected_final_status=f"paused_for_conflict_review_ch_1", timeout_secs=180)
                self.assertTrue(status_data.get("workflow_status", "").startswith("paused_for_conflict_review_ch_1"))
            else:
                print("No remaining unresolved conflict to ignore, or conflict has no ID.")

            # Action 3: Proceed with remaining
            proceed_payload = {"action": "proceed_with_remaining"}
            print_json(proceed_payload, "Submitting 'proceed_with_remaining':")
            submit_response = post_api(f"/novels/{novel_id}/decisions/conflict_review", proceed_payload)
            print_json(submit_response, "Proceed with remaining response:")
            self.assertTrue(submit_response.get("status_after_resume_trigger", "").startswith("resuming_with_decision"))

        # --- Completion ---
        print("\n--- Waiting for Novel Completion ---")
        final_status_data = poll_status(novel_id, expected_final_status="completed", timeout_secs=180)
        self.assertEqual(final_status_data.get("workflow_status"), "completed", "Final status not 'completed'")

        # --- Final DB Checks (Simplified) ---
        print(f"Verifying final database records for novel_id {novel_id}...")
        novel_record = query_db("SELECT * FROM novels WHERE id = ?", (novel_id,))
        self.assertEqual(len(novel_record), 1, "Novel record not found")
        self.assertEqual(novel_record[0]["workflow_status"], "completed")

        chapters_in_db = query_db("SELECT id, title, content FROM chapters WHERE novel_id = ? AND chapter_number = 1", (novel_id,))
        self.assertEqual(len(chapters_in_db), 1, "Chapter 1 not found in DB")
        print(f"Chapter 1 Title: {chapters_in_db[0]['title']}")
        # Further checks could involve verifying if chapter content reflects applied suggestions.
        # For example, if suggestions_1[0] was "new excerpt", check if "new excerpt" is in chapters_in_db[0]['content']
        # and the original excerpt (if known) is not. This requires knowing the original excerpt & suggestion.

        print("--- E2E Test HM-1 Completed Successfully ---")

    def test_human_mode_api_error_handling_hm2(self):
        print("\n--- Running E2E Test: Human-Mode API Error Handling (HM-2) ---")

        novel_payload_for_error_test = {
            "theme": "Error Handling Test Novel",
            "style_preferences": "Technical manual style",
            "chapters": 1,
            "words_per_chapter": 50,
            "mode": "human",
            "interaction_mode": "api"
        }

        # 1. Start a novel and let it pause for outline selection
        print("Starting a novel for error handling tests...")
        start_response = post_api("/novels/", novel_payload_for_error_test)
        novel_id = start_response.get("novel_id")
        print_json(start_response, "Start novel response:")
        self.assertIsNotNone(novel_id, "Novel ID not received for error test")

        print(f"Waiting for novel {novel_id} to pause for outline selection...")
        status_data = poll_status(novel_id, expected_final_status="paused_for_outline_selection", timeout_secs=120)
        self.assertTrue(status_data.get("workflow_status", "").startswith("paused_for_outline_selection"),
                        f"Novel did not pause for outline selection. Current status: {status_data.get('workflow_status')}")

        # 2. Attempt to submit a decision for the WRONG decision type
        print(f"Attempting to submit 'conflict_review' decision when 'outline_selection' is expected for novel {novel_id}...")
        wrong_decision_payload = {"action": "proceed_with_remaining"} # A valid payload for conflict_review
        try:
            post_api(f"/novels/{novel_id}/decisions/conflict_review", wrong_decision_payload)
            self.fail("API did not return an error for wrong decision type submission.")
        except requests.exceptions.HTTPError as e:
            print(f"Received expected HTTPError: {e.response.status_code} - {e.response.text}")
            # Expecting 400 (Bad Request) or 409 (Conflict) or 422 (Unprocessable Entity)
            self.assertIn(e.response.status_code, [400, 409, 422],
                          f"Expected 400, 409, or 422 for wrong decision type, got {e.response.status_code}")

        # 3. Attempt to submit a decision with an INVALID payload for the correct decision type
        print(f"Attempting to submit 'outline_selection' with invalid payload for novel {novel_id}...")
        invalid_payload = {"action": "select_outline_option"} # Missing 'selected_id'
        try:
            post_api(f"/novels/{novel_id}/decisions/outline_selection", invalid_payload)
            self.fail("API did not return an error for invalid payload.")
        except requests.exceptions.HTTPError as e:
            print(f"Received expected HTTPError: {e.response.status_code} - {e.response.text}")
            self.assertEqual(e.response.status_code, 422, # Pydantic validation error
                             f"Expected 422 for invalid payload, got {e.response.status_code}")

        # Test with another invalid payload: action missing (if model allows other fields to be validated first)
        invalid_payload_no_action = {"selected_id": "0"}
        print(f"Attempting to submit 'outline_selection' with missing 'action' for novel {novel_id}...")
        try:
            post_api(f"/novels/{novel_id}/decisions/outline_selection", invalid_payload_no_action)
            self.fail("API did not return an error for payload missing 'action'.")
        except requests.exceptions.HTTPError as e:
            print(f"Received expected HTTPError: {e.response.status_code} - {e.response.text}")
            self.assertEqual(e.response.status_code, 422,
                             f"Expected 422 for payload missing 'action', got {e.response.status_code}")


        # 4. Attempt to submit a decision for a NON-EXISTENT novel
        non_existent_novel_id = 9999999 # Use a valid format (int) but non-existent ID
        print(f"Attempting to submit decision for non-existent novel_id {non_existent_novel_id}...")
        valid_payload_for_outline = {"action": "select_outline_option", "selected_id": "0"}
        try:
            post_api(f"/novels/{non_existent_novel_id}/decisions/outline_selection", valid_payload_for_outline)
            self.fail("API did not return an error for non-existent novel_id.")
        except requests.exceptions.HTTPError as e:
            print(f"Received expected HTTPError: {e.response.status_code} - {e.response.text}")
            self.assertEqual(e.response.status_code, 404, # Not Found
                             f"Expected 404 for non-existent novel_id, got {e.response.status_code}")

        # Cleanup: For now, we don't have a /delete_novel endpoint.
        # The test novel {novel_id} will remain in the DB unless manually cleaned.
        # To make tests idempotent, a cleanup mechanism or unique DB per run would be needed.
        print("--- E2E Test HM-2 API Error Handling Completed Successfully ---")

if __name__ == "__main__":
    # This script assumes the FastAPI server (src.api.main) is running.
    # It also assumes that the database defined in common.py (e.g., novel_api_main.db)
    # is the one used by the server and is in a clean state or testable state.
    # For CI, a setup/teardown for the DB and server would be needed.

    # Create a dummy DB for this direct run if it doesn't exist, to satisfy common.py
    # In a real E2E setup, the server would manage its own DB.
    # Check if common module and DB_PATH are available
    try:
        from common import DB_PATH
        if not os.path.exists(DB_PATH):
            print(f"Creating dummy DB for E2E test script direct run: {DB_PATH}")
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            conn.close()
    except ImportError:
        print("Warning: common.py not found, cannot create dummy DB if needed by common.py.")
    except AttributeError:
        print("Warning: DB_PATH not found in common.py, cannot create dummy DB.")


    unittest.main()
