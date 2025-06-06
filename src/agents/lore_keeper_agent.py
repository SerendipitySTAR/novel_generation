import os
from dotenv import load_dotenv
from typing import List, Dict, Optional, Any # Added Optional and Any
from datetime import datetime, timezone
import uuid # Added import

from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
from src.persistence.database_manager import DatabaseManager
from src.core.models import Outline, WorldView, Plot, Character, Chapter, KnowledgeBaseEntry

class LoreKeeperAgent:
    def __init__(self, db_name: str = "novel_mvp.db", chroma_db_directory: str = "./chroma_db"):
        self.db_manager = DatabaseManager(db_name=db_name)
        # KnowledgeBaseManager will load .env and check for OPENAI_API_KEY itself
        try:
            self.kb_manager = KnowledgeBaseManager(db_directory=chroma_db_directory)
        except ValueError as e:
            print(f"Error initializing KnowledgeBaseManager in LoreKeeperAgent: {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or a .env file.")
            raise # Re-raise the error to stop initialization if KB manager fails

    def _prepare_text_from_outline(self, outline: Outline) -> str:
        return f"Overall Outline: {outline['overview_text']}"

    def _prepare_text_from_worldview(self, worldview: WorldView) -> str:
        return f"Worldview Setting: {worldview['description_text']}"

    def _prepare_text_from_plot(self, plot: Plot) -> str:
        return f"Main Plot Points: {plot['plot_summary']}"

    def _prepare_texts_from_characters(self, characters) -> List[str]:
        """
        Prepare text descriptions from characters.
        Handles both Character (DB model) and DetailedCharacterProfile objects.
        """
        texts = []
        for c in characters:
            name = c.get('name', 'Unknown')
            role = c.get('role_in_story', 'Unknown role')

            # Handle DetailedCharacterProfile (from CharacterSculptorAgent)
            if 'background_story' in c or 'personality_traits' in c:
                # This is a DetailedCharacterProfile
                description_parts = []
                if c.get('appearance_summary'):
                    description_parts.append(f"Appearance: {c['appearance_summary']}")
                if c.get('background_story'):
                    description_parts.append(f"Background: {c['background_story']}")
                if c.get('personality_traits'):
                    description_parts.append(f"Personality: {c['personality_traits']}")
                if c.get('motivations_deep_drive'):
                    description_parts.append(f"Motivation: {c['motivations_deep_drive']}")

                description = ". ".join(description_parts) if description_parts else "Detailed character profile available."
            else:
                # This is a Character (DB model) with a simple description field
                description = c.get('description', 'No description available.')

            text = f"Character: {name}. Description: {description}. Role: {role}"
            texts.append(text)

        return texts

    def initialize_knowledge_base(self, novel_id: int, outline: Outline, worldview: WorldView, plot: Plot, characters) -> None:
        all_texts: List[str] = []
        all_metadatas: List[Dict[str, any]] = [] # 'any' is more appropriate here than str for metadata values

        # Outline
        outline_text = self._prepare_text_from_outline(outline)
        all_texts.append(outline_text)
        all_metadatas.append({'source': 'outline', 'outline_id': outline['id']})
        self.db_manager.add_kb_entry(
            novel_id=novel_id,
            entry_type='outline',
            content_text=outline_text,
            embedding=None, # Chroma handles embeddings
            related_entities=None
        )

        # Worldview
        worldview_text = self._prepare_text_from_worldview(worldview)
        all_texts.append(worldview_text)
        all_metadatas.append({'source': 'worldview', 'worldview_id': worldview['id']})
        self.db_manager.add_kb_entry(
            novel_id=novel_id,
            entry_type='worldview',
            content_text=worldview_text,
            embedding=None,
            related_entities=None
        )

        # Plot
        plot_text = self._prepare_text_from_plot(plot)
        all_texts.append(plot_text)
        all_metadatas.append({'source': 'plot_summary', 'plot_id': plot['id']})
        self.db_manager.add_kb_entry(
            novel_id=novel_id,
            entry_type='plot_summary',
            content_text=plot_text,
            embedding=None,
            related_entities=None
        )

        # Characters
        character_texts = self._prepare_texts_from_characters(characters)
        for char_text, char_obj in zip(character_texts, characters):
            all_texts.append(char_text)

            # Handle both Character (DB model) and DetailedCharacterProfile objects
            char_id = char_obj.get('id') or char_obj.get('character_id')
            char_name = char_obj.get('name', 'Unknown')

            all_metadatas.append({'source': 'character_bio', 'character_id': char_id, 'character_name': char_name})
            self.db_manager.add_kb_entry(
                novel_id=novel_id,
                entry_type='character_bio',
                content_text=char_text,
                embedding=None,
                related_entities=[char_name] # Store character name as related entity
            )

        if all_texts:
            print(f"Initializing knowledge base for novel {novel_id} with {len(all_texts)} text chunks.")
            self.kb_manager.add_texts(novel_id, all_texts, metadatas=all_metadatas)
        else:
            print(f"No texts to initialize knowledge base for novel {novel_id}.")

    def update_knowledge_base_with_chapter(self, novel_id: int, chapter: Chapter) -> None:
        # Using a longer snippet for more context
        content_snippet = chapter['content'][:1000] # Increased snippet size
        text_to_add = (
            f"Chapter {chapter['chapter_number']} Title: {chapter['title']}. "
            f"Summary: {chapter['summary']}. "
            f"Content Snippet: {content_snippet}..."
        )
        metadata = {'source': f"chapter_{chapter['chapter_number']}", 'chapter_id': chapter['id'], 'chapter_title': chapter['title']}

        print(f"Updating knowledge base for novel {novel_id} with chapter {chapter['chapter_number']}.")
        self.kb_manager.add_texts(novel_id, [text_to_add], metadatas=[metadata])

        self.db_manager.add_kb_entry(
            novel_id=novel_id,
            entry_type='chapter_summary', # Consistent type
            content_text=text_to_add,
            embedding=None,
            related_entities=[chapter['title']] # Store chapter title
        )

    def get_context_for_chapter(self, novel_id: int, current_plot_focus: str, active_characters_in_scene: Optional[List[str]] = None) -> str:
        if active_characters_in_scene is None:
            active_characters_in_scene = []

        query = f"Current plot focus: {current_plot_focus}."
        if active_characters_in_scene:
            query += f" Characters potentially involved or relevant: {', '.join(active_characters_in_scene)}."

        # Adding more diverse sources to the query for broader context
        query += " Relevant information about world rules, key plot points, character backstories, and previous chapter summaries."

        print(f"Getting context for novel {novel_id} based on query: '{query}'")
        # Retrieve more chunks for potentially richer context, can be refined
        retrieved_chunks = self.kb_manager.retrieve_relevant_chunks(novel_id, query, k=5)

        if not retrieved_chunks:
            print("No relevant chunks found for the query.")
            return "No specific context found in the knowledge base for the current query."

        context_string = "\n\n---\n\n".join(retrieved_chunks)
        print(f"Retrieved context string (length: {len(context_string)} chars)")
        return f"Context for your writing:\n{context_string}"

    def get_knowledge_graph_data(self, novel_id: int) -> Dict[str, Any]:
        """
        Extracts data from the knowledge base suitable for graph visualization.
        This is a basic implementation focusing on characters and their mentions for Phase 2.
        Future enhancements could include relationships, plot event connections, etc.

        Args:
            novel_id: The ID of the novel to extract KB data for.

        Returns:
            A dictionary containing lists of nodes (e.g., characters, events)
            and edges (relationships, interactions).
        """
        print(f"LoreKeeperAgent: Generating knowledge graph data for novel_id {novel_id}")
        nodes = []
        edges = []

        # Ensure DBManager is available (it's part of __init__)
        if not self.db_manager:
            print("LoreKeeperAgent: DBManager not initialized, cannot fetch graph data.")
            return {"nodes": [], "edges": [], "error": "DBManager not initialized"}

        # 1. Get Characters as Nodes
        try:
            # Corrected method name to match DatabaseManager
            characters_db = self.db_manager.get_characters_for_novel(novel_id)
            for char_db in characters_db:
                # characters_db from get_characters_for_novel returns List[DetailedCharacterProfile] (dicts)
                # Ensure we are accessing fields correctly (e.g., char_db['character_id'] or char_db.get('character_id'))
                # The DetailedCharacterProfile TypedDict uses 'character_id', 'name', 'description', 'role_in_story'
                # The actual DB columns are 'id', 'name', 'description', 'role_in_story'
                # The get_characters_for_novel method maps DB 'id' to 'character_id' in the DetailedCharacterProfile
                nodes.append({
                    "id": f"char_{char_db['character_id']}", # Use character_id from DetailedCharacterProfile
                    "label": char_db['name'],
                    "type": "character",
                    "properties": {
                        # 'description' in DetailedCharacterProfile is the full JSON string.
                        # We might want a summary here, or specific fields from it.
                        # For now, let's use the 'appearance_summary' if available, or a generic note.
                        "description": char_db.get('appearance_summary') or char_db.get('background_story', 'No detailed description available in graph properties.'),
                        "role": char_db.get('role_in_story', '')
                    }
                })

            # 2. Basic Edges: Co-occurrence in chapters (placeholder for actual relationship extraction)
            # This is a very simplified approach. True relationship extraction is complex.
            # For now, we're not adding edges to keep it simple for Phase 2 backend support.
            # A more advanced version would parse chapter contents or use LLM to find interactions.
            # Example of how one might add edges if relationships were known:
            # if len(characters_db) >= 2:
            #     edges.append({
            #         "id": f"edge_{nodes[0]['id']}_{nodes[1]['id']}",
            #         "source": nodes[0]['id'],
            #         "target": nodes[1]['id'],
            #         "label": "related_to", # Or "interacted_in_chapter_X"
            #         "properties": {"type": "generic_relation"}
            #     })
            print(f"LoreKeeperAgent: Added {len(characters_db)} character nodes.")

        except Exception as e:
            print(f"LoreKeeperAgent: Error fetching character data for graph: {e}")
            # Continue if possible, or return error if critical

        # 3. Get Plot Events as Nodes (Simplified from PlotChapterDetail)
        try:
            novel = self.db_manager.get_novel_by_id(novel_id)
            plot = None
            if novel and novel.get('active_plot_id') is not None: # Check if 'active_plot_id' exists and is not None
                plot = self.db_manager.get_plot_by_id(novel['active_plot_id'])

            if plot and plot.get('plot_summary'):
                # Assuming plot_summary is JSON string of List[PlotChapterDetail]
                import json # Import json here, as it's used locally
                try:
                    plot_details_list = json.loads(plot['plot_summary']) # This is List[Dict] matching PlotChapterDetail
                    for p_detail_dict in plot_details_list:
                        chapter_num = p_detail_dict.get('chapter_number', 'Unknown')
                        event_summary = p_detail_dict.get('key_events_and_plot_progression', p_detail_dict.get('title', 'Unnamed Event'))
                        nodes.append({
                            "id": f"event_ch{chapter_num}_{str(uuid.uuid4())[:4]}",
                            "label": f"Ch{chapter_num}: {event_summary[:50]}...",
                            "type": "plot_event",
                            "properties": {
                                "chapter": chapter_num,
                                "full_summary": event_summary,
                                "characters_present": p_detail_dict.get("characters_present", [])
                            }
                        })
                    print(f"LoreKeeperAgent: Added {len(plot_details_list)} plot event nodes.")
                except json.JSONDecodeError as je:
                    print(f"LoreKeeperAgent: Error decoding plot_summary JSON: {je}")
                except Exception as ex: # Catch other errors during plot processing
                    print(f"LoreKeeperAgent: Error processing plot details for graph: {ex}")
        except Exception as e:
            print(f"LoreKeeperAgent: Error fetching plot data for graph: {e}")

        return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    print("--- Testing LoreKeeperAgent ---")

    # Ensure OPENAI_API_KEY is set for KnowledgeBaseManager to initialize OpenAIEmbeddings
    # For testing, create a .env file in the root of the project:
    # OPENAI_API_KEY="your_actual_openai_api_key"
    # A dummy key will cause errors when add_texts or retrieve_relevant_chunks is called.
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for testing LoreKeeperAgent...")
        with open(".env", "w") as f:
            # Replace with a real key for actual testing of KB functionality
            f.write("OPENAI_API_KEY=\"sk-dummykeyforlorekeepertesting\"\n")

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummykey" in os.getenv("OPENAI_API_KEY", ""):
        print("WARNING: A valid OPENAI_API_KEY is required for LoreKeeperAgent tests to fully pass, especially for ChromaDB interactions.")
        print("A dummy key will likely lead to authentication errors during embedding generation.")
        # Allow to proceed so other parts can be tested if API call is mocked/avoided later,
        # but real KB functionality will fail.

    test_sql_db_name = "test_lore_keeper_novel.db"
    test_chroma_db_dir = "./test_lore_keeper_chroma_db"

    # Clean up previous test databases and directories
    import shutil
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)
    if os.path.exists(test_chroma_db_dir):
        shutil.rmtree(test_chroma_db_dir)

    # Initialize managers
    # Ensure DatabaseManager creates tables by instantiating it once
    _db_setup_manager = DatabaseManager(db_name=test_sql_db_name)

    try:
        agent = LoreKeeperAgent(db_name=test_sql_db_name, chroma_db_directory=test_chroma_db_dir)
        print("LoreKeeperAgent initialized.")
    except ValueError as e:
        print(f"Failed to initialize LoreKeeperAgent: {e}")
        # Clean up before exiting if agent init fails
        if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
        if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)
        if os.path.exists(".env") and "dummykeyforlorekeepertesting" in open(".env").read(): os.remove(".env")
        exit(1)


    # 1. Create dummy novel and its components
    novel_id_test = agent.db_manager.add_novel("The Quest for the Sunstone", "Fantasy epic")
    print(f"Test Novel created with ID: {novel_id_test}")

    outline_data = Outline(id=agent.db_manager.add_outline(novel_id_test, "A hero seeks a mythical artifact to save their village."),
                           novel_id=novel_id_test, overview_text="A hero seeks a mythical artifact to save their village.",
                           creation_date=datetime.now(timezone.utc).isoformat())

    worldview_data = WorldView(id=agent.db_manager.add_worldview(novel_id_test, "A land plagued by a spreading darkness, magic is rare."),
                               novel_id=novel_id_test, description_text="A land plagued by a spreading darkness, magic is rare.",
                               creation_date=datetime.now(timezone.utc).isoformat())

    plot_data = Plot(id=agent.db_manager.add_plot(novel_id_test, "The hero gathers allies, overcomes trials, and confronts the shadow entity."),
                     novel_id=novel_id_test, plot_summary="The hero gathers allies, overcomes trials, and confronts the shadow entity.",
                     creation_date=datetime.now(timezone.utc).isoformat())

    char1_id = agent.db_manager.add_character(novel_id_test, "Elara", "A skilled archer with a mysterious past.", "Protagonist")
    char2_id = agent.db_manager.add_character(novel_id_test, "Gorok", "A grumpy dwarf warrior, loyal to Elara.", "Ally")
    characters_data = agent.db_manager.get_characters_for_novel(novel_id_test)

    print(f"Dummy data created for Novel ID {novel_id_test}: Outline, Worldview, Plot, {len(characters_data)} Characters.")

    # 2. Initialize Knowledge Base
    print("\nInitializing knowledge base...")
    try:
        agent.initialize_knowledge_base(novel_id_test, outline_data, worldview_data, plot_data, characters_data)
        # Verify ChromaDB files
        assert os.path.exists(test_chroma_db_dir), "Chroma DB directory not created after init."
        chroma_files = os.listdir(os.path.join(test_chroma_db_dir, agent.kb_manager._get_collection_name(novel_id_test)))
        assert any(f.endswith('.sqlite3') for f in chroma_files), "Chroma .sqlite3 file not found after init." # Langchain Chroma default
        print("Knowledge base initialized. Chroma files seem to be present.")

        # Verify SQL KB entries
        kb_entries_sql = agent.db_manager.get_kb_entries_for_novel(novel_id_test)
        print(f"Found {len(kb_entries_sql)} entries in SQL knowledge_base_entries table.")
        # Expected: 1 outline + 1 worldview + 1 plot + N characters
        assert len(kb_entries_sql) == (3 + len(characters_data)), "Incorrect number of KB entries in SQL DB after init."
        print("SQL KB entries count verified.")

    except Exception as e:
        print(f"ERROR during initialize_knowledge_base: {e}")
        print("This is likely due to an invalid/dummy OPENAI_API_KEY.")
        # Fall through to cleanup, but this part of the test effectively failed.


    # 3. Add a chapter
    print("\nAdding a chapter to knowledge base...")
    chapter_data = Chapter(
        id=agent.db_manager.add_chapter(novel_id_test, 1, "The Shadow Creeps", "Elara's village is attacked...", "Elara decides to seek the Sunstone."),
        novel_id=novel_id_test, chapter_number=1, title="The Shadow Creeps",
        content="The village of Oakhaven was peaceful until the shadows came. Elara, watching from the forest edge, knew she had to act. The Sunstone was their only hope, a legend whispered by the elders.",
        summary="Elara's village is attacked by shadows, prompting her to seek the legendary Sunstone.",
        creation_date=datetime.now(timezone.utc).isoformat()
    )
    try:
        agent.update_knowledge_base_with_chapter(novel_id_test, chapter_data)
        kb_entries_after_chap = agent.db_manager.get_kb_entries_for_novel(novel_id_test)
        print(f"Found {len(kb_entries_after_chap)} entries in SQL KB after chapter update.")
        assert len(kb_entries_after_chap) == (3 + len(characters_data) + 1), "Incorrect number of SQL KB entries after chapter update."
        print("Chapter added to KB. SQL entry count verified.")
    except Exception as e:
        print(f"ERROR during update_knowledge_base_with_chapter: {e}")
        print("This is likely due to an invalid/dummy OPENAI_API_KEY.")

    # 4. Get context for chapter
    print("\nGetting context for a chapter scenario...")
    plot_focus = "Elara and Gorok are about to enter the Whispering Woods to find a map."
    active_chars = ["Elara", "Gorok"]
    try:
        context = agent.get_context_for_chapter(novel_id_test, plot_focus, active_chars)
        print("\nRetrieved Context:")
        print(context)
        assert context is not None
        if "dummykey" not in os.getenv("OPENAI_API_KEY",""): # Only assert content if real key might be used
             assert "Elara" in context or "Gorok" in context or "Sunstone" in context, "Context seems unrelated or empty."
        else:
            print("Skipping content assertion for context due to dummy API key.")

    except Exception as e:
        print(f"ERROR during get_context_for_chapter: {e}")
        print("This is likely due to an invalid/dummy OPENAI_API_KEY or an empty Chroma collection from prior errors.")


    # 5. Clean up
    print("\nCleaning up test databases and directories...")
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)
        print(f"Removed SQL DB: {test_sql_db_name}")
    if os.path.exists(test_chroma_db_dir):
        shutil.rmtree(test_chroma_db_dir)
        print(f"Removed Chroma DB directory: {test_chroma_db_dir}")

    if os.path.exists(".env") and "dummykeyforlorekeepertesting" in open(".env").read():
        print("Removing dummy .env file for LoreKeeperAgent test...")
        os.remove(".env")

    print("--- LoreKeeperAgent Test Finished ---")
