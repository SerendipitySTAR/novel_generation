# src/tests/test_api_models.py
import unittest
from pydantic import ValidationError, BaseModel
from typing import Optional, Dict, Any # Ensure these are imported for the model itself
from unittest.mock import patch, MagicMock # Added for endpoint logic tests

from fastapi import HTTPException, BackgroundTasks # Added for endpoint logic tests

# Import the model to be tested & the endpoint function
from src.api.main import DecisionSubmissionRequest, submit_human_decision # Assuming this is the correct function name
from src.persistence.database_manager import DatabaseManager # For mocking
# WorkflowManager might not be directly needed if only DB manager is mocked for these specific tests


class TestAPIRequestModels(unittest.TestCase):

    def test_decision_submission_select_outline_valid(self):
        data = {"action": "select_outline", "selected_id": "outline_abc", "user_comment": "Looks good."}
        model = DecisionSubmissionRequest(**data)
        self.assertEqual(model.action, "select_outline")
        self.assertEqual(model.selected_id, "outline_abc")
        self.assertIsNone(model.conflict_id)
        self.assertIsNone(model.suggestion_index)
        self.assertEqual(model.user_comment, "Looks good.")
        self.assertIsNone(model.custom_payload)

    def test_decision_submission_apply_suggestion_valid(self):
        data = {"action": "apply_suggestion", "conflict_id": "c123", "suggestion_index": 0, "user_comment": "Applying first suggestion."}
        model = DecisionSubmissionRequest(**data)
        self.assertEqual(model.action, "apply_suggestion")
        self.assertEqual(model.conflict_id, "c123")
        self.assertEqual(model.suggestion_index, 0)
        self.assertEqual(model.user_comment, "Applying first suggestion.")
        self.assertIsNone(model.selected_id)

    def test_decision_submission_ignore_conflict_valid(self):
        data = {"action": "ignore_conflict", "conflict_id": "c456"}
        model = DecisionSubmissionRequest(**data)
        self.assertEqual(model.action, "ignore_conflict")
        self.assertEqual(model.conflict_id, "c456")
        self.assertIsNone(model.suggestion_index)
        self.assertIsNone(model.selected_id)

    def test_decision_submission_rewrite_all_valid(self):
        data = {"action": "rewrite_all_auto_remaining", "custom_payload": {"strategy": "aggressive"}}
        model = DecisionSubmissionRequest(**data)
        self.assertEqual(model.action, "rewrite_all_auto_remaining")
        self.assertIsNone(model.conflict_id)
        self.assertIsNone(model.suggestion_index)
        self.assertIsNone(model.selected_id)
        self.assertEqual(model.custom_payload, {"strategy": "aggressive"})

    def test_decision_submission_proceed_valid(self):
        data = {"action": "proceed_with_remaining"}
        model = DecisionSubmissionRequest(**data)
        self.assertEqual(model.action, "proceed_with_remaining")
        self.assertIsNone(model.selected_id)

    def test_decision_submission_missing_action_invalid(self):
        data = {"selected_id": "sel123"} # Missing 'action'
        with self.assertRaises(ValidationError) as context:
            DecisionSubmissionRequest(**data)
        self.assertTrue(any("action" in err.get("loc", ()) for err in context.exception.errors()))

    def test_decision_submission_all_optional_fields_can_be_none(self):
        # Only 'action' is mandatory
        data = {"action": "some_generic_action"}
        model = DecisionSubmissionRequest(**data)
        self.assertEqual(model.action, "some_generic_action")
        self.assertIsNone(model.selected_id)
        self.assertIsNone(model.conflict_id)
        self.assertIsNone(model.suggestion_index)
        self.assertIsNone(model.user_comment)
        self.assertIsNone(model.custom_payload)

    def test_decision_submission_invalid_action_type(self):
        data = {"action": 123} # Action should be a string
        with self.assertRaises(ValidationError):
            DecisionSubmissionRequest(**data)

    def test_decision_submission_invalid_suggestion_index_type(self):
        data = {"action": "apply_suggestion", "conflict_id": "c1", "suggestion_index": "zero"} # Index should be int
        with self.assertRaises(ValidationError):
            DecisionSubmissionRequest(**data)

    def test_decision_submission_invalid_custom_payload_type(self):
        data = {"action": "custom_action", "custom_payload": "not_a_dict"}
        with self.assertRaises(ValidationError):
            DecisionSubmissionRequest(**data)

    def test_decision_submission_extra_fields_ignored(self):
        # Pydantic v2 by default ignores extra fields
        data = {"action": "some_action", "extra_field_not_in_model": "some_value"}
        try:
            model = DecisionSubmissionRequest(**data)
            self.assertEqual(model.action, "some_action")
            self.assertFalse(hasattr(model, "extra_field_not_in_model"))
        except ValidationError as e:
            self.fail(f"Model creation failed with extra fields, should be ignored by default: {e.errors()}")


if __name__ == '__main__':
    unittest.main()


# New class for testing the API endpoint logic for decision submission
class TestAPIDecisionEndpointLogic(unittest.IsolatedAsyncioTestCase): # Using IsolatedAsyncioTestCase for async methods

    async def test_submit_decision_novel_not_found(self):
        with patch('src.api.main.DatabaseManager') as MockDbManager:
            mock_db_instance = MockDbManager.return_value
            # Simulate novel not found by get_novel_by_id, which is called before load_workflow_snapshot
            mock_db_instance.get_novel_by_id.return_value = None
            # load_workflow_snapshot_and_decision_info would also return None or not be reached
            mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = None

            request_payload = DecisionSubmissionRequest(action="select_outline", selected_id="0")
            mock_background_tasks = MagicMock(spec=BackgroundTasks)

            with self.assertRaises(HTTPException) as cm:
                await submit_human_decision(novel_id=999, decision_type_param="outline_selection", payload=request_payload, background_tasks=mock_background_tasks)

            self.assertEqual(cm.exception.status_code, 404)
            # The first check in the endpoint is get_novel_by_id
            self.assertIn("Novel with ID 999 not found.", str(cm.exception.detail))

    async def test_submit_decision_workflow_state_not_found(self):
        with patch('src.api.main.DatabaseManager') as MockDbManager:
            mock_db_instance = MockDbManager.return_value
            mock_db_instance.get_novel_by_id.return_value = {"id": 1, "user_theme": "Test"} # Novel exists
            mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = None # But no workflow state

            request_payload = DecisionSubmissionRequest(action="select_outline", selected_id="0")
            mock_background_tasks = MagicMock(spec=BackgroundTasks)

            with self.assertRaises(HTTPException) as cm:
                await submit_human_decision(novel_id=1, decision_type_param="outline_selection", payload=request_payload, background_tasks=mock_background_tasks)

            self.assertEqual(cm.exception.status_code, 404)
            self.assertIn("Workflow state not found for novel ID 1", str(cm.exception.detail))

    async def test_submit_decision_novel_not_paused(self):
        with patch('src.api.main.DatabaseManager') as MockDbManager:
            mock_db_instance = MockDbManager.return_value
            mock_db_instance.get_novel_by_id.return_value = {"id": 1, "user_theme": "Test"}
            mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
                "workflow_status": "running",
                "pending_decision_type": None
            }
            request_payload = DecisionSubmissionRequest(action="select_outline", selected_id="0")
            mock_background_tasks = MagicMock(spec=BackgroundTasks)

            with self.assertRaises(HTTPException) as cm:
                await submit_human_decision(novel_id=1, decision_type_param="outline_selection", payload=request_payload, background_tasks=mock_background_tasks)

            self.assertEqual(cm.exception.status_code, 409)
            self.assertIn("not currently awaiting a decision", str(cm.exception.detail))

    async def test_submit_decision_mismatched_decision_type(self):
        with patch('src.api.main.DatabaseManager') as MockDbManager:
            mock_db_instance = MockDbManager.return_value
            mock_db_instance.get_novel_by_id.return_value = {"id": 1, "user_theme": "Test"}
            mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
                "workflow_status": "paused_for_worldview_selection",
                "pending_decision_type": "worldview_selection"
            }
            request_payload = DecisionSubmissionRequest(action="select_outline", selected_id="0") # Submitting for outline
            mock_background_tasks = MagicMock(spec=BackgroundTasks)

            with self.assertRaises(HTTPException) as cm:
                await submit_human_decision(novel_id=1, decision_type_param="outline_selection", payload=request_payload, background_tasks=mock_background_tasks)

            self.assertEqual(cm.exception.status_code, 409)
            self.assertIn("awaiting decision type 'worldview_selection', but received decision for 'outline_selection'", str(cm.exception.detail))

    async def test_submit_decision_payload_missing_selected_id_for_outline(self):
        with patch('src.api.main.DatabaseManager') as MockDbManager:
            mock_db_instance = MockDbManager.return_value
            mock_db_instance.get_novel_by_id.return_value = {"id": 1, "user_theme": "Test"}
            mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
                "workflow_status": "paused_for_outline_selection",
                "pending_decision_type": "outline_selection"
            }
            # Payload missing 'selected_id', but action implies it's needed for outline_selection
            invalid_payload = DecisionSubmissionRequest(action="select_outline_option")
            mock_background_tasks = MagicMock(spec=BackgroundTasks)

            with self.assertRaises(HTTPException) as cm:
                await submit_human_decision(novel_id=1, decision_type_param="outline_selection", payload=invalid_payload, background_tasks=mock_background_tasks)

            self.assertEqual(cm.exception.status_code, 422)
            self.assertIn("'selected_id' is required", str(cm.exception.detail))
            self.assertIn("outline_selection", str(cm.exception.detail)) # Check if decision type is mentioned

    async def test_submit_decision_payload_missing_fields_for_apply_suggestion(self):
        with patch('src.api.main.DatabaseManager') as MockDbManager:
            mock_db_instance = MockDbManager.return_value
            mock_db_instance.get_novel_by_id.return_value = {"id": 1, "user_theme": "Test"}
            mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
                "workflow_status": "paused_for_conflict_review",
                "pending_decision_type": "conflict_review"
            }
            # Missing conflict_id and suggestion_index
            invalid_payload = DecisionSubmissionRequest(action="apply_suggestion")
            mock_background_tasks = MagicMock(spec=BackgroundTasks)

            with self.assertRaises(HTTPException) as cm:
                await submit_human_decision(novel_id=1, decision_type_param="conflict_review", payload=invalid_payload, background_tasks=mock_background_tasks)

            self.assertEqual(cm.exception.status_code, 422)
            self.assertIn("'conflict_id' and 'suggestion_index' are required", str(cm.exception.detail))

    async def test_submit_decision_payload_missing_conflict_id_for_ignore(self):
        with patch('src.api.main.DatabaseManager') as MockDbManager:
            mock_db_instance = MockDbManager.return_value
            mock_db_instance.get_novel_by_id.return_value = {"id": 1, "user_theme": "Test"}
            mock_db_instance.load_workflow_snapshot_and_decision_info.return_value = {
                "workflow_status": "paused_for_conflict_review",
                "pending_decision_type": "conflict_review"
            }
            invalid_payload = DecisionSubmissionRequest(action="ignore_conflict") # Missing conflict_id
            mock_background_tasks = MagicMock(spec=BackgroundTasks)

            with self.assertRaises(HTTPException) as cm:
                await submit_human_decision(novel_id=1, decision_type_param="conflict_review", payload=invalid_payload, background_tasks=mock_background_tasks)

            self.assertEqual(cm.exception.status_code, 422)
            self.assertIn("'conflict_id' is required", str(cm.exception.detail))
