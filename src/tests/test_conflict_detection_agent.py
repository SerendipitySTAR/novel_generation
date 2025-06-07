import unittest
from unittest.mock import patch, MagicMock
import uuid # For checking conflict_id format, not for generating in tests

from src.agents.conflict_detection_agent import ConflictDetectionAgent
# Need to mock LLMClient and LoreKeeperAgent (and its dependencies if used directly)
from src.llm_abstraction.llm_client import LLMClient
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager


# --- Mock Classes ---
class MockLLMClient:
    def __init__(self, response_map=None, default_response="No significant conflicts detected."):
        self.response_map = response_map if response_map else {}
        self.default_response = default_response
        self.last_prompt = None

    def generate_text(self, prompt: str, max_tokens: int) -> str:
        self.last_prompt = prompt # Store the last prompt for inspection
        # Check if any key from response_map is in the prompt
        for key, response in self.response_map.items():
            if key in prompt:
                return response
        return self.default_response

    def set_next_response(self, response: str):
        """Allows setting a specific response for the next call, useful for side_effect like behavior"""
        self.default_response = response


class MockKnowledgeBaseManager:
    def __init__(self, novel_id_to_query_results=None):
        self.novel_id_to_query_results = novel_id_to_query_results if novel_id_to_query_results else {}
        self.last_query_params = None

    def query_knowledge_base(self, novel_id: int, query_text: str, n_results: int = 3) -> list:
        self.last_query_params = (novel_id, query_text, n_results)
        return self.novel_id_to_query_results.get(novel_id, {}).get(query_text, [])

    def set_query_results_for_novel(self, novel_id: int, query_text: str, results: list):
        if novel_id not in self.novel_id_to_query_results:
            self.novel_id_to_query_results[novel_id] = {}
        self.novel_id_to_query_results[novel_id][query_text] = results


class MockLoreKeeperAgent:
    def __init__(self, db_name: str, llm_client: Optional[LLMClient] = None): # Added llm_client to match LKA's constructor
        self.db_name = db_name
        self.llm_client = llm_client # Store if needed for LKA's own ops, though not used in this mock's KB part
        self.kb_manager = MockKnowledgeBaseManager()
        print(f"MockLoreKeeperAgent initialized with db_name='{db_name}'")


class TestConflictDetectionAgent(unittest.TestCase):

    def setUp(self):
        self.db_name = "test_conflicts.db"
        self.mock_llm_client = MockLLMClient()
        self.novel_id = 1
        self.chapter_number = 1
        self.chapter_text = "This is a sample chapter text."
        self.novel_context = {"theme": "Fantasy", "style_preferences": "Dark"}

    # 1. Test Cases for Initialization
    def test_initialization_with_llm_and_db_name(self):
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client, db_name=self.db_name)
        self.assertIsNotNone(agent.llm_client)
        self.assertEqual(agent.db_name, self.db_name)
        self.assertIsNone(agent.lore_keeper) # LoreKeeper is instantiated on demand

    def test_initialization_with_llm_only(self):
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client)
        self.assertIsNotNone(agent.llm_client)
        self.assertIsNone(agent.db_name)
        self.assertIsNone(agent.lore_keeper)

    def test_initialization_with_llm_and_mock_lore_keeper_instance(self):
        mock_lka_instance = MockLoreKeeperAgent(db_name=self.db_name, llm_client=self.mock_llm_client)
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client, lore_keeper=mock_lka_instance)
        self.assertIsNotNone(agent.llm_client)
        self.assertEqual(agent.lore_keeper, mock_lka_instance)
        self.assertIsNone(agent.db_name) # db_name on agent is only for on-demand LKA

    # 2. Test Cases for detect_conflicts main logic
    @patch('src.agents.conflict_detection_agent.LoreKeeperAgent', new_callable=MockLoreKeeperAgent)
    def test_detect_conflicts_no_kb_context_no_llm_conflicts(self, MockLKA):
        # LLM returns "no conflicts" by default in mock
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client, db_name=self.db_name)
        # Ensure KB returns nothing
        # Access the kb_manager of the *instance* of MockLKA that will be created inside agent
        # This requires a bit more involved patching or accessing the created instance.
        # For simplicity, we assume MockLoreKeeperAgent's default MockKnowledgeBaseManager returns []

        conflicts = agent.detect_conflicts(self.novel_id, self.chapter_text, self.chapter_number, self.novel_context)
        self.assertEqual(len(conflicts), 0)

    @patch('src.agents.conflict_detection_agent.LoreKeeperAgent', new_callable=MagicMock) # Use MagicMock for more control
    def test_detect_conflicts_with_kb_context_llm_finds_one_conflict(self, mock_lka_constructor):
        # Configure LoreKeeperAgent mock instance and its kb_manager
        mock_lka_instance = MockLoreKeeperAgent(db_name=self.db_name, llm_client=self.mock_llm_client)
        mock_lka_instance.kb_manager.set_query_results_for_novel(
            self.novel_id, self.chapter_text[:1500], [("Character X is a pacifist.", 0.9)]
        )
        mock_lka_constructor.return_value = mock_lka_instance # Make constructor return our configured mock

        llm_response_one_conflict = """Conflict 1:
  Description: Character X, noted as a pacifist in KB, initiates a fight.
  Excerpt: Character X punched the guard.
  KB_Reference: Character X is a pacifist.
  Conflict_Type: Character Inconsistency
  Severity: Medium""" # No trailing --- for single conflict
        self.mock_llm_client.set_next_response(llm_response_one_conflict)

        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client, db_name=self.db_name) # Will use patched LKA

        conflicts = agent.detect_conflicts(self.novel_id, "Character X punched the guard.", self.chapter_number, self.novel_context)

        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(conflict['description'], "Character X, noted as a pacifist in KB, initiates a fight.")
        self.assertEqual(conflict['excerpt'], "Character X punched the guard.")
        self.assertEqual(conflict['kb_reference'], "Character X is a pacifist.")
        self.assertEqual(conflict['type'], "Character Inconsistency")
        self.assertEqual(conflict['severity'], "Medium")
        self.assertEqual(conflict['chapter_source'], self.chapter_number)
        self.assertTrue(uuid.UUID(conflict['conflict_id'])) # Check if it's a valid UUID

    @patch('src.agents.conflict_detection_agent.LoreKeeperAgent', new_callable=MagicMock)
    def test_detect_conflicts_llm_finds_multiple_conflicts(self, mock_lka_constructor):
        mock_lka_instance = MockLoreKeeperAgent(db_name=self.db_name, llm_client=self.mock_llm_client)
        mock_lka_instance.kb_manager.set_query_results_for_novel(
            self.novel_id, self.chapter_text[:1500], [("Character Y is infallibly honest.", 0.92)]
        )
        mock_lka_constructor.return_value = mock_lka_instance

        llm_response_multiple = """Conflict 1:
  Description: Internal contradiction about object color.
  Excerpt: The box was blue. Later, the box was red.
  KB_Reference: N/A
  Conflict_Type: Internal Inconsistency
  Severity: Low
---
Conflict 2:
  Description: Character Y acts against established KB trait.
  Excerpt: Character Y stole the artifact.
  KB_Reference: Character Y is infallibly honest.
  Conflict_Type: Character Inconsistency
  Severity: High
"""
        self.mock_llm_client.set_next_response(llm_response_multiple)
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client, db_name=self.db_name)
        conflicts = agent.detect_conflicts(self.novel_id, self.chapter_text, self.chapter_number, self.novel_context)

        self.assertEqual(len(conflicts), 2)
        self.assertEqual(conflicts[0]['type'], "Internal Inconsistency")
        self.assertEqual(conflicts[0]['severity'], "Low")
        self.assertEqual(conflicts[0]['kb_reference'], "N/A") # Check explicit N/A if LLM provides it
        self.assertEqual(conflicts[1]['type'], "Character Inconsistency")
        self.assertEqual(conflicts[1]['severity'], "High")
        self.assertIsNotNone(conflicts[1]['kb_reference'])


    # 3. Test Cases for _parse_conflict_response
    def test_parse_conflict_response_no_conflicts(self):
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client)
        response = "No significant conflicts detected."
        parsed = agent._parse_conflict_response(response, self.chapter_number)
        self.assertEqual(len(parsed), 0)

    def test_parse_conflict_response_single_conflict_all_fields(self):
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client)
        response = """Conflict 1:
  Description: Test Description
  Excerpt: Test Excerpt
  KB_Reference: Test KB Ref
  Conflict_Type: Test Type
  Severity: Test Severity"""
        parsed = agent._parse_conflict_response(response, self.chapter_number)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['description'], "Test Description")
        self.assertEqual(parsed[0]['excerpt'], "Test Excerpt")
        self.assertEqual(parsed[0]['kb_reference'], "Test KB Ref")
        self.assertEqual(parsed[0]['type'], "Test Type")
        self.assertEqual(parsed[0]['severity'], "Test Severity")

    def test_parse_conflict_response_single_conflict_missing_optional_kb_ref(self):
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client)
        response = """Conflict 1:
  Description: Test Description
  Excerpt: Test Excerpt
  Conflict_Type: Test Type
  Severity: Test Severity""" # KB_Reference is missing
        parsed = agent._parse_conflict_response(response, self.chapter_number)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['description'], "Test Description")
        self.assertIsNone(parsed[0].get('kb_reference')) # Should be None or not present
        self.assertEqual(parsed[0]['type'], "Test Type")

    def test_parse_conflict_response_malformed_block_skipped(self):
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client)
        response = """Conflict 1:
  Description: Valid one.
  Excerpt: Excerpt A.
  Conflict_Type: Type A
  Severity: High
---
Malformed Block: This block has no proper fields.
---
Conflict 3:
  Description: Another valid one.
  Excerpt: Excerpt C.
  Conflict_Type: Type C
  Severity: Low"""
        parsed = agent._parse_conflict_response(response, self.chapter_number)
        self.assertEqual(len(parsed), 2) # Malformed block should be skipped or result in a generic parsing error entry
        self.assertEqual(parsed[0]['description'], "Valid one.")
        self.assertEqual(parsed[1]['description'], "Another valid one.")
        # Check if a parsing error was logged for the middle block (if the parser is set to do so)
        # For current parser, it might just skip. If it adds a "Parsing Error" type, test for it.

    def test_parse_conflict_response_unparseable_but_not_no_conflict_message(self):
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client)
        response = "There are some issues here but not in the right format."
        parsed = agent._parse_conflict_response(response, self.chapter_number)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['type'], "Unparsed LLM Output")
        self.assertIn("LLM flagged potential issues, but they could not be parsed", parsed[0]['description'])


    # 4. Test Cases for Agent Resilience
    @patch('src.agents.conflict_detection_agent.LoreKeeperAgent')
    def test_detect_conflicts_lorekeeper_instantiation_failure(self, mock_lka_constructor):
        mock_lka_constructor.side_effect = Exception("LKA Init Failed")

        # LLM should still be called, but KB context will be unavailable
        self.mock_llm_client.set_next_response("Conflict 1:\n  Description: Internal only.\n  Excerpt: Snippet.\n  Conflict_Type: Internal\n  Severity: Low")
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client, db_name=self.db_name) # db_name is provided

        conflicts = agent.detect_conflicts(self.novel_id, self.chapter_text, self.chapter_number, self.novel_context)

        self.assertIn("Error instantiating LoreKeeperAgent: LKA Init Failed", self.mock_llm_client.last_prompt) # Check prompt
        self.assertIn("Knowledge Base context not available.", self.mock_llm_client.last_prompt)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['description'], "Internal only.")

    def test_detect_conflicts_llm_client_failure(self):
        self.mock_llm_client.generate_text = MagicMock(side_effect=Exception("LLM API Error"))
        agent = ConflictDetectionAgent(llm_client=self.mock_llm_client, db_name=self.db_name)

        conflicts = agent.detect_conflicts(self.novel_id, self.chapter_text, self.chapter_number, self.novel_context)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], "LLM Error")
        self.assertIn("LLM call failed: LLM API Error", conflicts[0]['description'])

    def test_detect_conflicts_no_llm_client(self):
        agent = ConflictDetectionAgent(llm_client=None, db_name=self.db_name)
        conflicts = agent.detect_conflicts(self.novel_id, self.chapter_text, self.chapter_number, self.novel_context)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['type'], "Setup Error")
        self.assertIn("LLMClient not configured", conflicts[0]['description'])


if __name__ == '__main__':
    unittest.main()
