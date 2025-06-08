from typing import Any, List, Optional, Dict
import operator
class AutoDecisionEngine:
    def __init__(self):
        """
        Initializes the AutoDecisionEngine.
        Future enhancements could include loading models or configurations.
        """
        print("AutoDecisionEngine initialized.")

    def decide(self, options: List[Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Makes a decision from a list of options.
        For Phase 1, this is a simple "select the first option" logic.

        Args:
            options: A list of options to choose from.
            context: Optional context that might influence the decision in the future.

        Returns:
            The selected option. Returns None if options list is empty.
        """
        if not options:
            print("AutoDecisionEngine: No options provided to decide from.")
            return None

        # Basic strategy: pick the first option
        selected_option = options[0]

        print(f"AutoDecisionEngine: Decided on option: {selected_option} from {len(options)} choices.")
        if context:
            print(f"AutoDecisionEngine: Context provided: {list(context.keys())}")

        # Score-based decision logic
        if context and context.get("decision_type") == "score_threshold_branch":
            score = context.get("score")
            threshold = context.get("threshold")
            operator_str = context.get("operator")

            # Options for score-based decision are typically outcome paths/branch names
            # e.g., ["proceed_if_true", "proceed_if_false"]

            if not (options and len(options) >= 2):
                print("AutoDecisionEngine: Error - Score-based decision requires at least two outcome options (branches).")
                # Fallback to default logic or raise error
                # For now, let's try to proceed if possible, or just return None if options are truly bad
                if not options: return None
                selected_option = options[0] # Fallback
                print(f"AutoDecisionEngine: Falling back to selecting first option: {selected_option}")
                return selected_option

            if score is None or threshold is None or operator_str is None:
                print("AutoDecisionEngine: Error - Missing 'score', 'threshold', or 'operator' in context for score_threshold_branch.")
                # Fallback to default logic (e.g. first path)
                selected_option = options[0]
                print(f"AutoDecisionEngine: Falling back to selecting first outcome path: {selected_option}")
                return selected_option

            ops = {
                ">": operator.gt,
                "<": operator.lt,
                ">=": operator.ge,
                "<=": operator.le,
                "==": operator.eq,
                "!=": operator.ne,
            }
            op_func = ops.get(operator_str)

            if op_func is None:
                print(f"AutoDecisionEngine: Error - Invalid operator string '{operator_str}'.")
                # Fallback to default logic (e.g. first path)
                selected_option = options[0]
                print(f"AutoDecisionEngine: Falling back to selecting first outcome path: {selected_option}")
                return selected_option

            try:
                score_float = float(score)
                threshold_float = float(threshold)
            except ValueError:
                print("AutoDecisionEngine: Error - Score or threshold cannot be converted to float.")
                selected_option = options[0]
                print(f"AutoDecisionEngine: Falling back to selecting first outcome path: {selected_option}")
                return selected_option

            result = op_func(score_float, threshold_float)
            print(f"AutoDecisionEngine: Score-based decision: {score_float} {operator_str} {threshold_float} = {result}")

            if result: # True condition
                selected_path = options[0]
                print(f"AutoDecisionEngine: Path selected based on TRUE result: {selected_path}")
                return selected_path
            else: # False condition
                selected_path = options[1]
                print(f"AutoDecisionEngine: Path selected based on FALSE result: {selected_path}")
                return selected_path

        # Original fallback logic if not score-based or if score-based failed and fell through
        if not options: # This check is now redundant due to earlier check in score-based logic, but keep for general case
            print("AutoDecisionEngine: No options provided to decide from (re-check).")
            return None

        selected_option = options[0]
        print(f"AutoDecisionEngine: Default logic: Decided on option: {selected_option} from {len(options)} choices.")
        return selected_option

if __name__ == '__main__':
    # Example Usage
    engine = AutoDecisionEngine()

    # Test case 1: List of strings
    string_options = ["Option A", "Option B", "Option C"]
    decision1 = engine.decide(string_options)
    print(f"Test Case 1 Decision: {decision1}") # Expected: Option A

    # Test case 2: List of numbers
    number_options = [10, 20, 30]
    decision2 = engine.decide(number_options, context={"reason": "numerical selection"})
    print(f"Test Case 2 Decision: {decision2}") # Expected: 10

    # Test case 3: Empty list
    empty_options = []
    decision3 = engine.decide(empty_options)
    print(f"Test Case 3 Decision: {decision3}") # Expected: None

    # Test case 4: List with one option
    single_option = [{"id": 1, "value": "Unique"}]
    decision4 = engine.decide(single_option)
    print(f"Test Case 4 Decision: {decision4}") # Expected: {"id": 1, "value": "Unique"}

    print("\n--- Score-Based Decision Tests ---")
    # Test case 5: Score >= Threshold (True path)
    score_options = ["retry_chapter", "proceed_to_kb_update"]
    context5 = {
        "decision_type": "score_threshold_branch",
        "score": 8.5,
        "threshold": 7.0,
        "operator": ">=",
    }
    decision5 = engine.decide(score_options, context5)
    print(f"Test Case 5 (Score >= Threshold): {decision5}") # Expected: retry_chapter (options[0])

    # Test case 6: Score < Threshold (False path)
    context6 = {
        "decision_type": "score_threshold_branch",
        "score": 6.0,
        "threshold": 7.0,
        "operator": ">=", # Score 6.0 is NOT >= 7.0
    }
    decision6 = engine.decide(score_options, context6)
    print(f"Test Case 6 (Score < Threshold): {decision6}") # Expected: proceed_to_kb_update (options[1])

    # Test case 7: Missing context fields (e.g., score)
    context7 = {
        "decision_type": "score_threshold_branch",
        # "score": 9.0, # Score is missing
        "threshold": 7.0,
        "operator": ">=",
    }
    decision7 = engine.decide(score_options, context7)
    print(f"Test Case 7 (Missing Score): {decision7}") # Expected: Fallback to options[0] (retry_chapter)

    # Test case 8: Invalid operator string
    context8 = {
        "decision_type": "score_threshold_branch",
        "score": 9.0,
        "threshold": 7.0,
        "operator": "INVALID_OP",
    }
    decision8 = engine.decide(score_options, context8)
    print(f"Test Case 8 (Invalid Operator): {decision8}") # Expected: Fallback to options[0] (retry_chapter)

    # Test case 9: Not enough options for score-based decision
    not_enough_options = ["only_one_path"]
    context9 = {
        "decision_type": "score_threshold_branch",
        "score": 9.0,
        "threshold": 7.0,
        "operator": ">=",
    }
    decision9 = engine.decide(not_enough_options, context9)
    print(f"Test Case 9 (Not enough options): {decision9}") # Expected: Fallback to options[0] (only_one_path)

    # Test case 10: Score and threshold as strings
    context10 = {
        "decision_type": "score_threshold_branch",
        "score": "9.1",
        "threshold": "8.2",
        "operator": ">",
    }
    decision10 = engine.decide(score_options, context10)
    print(f"Test Case 10 (String scores): {decision10}") # Expected: retry_chapter

    # Test case 11: Non-convertible score
    context11 = {
        "decision_type": "score_threshold_branch",
        "score": "high",
        "threshold": "8.2",
        "operator": ">",
    }
    decision11 = engine.decide(score_options, context11)
    print(f"Test Case 11 (Non-convertible score): {decision11}") # Expected: retry_chapter (fallback)
