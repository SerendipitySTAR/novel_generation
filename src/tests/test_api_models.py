# src/tests/test_api_models.py
import unittest
from pydantic import ValidationError, BaseModel
from typing import Optional, Dict, Any # Ensure these are imported for the model itself

# Import the model to be tested
from src.api.main import DecisionSubmissionRequest

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
