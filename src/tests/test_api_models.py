# src/tests/test_api_models.py
import unittest
from pydantic import ValidationError
from typing import Optional, Dict, Any # Ensure these are imported for the model itself

# Import the model to be tested
from src.api.main import DecisionSubmissionRequest

class TestAPIRequestModels(unittest.TestCase):

    def test_decision_submission_apply_suggestion_valid(self):
        data = {"action": "apply_suggestion", "conflict_id": "c123", "suggestion_index": 0, "user_comment": "Applying first suggestion."}
        try:
            model = DecisionSubmissionRequest(**data)
            self.assertEqual(model.action, "apply_suggestion")
            self.assertEqual(model.conflict_id, "c123")
            self.assertEqual(model.suggestion_index, 0)
            self.assertEqual(model.user_comment, "Applying first suggestion.")
        except ValidationError as e:
            self.fail(f"Validation failed for valid data: {e.errors()}")

    def test_decision_submission_ignore_conflict_valid(self):
        data = {"action": "ignore_conflict", "conflict_id": "c456"}
        try:
            model = DecisionSubmissionRequest(**data)
            self.assertEqual(model.action, "ignore_conflict")
            self.assertEqual(model.conflict_id, "c456")
            self.assertIsNone(model.suggestion_index)
            self.assertIsNone(model.user_comment)
        except ValidationError as e:
            self.fail(f"Validation failed for valid data: {e.errors()}")

    def test_decision_submission_rewrite_all_valid(self):
        data = {"action": "rewrite_all_auto_remaining"}
        try:
            model = DecisionSubmissionRequest(**data)
            self.assertEqual(model.action, "rewrite_all_auto_remaining")
            self.assertIsNone(model.conflict_id)
            self.assertIsNone(model.suggestion_index)
        except ValidationError as e:
            self.fail(f"Validation failed for valid data: {e.errors()}")

    def test_decision_submission_proceed_valid(self):
        data = {"action": "proceed_with_remaining"}
        try:
            model = DecisionSubmissionRequest(**data)
            self.assertEqual(model.action, "proceed_with_remaining")
        except ValidationError as e:
            self.fail(f"Validation failed for valid data: {e.errors()}")

    def test_decision_submission_missing_action_invalid(self):
        data = {"conflict_id": "c123"} # Missing 'action'
        with self.assertRaises(ValidationError) as context:
            DecisionSubmissionRequest(**data)
        # Check that the error message mentions 'action'
        self.assertTrue(any("action" in err.get("loc", ()) for err in context.exception.errors()))


    def test_decision_submission_apply_suggestion_optional_fields_can_be_none(self):
        # This test verifies that optional fields can indeed be None if not provided,
        # as per current model definition. API logic would handle if they are required for certain actions.
        data = {"action": "apply_suggestion"} # conflict_id and suggestion_index are optional in model
        try:
            model = DecisionSubmissionRequest(**data)
            self.assertEqual(model.action, "apply_suggestion")
            self.assertIsNone(model.conflict_id)
            self.assertIsNone(model.suggestion_index)
        except ValidationError as e:
            self.fail(f"Validation should pass with optional fields missing: {e.errors()}")

    def test_decision_submission_invalid_action_type(self):
        data = {"action": 123} # Action should be a string
        with self.assertRaises(ValidationError):
            DecisionSubmissionRequest(**data)

    def test_decision_submission_invalid_suggestion_index_type(self):
        data = {"action": "apply_suggestion", "conflict_id": "c1", "suggestion_index": "zero"} # Index should be int
        with self.assertRaises(ValidationError):
            DecisionSubmissionRequest(**data)

if __name__ == '__main__':
    unittest.main()
