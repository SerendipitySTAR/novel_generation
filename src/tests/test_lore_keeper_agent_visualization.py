import unittest
import json
from unittest.mock import MagicMock, patch
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.persistence.database_manager import DatabaseManager # Used by LoreKeeperAgent

class TestLoreKeeperAgentVisualization(unittest.TestCase):

    def setUp(self):
        # Use an in-memory SQLite DB for testing or mock DatabaseManager
        self.db_manager_mock = MagicMock(spec=DatabaseManager)

        # Mock LLMClient for LoreKeeperAgent, though not directly used by get_knowledge_graph_data
        # However, KnowledgeBaseManager (part of LoreKeeperAgent) might try to init embeddings
        # So we patch KnowledgeBaseManager to prevent actual OpenAI API calls.
        self.kb_manager_patcher = patch('src.agents.lore_keeper_agent.KnowledgeBaseManager')
        self.mock_kb_manager_class = self.kb_manager_patcher.start()
        self.mock_kb_manager_instance = MagicMock()
        self.mock_kb_manager_class.return_value = self.mock_kb_manager_instance

        self.lore_keeper = LoreKeeperAgent(db_name=":memory:") # LLMClient is not passed, KB Manager is mocked
        # Replace the agent's db_manager with our mock AFTER initialization,
        # as __init__ creates its own db_manager instance.
        self.lore_keeper.db_manager = self.db_manager_mock


    def tearDown(self):
        self.kb_manager_patcher.stop()

    def test_get_knowledge_graph_data_no_novel_id(self):
        # This test assumes get_knowledge_graph_data might be called with invalid ID,
        # though current workflow ensures novel_id exists.
        # For robustness, the method itself could handle this.
        # Current method relies on db_manager to handle invalid novel_id.
        self.db_manager_mock.get_characters_for_novel.return_value = []
        self.db_manager_mock.get_novel_by_id.return_value = None # Simulate novel not found
        # self.db_manager_mock.get_active_plot_for_novel.return_value = None # Old mock, remove

        graph_data = self.lore_keeper.get_knowledge_graph_data(999) # Non-existent novel_id
        self.assertEqual(len(graph_data["nodes"]), 0)
        self.assertEqual(len(graph_data["edges"]), 0)

    def test_get_knowledge_graph_data_with_characters_and_plot(self):
        novel_id = 1
        # Mock characters should now match DetailedCharacterProfile structure
        # Required fields: character_id, novel_id, name, role_in_story, creation_date
        # Optional for testing graph node properties: appearance_summary, background_story
        mock_characters = [
            {"character_id": 1, "novel_id": novel_id, "name": "Hero", "appearance_summary": "Brave look", "role_in_story": "Protagonist", "creation_date": "2023-01-01T00:00:00Z"},
            {"character_id": 2, "novel_id": novel_id, "name": "Villain", "background_story": "Very evil", "role_in_story": "Antagonist", "creation_date": "2023-01-01T00:00:00Z"}
        ]
        # PlotChapterDetail structure (as JSON string in DB)
        mock_plot_details = [
            {"chapter_number": 1, "title": "The Beginning", "key_events_and_plot_progression": "Hero starts journey", "characters_present": ["Hero"]},
            {"chapter_number": 2, "title": "The Confrontation", "key_events_and_plot_progression": "Hero meets Villain", "characters_present": ["Hero", "Villain"]}
        ]
        mock_plot_summary_json = json.dumps(mock_plot_details)
        # Plot TypedDict requires: id, novel_id, plot_summary, creation_date
        mock_plot_db_record = {"id": 1, "novel_id": novel_id, "plot_summary": mock_plot_summary_json, "creation_date": "2023-01-01T00:00:00Z"}
        # Simulate get_novel_by_id returning a novel with an active_plot_id
        mock_novel_record = {"id": novel_id, "active_plot_id": 1, "user_theme": "test", "creation_date": "test", "last_updated_date": "test"}


        self.db_manager_mock.get_characters_for_novel.return_value = mock_characters
        self.db_manager_mock.get_novel_by_id.return_value = mock_novel_record
        self.db_manager_mock.get_plot_by_id.return_value = mock_plot_db_record

        graph_data = self.lore_keeper.get_knowledge_graph_data(novel_id)

        self.assertGreater(len(graph_data["nodes"]), 0)
        # Expected nodes: 2 characters + 2 plot events = 4 nodes
        self.assertEqual(len(graph_data["nodes"]), 4)
        self.assertEqual(len(graph_data["edges"]), 0) # Edges are not implemented yet

        char_node_count = sum(1 for node in graph_data["nodes"] if node["type"] == "character")
        event_node_count = sum(1 for node in graph_data["nodes"] if node["type"] == "plot_event")
        self.assertEqual(char_node_count, 2)
        self.assertEqual(event_node_count, 2)

        # Check a sample node
        hero_node = next(n for n in graph_data["nodes"] if n["id"] == "char_1")
        self.assertEqual(hero_node["label"], "Hero")
        # Based on LoreKeeperAgent logic: char_db.get('appearance_summary') or char_db.get('background_story', ...)
        self.assertEqual(hero_node["properties"]["description"], "Brave look")
        villain_node = next(n for n in graph_data["nodes"] if n["id"] == "char_2")
        self.assertEqual(villain_node["properties"]["description"], "Very evil")

        event_node = next(n for n in graph_data["nodes"] if n["id"].startswith("event_ch1"))
        self.assertTrue("Hero starts journey" in event_node["label"])


    def test_get_knowledge_graph_data_empty_plot(self):
        novel_id = 1
        mock_characters = [{"character_id": 1, "novel_id": novel_id, "name": "Solo Character", "role_in_story":"loner", "creation_date": "2023-01-01T00:00:00Z"}]
        mock_novel_record = {"id": novel_id, "active_plot_id": 1, "user_theme": "test", "creation_date": "test", "last_updated_date": "test"}
        mock_empty_plot_record = {"id": 1, "novel_id": novel_id, "plot_summary": "[]", "creation_date": "2023-01-01T00:00:00Z"}

        self.db_manager_mock.get_characters_for_novel.return_value = mock_characters
        self.db_manager_mock.get_novel_by_id.return_value = mock_novel_record
        self.db_manager_mock.get_plot_by_id.return_value = mock_empty_plot_record


        graph_data = self.lore_keeper.get_knowledge_graph_data(novel_id)
        self.assertEqual(len(graph_data["nodes"]), 1) # Only character node
        self.assertEqual(graph_data["nodes"][0]["type"], "character")

    def test_get_knowledge_graph_data_plot_json_decode_error(self):
        novel_id = 1
        mock_novel_record = {"id": novel_id, "active_plot_id": 1, "user_theme": "test", "creation_date": "test", "last_updated_date": "test"}
        mock_invalid_plot_record = {"id": 1, "novel_id": novel_id, "plot_summary": "This is not JSON", "creation_date": "2023-01-01T00:00:00Z"}

        self.db_manager_mock.get_characters_for_novel.return_value = []
        self.db_manager_mock.get_novel_by_id.return_value = mock_novel_record
        self.db_manager_mock.get_plot_by_id.return_value = mock_invalid_plot_record

        graph_data = self.lore_keeper.get_knowledge_graph_data(novel_id)
        # No nodes should be added from plot if JSON is invalid; error should be logged by agent.
        # Depending on implementation, it might return empty nodes or an error field.
        # The current agent code logs error and continues, so nodes from characters (if any) would still be there.
        self.assertEqual(len(graph_data["nodes"]), 0)


if __name__ == '__main__':
    unittest.main()
