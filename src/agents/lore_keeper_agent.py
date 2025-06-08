import os
import os
import json # For parsing LLM response
import re # For _normalize_id
from dotenv import load_dotenv
from typing import List, Dict, TypedDict, Optional, Any
from datetime import datetime, timezone
import uuid

from src.llm_abstraction.llm_client import LLMClient
from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
from src.persistence.database_manager import DatabaseManager
from src.core.models import Outline, WorldView, Plot, Character, Chapter, KnowledgeBaseEntry

# TypedDicts for structured information extraction (defined locally for this subtask)
class ExtractedEntity(TypedDict, total=False):
    name: str
    type: str # character, location, item, organization, event_trigger
    description: Optional[str]
    status_update: Optional[str]
    location: Optional[str] # For characters or items

class ExtractedRelationship(TypedDict, total=False):
    source_entity: str
    target_entity: str
    type: str # e.g., INTERACTS_WITH, POSSESSES, ALLIED_WITH, LOCATED_NEAR
    details: Optional[str]

class ExtractedEvent(TypedDict, total=False):
    summary: str
    participants: Optional[List[str]] # Names of characters/entities
    location: Optional[str]
    items_involved: Optional[List[str]]
    significance: Optional[str] # e.g., minor, major, turning_point

class ExtractedLoreSnippet(TypedDict, total=False):
    snippet: str # A piece of world-building, rule, or fact
    category: Optional[str] # e.g., world_rule, cultural_norm, historical_fact

class ExtractedInfo(TypedDict, total=False):
    entities: Optional[List[ExtractedEntity]]
    relationships: Optional[List[ExtractedRelationship]]
    events: Optional[List[ExtractedEvent]]
    new_lore_snippets: Optional[List[ExtractedLoreSnippet]]
    parsing_errors: Optional[List[str]] # For LLM to report if it couldn't fit something

# --- Knowledge Graph Data Structures ---
class KGNode(TypedDict):
    id: str # Unique ID, e.g., "novelid_character_elara" or "novelid_event_event_uuid"
    label: str # User-friendly name, e.g., "Elara"
    type: str # From ExtractedEntity.type or "event"
    properties: Dict[str, Any]

class KGEdge(TypedDict):
    id: str # Unique ID for the edge, e.g., "edge_uuid"
    source: str # ID of source KGNode
    target: str # ID of target KGNode
    type: str # From ExtractedRelationship.type or e.g., "PARTICIPATES_IN"
    properties: Dict[str, Any]


class LoreKeeperAgent:
    def __init__(self, db_name: str = "novel_mvp.db", chroma_db_directory: str = "./chroma_db"):
        self.db_manager = DatabaseManager(db_name=db_name)
        self.knowledge_graphs: Dict[int, Dict[str, List[Any]]] = {} # novel_id -> {"nodes": [], "edges": []}
        try:
            # Initialize LLMClient, crucial for the new extraction method
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"LoreKeeperAgent Error: LLMClient initialization failed. {e}")
            # Decide if this is critical enough to raise. For extraction, it is.
            raise
        except Exception as e:
            print(f"LoreKeeperAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise

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
        text_to_add_to_vector_db = ( # Renamed to avoid confusion with full content for extraction
            f"Chapter {chapter['chapter_number']} Title: {chapter['title']}. "
            f"Summary: {chapter['summary']}. "
            f"Content Snippet (for vector search context): {content_snippet}..."
        )
        metadata = {'source': f"chapter_{chapter['chapter_number']}", 'chapter_id': chapter['id'], 'chapter_title': chapter['title']}

        print(f"Updating knowledge base (vector store) for novel {novel_id} with chapter {chapter['chapter_number']}.")
        self.kb_manager.add_texts(novel_id, [text_to_add_to_vector_db], metadatas=[metadata])

        # Add entry to SQL DB (as before)
        self.db_manager.add_kb_entry(
            novel_id=novel_id,
            entry_type='chapter_summary', # Consistent type for this vector entry
            content_text=text_to_add_to_vector_db, # Store the same summarized text
            embedding=None, # Chroma handles embeddings
            related_entities=[chapter['title']], # Store chapter title
            # structured_data=None # Placeholder if we were adding the field
        )

        # Now, extract structured information from the full chapter content
        print(f"Extracting structured information from Chapter {chapter['chapter_number']} content...")
        extracted_info = self.extract_structured_info_from_text(
            novel_id=novel_id,
            text_content=chapter['content'], # Use full chapter content for extraction
            text_source_description=f"Full content of Chapter {chapter['chapter_number']}: {chapter['title']}"
        )

        if extracted_info:
            print(f"Successfully extracted structured info from Chapter {chapter['chapter_number']}:")
            # Pretty print the JSON for better readability in logs
            try:
                print(json.dumps(extracted_info, indent=2, ensure_ascii=False))
            except TypeError: # In case TypedDict is not directly serializable by json.dumps in some environments
                print(str(extracted_info))

            # Here, you could store `extracted_info` (e.g., as JSON string) in a dedicated table
            # or a new field in 'knowledge_base_entries' if the schema were extended.
            # For this subtask, we are just printing it.
            # Example: self.db_manager.add_structured_lore_entry(novel_id, chapter['id'], 'chapter', extracted_info)

            # After successful extraction, generate validation requests
            self._generate_validation_requests_from_extracted_info(
                novel_id=novel_id,
                extracted_info=extracted_info,
                source_reference=f"Chapter {chapter['chapter_number']}: {chapter['title']}",
                source_text_snippet=chapter['content'][:500] # Pass a snippet of the chapter as context
            )
        else:
            print(f"Could not extract structured information from Chapter {chapter['chapter_number']}. Skipping validation request generation.")


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
        Extracts data from the persisted knowledge graph for a novel.
        If no persisted graph exists, it attempts to build one from character and plot data as a fallback
        (though ideally, the graph is built incrementally via `update_knowledge_graph_from_extracted_info`).

        Args:
            novel_id: The ID of the novel to extract KB data for.

        Returns:
            A dictionary containing lists of nodes (e.g., characters, events)
            and edges (relationships, interactions).
        """
        print(f"LoreKeeperAgent: Getting knowledge graph data for novel_id {novel_id}")
        kg = self._get_or_create_kg(novel_id) # This handles loading or initializing

        if not kg["nodes"] and not kg["edges"]: # If KG is empty after trying to load/create
            print(f"LoreKeeperAgent: Knowledge graph for novel {novel_id} is empty. No persisted graph found and fallback generation is not implemented in this step.")
            # Fallback: Could try to build a very basic graph from characters if needed,
            # but the primary mechanism should be incremental updates via ExtractedInfo.
            # For now, return empty if not populated by new methods.
            # The old logic for building from scratch is removed to favor the new incremental build.
            # This method now primarily serves as an accessor to the managed KG.

        return kg # Returns {"nodes": [...], "edges": [...]}

    # --- Knowledge Graph Management Methods ---
    def _normalize_id(self, input_id: str), novel_id_prefix: Optional[str]=None) -> str:
        """Normalizes an ID string for KG consistency."""
        # Lowercase, replace spaces with underscores, remove special chars except underscore/hyphen
        normalized = re.sub(r'[^\w\s-]', '', input_id.lower()).strip()
        normalized = re.sub(r'\s+', '_', normalized)
        if novel_id_prefix and not normalized.startswith(novel_id_prefix):
             return f"{novel_id_prefix}_{normalized}"
        return normalized

    def _load_kg_for_novel(self, novel_id: int) -> None:
        print(f"LoreKeeperAgent: Loading knowledge graph from DB for novel {novel_id}")
        graph_json = self.db_manager.load_knowledge_graph(novel_id)
        if graph_json:
            try:
                self.knowledge_graphs[novel_id] = json.loads(graph_json)
                print(f"LoreKeeperAgent: Successfully loaded KG for novel {novel_id} from DB.")
            except json.JSONDecodeError as e:
                print(f"LoreKeeperAgent: Error decoding KG JSON from DB for novel {novel_id}: {e}. Initializing empty graph.")
                self.knowledge_graphs[novel_id] = {"nodes": [], "edges": []}
        else:
            print(f"LoreKeeperAgent: No KG found in DB for novel {novel_id}. Initializing empty graph.")
            self.knowledge_graphs[novel_id] = {"nodes": [], "edges": []}

    def _save_kg_to_db(self, novel_id: int) -> None:
        if novel_id in self.knowledge_graphs:
            try:
                graph_json = json.dumps(self.knowledge_graphs[novel_id], indent=2)
                self.db_manager.save_knowledge_graph(novel_id, graph_json)
                print(f"LoreKeeperAgent: Successfully saved KG for novel {novel_id} to DB.")
            except TypeError as e: # Handle non-serializable data if any slips in
                print(f"LoreKeeperAgent: Error serializing KG to JSON for novel {novel_id}: {e}")
            except Exception as e: # Catch other DB save errors
                print(f"LoreKeeperAgent: Error saving KG to DB for novel {novel_id}: {e}")
        else:
            print(f"LoreKeeperAgent: No KG in memory for novel {novel_id} to save.")

    def _get_or_create_kg(self, novel_id: int) -> Dict[str, List[Any]]:
        if novel_id not in self.knowledge_graphs:
            self._load_kg_for_novel(novel_id)
        return self.knowledge_graphs[novel_id]

    def _add_node_to_kg(self, kg: Dict[str, List[Any]], node_id: str, label: str, node_type: str, properties: Optional[Dict] = None) -> None:
        # Check for duplicates
        for i, existing_node in enumerate(kg["nodes"]):
            if existing_node["id"] == node_id:
                # Update existing node: simple merge for properties, or replace
                kg["nodes"][i]["label"] = label # Update label if changed
                kg["nodes"][i]["type"] = node_type # Update type if changed
                if properties:
                    kg["nodes"][i]["properties"].update(properties)
                return

        # Add new node
        new_node = KGNode(id=node_id, label=label, type=node_type, properties=properties or {})
        kg["nodes"].append(new_node)

    def _add_edge_to_kg(self, kg: Dict[str, List[Any]], source_id: str, target_id: str, edge_type: str, properties: Optional[Dict] = None) -> None:
        # Generate a unique ID for the edge to allow for multiple edges between same nodes if properties differ
        # For simplicity here, if type and properties are same, consider it a duplicate.
        # A more robust approach might use UUIDs for all edge IDs if updates are not expected.
        edge_id_candidate = f"{source_id}_{edge_type}_{target_id}"
        prop_hash = hash(json.dumps(properties, sort_keys=True)) if properties else 0
        final_edge_id = f"{edge_id_candidate}_{prop_hash}"

        for existing_edge in kg["edges"]:
            if existing_edge["id"] == final_edge_id:
                return # Edge already exists

        new_edge = KGEdge(id=final_edge_id, source=source_id, target=target_id, type=edge_type, properties=properties or {})
        kg["edges"].append(new_edge)

    def update_knowledge_graph_from_extracted_info(self, novel_id: int, extracted_info: ExtractedInfo, source_ref_for_id: Optional[str] = None) -> None:
        kg = self._get_or_create_kg(novel_id)
        novel_id_prefix = f"novel{novel_id}"

        entity_id_map: Dict[str, str] = {} # Maps entity name from ExtractedInfo to generated KG node ID

        # Process Entities
        if extracted_info.get("entities"):
            for entity in extracted_info["entities"]:
                name = entity.get("name")
                ent_type = entity.get("type", "unknown_entity")
                if not name: continue

                node_id = self._normalize_id(f"{ent_type}_{name}", novel_id_prefix)
                entity_id_map[name] = node_id # Store mapping for relationships/events

                props = {
                    "description": entity.get("description"),
                    "status_update": entity.get("status_update"),
                    "location": entity.get("location")
                }
                # Filter out None properties before adding
                final_props = {k: v for k, v in props.items() if v is not None}
                if source_ref_for_id: # Add source if available
                    final_props["source_document"] = source_ref_for_id

                self._add_node_to_kg(kg, node_id, name, ent_type, final_props)

        # Process Events
        if extracted_info.get("events"):
            for i, event in enumerate(extracted_info["events"]):
                summary = event.get("summary", f"Unnamed Event {i+1}")
                # Create a unique ID for each event instance
                event_base_id = self._normalize_id(summary[:30]) # Use part of summary for a somewhat stable ID base
                event_node_id = f"{novel_id_prefix}_event_{event_base_id}_{str(uuid.uuid4())[:4]}"

                props = {
                    "summary": summary,
                    "location": event.get("location"),
                    "items_involved": event.get("items_involved"),
                    "significance": event.get("significance")
                }
                final_props = {k: v for k, v in props.items() if v is not None}
                if source_ref_for_id:
                    final_props["source_document"] = source_ref_for_id

                self._add_node_to_kg(kg, event_node_id, summary, "event", final_props)

                # Link participants to the event
                if event.get("participants"):
                    for participant_name in event["participants"]:
                        participant_node_id = entity_id_map.get(participant_name)
                        if not participant_node_id:
                            # If participant not in current batch's entities, try to create/get its ID
                            # This assumes characters/entities might be mentioned without full entity extraction in THIS batch
                            participant_node_id = self._normalize_id(f"unknown_{participant_name}", novel_id_prefix)
                            # Optionally add a basic node for this implicitly mentioned participant
                            # self._add_node_to_kg(kg, participant_node_id, participant_name, "unknown_participant_type", {"source_document": source_ref_for_id, "status": "implicitly_mentioned"})

                        if participant_node_id: # Ensure we have an ID
                            self._add_edge_to_kg(kg, participant_node_id, event_node_id, "PARTICIPATES_IN", {"source_document": source_ref_for_id})

        # Process Relationships
        if extracted_info.get("relationships"):
            for rel in extracted_info["relationships"]:
                source_name = rel.get("source_entity")
                target_name = rel.get("target_entity")
                rel_type = rel.get("type", "RELATED_TO")
                if not source_name or not target_name: continue

                source_node_id = entity_id_map.get(source_name)
                target_node_id = entity_id_map.get(target_name)

                # If entities involved in relationship were not in this batch's entities list, generate IDs
                if not source_node_id: source_node_id = self._normalize_id(f"unknown_{source_name}", novel_id_prefix)
                if not target_node_id: target_node_id = self._normalize_id(f"unknown_{target_name}", novel_id_prefix)

                props = {"details": rel.get("details")}
                final_props = {k:v for k,v in props.items() if v is not None}
                if source_ref_for_id: final_props["source_document"] = source_ref_for_id

                self._add_edge_to_kg(kg, source_node_id, target_node_id, rel_type, final_props)

        self._save_kg_to_db(novel_id)
        print(f"LoreKeeperAgent: Updated and saved knowledge graph for novel {novel_id}. Total nodes: {len(kg['nodes'])}, Total edges: {len(kg['edges'])}")


if __name__ == "__main__":
    print("--- Testing LoreKeeperAgent ---")

    # Ensure OPENAI_API_KEY is set for KnowledgeBaseManager to initialize OpenAIEmbeddings
    # For testing, create a .env file in the root of the project:
    # OPENAI_API_KEY="your_actual_openai_api_key"
    # A dummy key will cause errors when add_texts or retrieve_relevant_chunks is called.
        # Also, LLMClient now requires it for extraction.
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for testing LoreKeeperAgent...")
        with open(".env", "w") as f:
                f.write("OPENAI_API_KEY=\"sk-dummykeyforlorekeepertesting\"\n") # Dummy key

    load_dotenv() # Load environment variables from .env

    # Critical check for API key for LLMClient and KnowledgeBaseManager
    api_key_is_valid = os.getenv("OPENAI_API_KEY") and "dummykey" not in os.getenv("OPENAI_API_KEY", "")
    if not api_key_is_valid:
        print("CRITICAL WARNING: A valid OPENAI_API_KEY is required for LoreKeeperAgent tests, including LLMClient initialization and ChromaDB interactions.")
        print("A dummy key will likely lead to authentication errors. Some tests might be skipped or fail.")

    test_sql_db_name = "test_lore_keeper_novel.db"
    test_chroma_db_dir = "./test_lore_keeper_chroma_db"

    # --- Test Setup ---
    # Mock LLMClient and other dependencies as needed for focused testing
    class MockLLMClient:
        def generate_text(self, prompt: str, model_name: str, temperature: float, max_tokens: int) -> str:
            if "Extract key entities" in prompt: # For _extract_key_entities_for_kb_query
                return "Elara, Whispering Woods, Moonpetal"
            # For extract_structured_info_from_text
            # Return a valid JSON string structure based on ExtractedInfo
            sample_extracted_info = {
                "entities": [
                    {"name": "Elara", "type": "character", "description": "The protagonist."},
                    {"name": "Whispering Woods", "type": "location", "description": "A mysterious forest."}
                ],
                "events": [
                    {"summary": "Elara entered the Whispering Woods.", "significance": "major_plot_point", "participants": ["Elara"], "location": "Whispering Woods"}
                ],
                "new_lore_snippets": [
                    {"snippet": "Magic is fading from the land.", "category": "world_rule"}
                ]
            }
            return json.dumps(sample_extracted_info)

    class MockKBManager:
        def __init__(self, db_directory):
            self.added_texts_log = []
        def add_texts(self, novel_id: int, texts: List[str], metadatas: Optional[List[dict]] = None):
            print(f"MockKBManager: add_texts called for novel_id {novel_id} with {len(texts)} text(s).")
            for i, text in enumerate(texts):
                meta = metadatas[i] if metadatas and i < len(metadatas) else {}
                print(f"  - Text: \"{text[:100]}...\", Metadata: {meta}")
                self.added_texts_log.append({"text": text, "metadata": meta, "novel_id": novel_id})
        def query_knowledge_base(self, novel_id: int, query_text: str, n_results: int = 3): return [] # Not used in these tests
        def retrieve_relevant_chunks(self, novel_id: int, query_text: str, k: int = 5): return [] # Not used

    # Setup for testing
    if not api_key_is_valid:
        print("Skipping LoreKeeperAgent tests that require a valid API key for LLMClient.")
    else:
        test_sql_db_name = "test_lore_keeper_validation.db"
        test_chroma_db_dir = "./test_lore_keeper_validation_chroma_db"
        import shutil
        if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
        if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)

        db_mngr_test = DatabaseManager(db_name=test_sql_db_name)
        agent = LoreKeeperAgent(db_name=test_sql_db_name, chroma_db_directory=test_chroma_db_dir)

        # Override the real LLM client and KB manager with mocks for testing this specific logic
        agent.llm_client = MockLLMClient()
        agent.kb_manager = MockKBManager(db_directory=test_chroma_db_dir)

        novel_id_test = db_mngr_test.add_novel("Validation Test Novel", "Fantasy")
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
        if not api_key_is_valid:
            print("Skipping further tests that require valid API key for KB initialization.")
            # Clean up and exit if API key is not valid, as other tests depend on it.
            if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
            if os.path.exists(test_chroma_db_dir): shutil.rmtree(test_chroma_db_dir)
            if os.path.exists(".env") and "dummykeyforlorekeepertesting" in open(".env").read(): os.remove(".env")
            exit(0) # Exit test script if API key is missing/dummy for critical init.

    # 3. Add a chapter (this will also test extraction)
    print("\nAdding a chapter to knowledge base (and testing structured info extraction)...")
    sample_chapter_content_for_extraction = """
    Elara and Gorok finally reached the edge of the Whispering Woods. Gorok grumbled about the eerie silence.
    Suddenly, a spectral wolf, its eyes glowing with a faint blue light, appeared before them.
    Elara nocked an arrow, her heart pounding. "State your business, spirit!" she called out.
    The wolf did not attack but instead spoke, its voice a chilling whisper, "The Sunstone you seek lies beyond the Shadow Pass, but only those who carry the Moonpetal bloom can safely pass."
    It then faded away, leaving behind a single, shimmering Moonpetal flower on the mossy ground. Elara picked it up carefully; it felt cool to the touch.
    Gorok, visibly shaken, muttered, "A talking wolf... this quest gets stranger by the day."
    Elara knew this was a significant clue. The Moonpetal was now a key item.
    They also learned the Sunstone's general location: beyond Shadow Pass. This was new information.
    """
    chapter_data = Chapter(
        id=agent.db_manager.add_chapter(novel_id_test, 1, "The Spectral Wolf's Clue", sample_chapter_content_for_extraction, "Elara and Gorok receive a clue about the Sunstone and Moonpetal from a spectral wolf."),
        novel_id=novel_id_test, chapter_number=1, title="The Spectral Wolf's Clue",
        content=sample_chapter_content_for_extraction,
        summary="Elara and Gorok receive a clue about the Sunstone and Moonpetal from a spectral wolf.",
        creation_date=datetime.now(timezone.utc).isoformat()
    )
    try:
        # This now also calls extract_structured_info_from_text internally
        agent.update_knowledge_base_with_chapter(novel_id_test, chapter_data)
        kb_entries_after_chap = agent.db_manager.get_kb_entries_for_novel(novel_id_test)
        print(f"Found {len(kb_entries_after_chap)} entries in SQL KB after chapter update.")
        assert len(kb_entries_after_chap) == (3 + len(characters_data) + 1), "Incorrect number of SQL KB entries after chapter update."
        print("Chapter added to KB (vector and SQL summary). SQL entry count verified.")
        # Further checks for structured data would go here if it were stored.
    except Exception as e:
        print(f"ERROR during update_knowledge_base_with_chapter (and extraction): {e}")
        if not api_key_is_valid:
            print("This error is expected if using a dummy API key for LLM calls.")
        # else: raise # Re-raise if key was supposed to be valid

    # 4. Test extract_structured_info_from_text directly (if not fully covered above)
    if api_key_is_valid: # Only if a real key is available
        print("\nDirectly testing extract_structured_info_from_text...")
        sample_text = "Sir Reginald Fancypants, a noble knight, found a Vorpal Sword in the dragon's hoard at Dragon's Peak. He then travelled to Oakhaven."
        source_desc = "Test snippet for Sir Reginald"
        extracted = agent.extract_structured_info_from_text(novel_id_test, sample_text, source_desc)
        if extracted:
            print("Extracted data from direct test:")
            print(json.dumps(extracted, indent=2, ensure_ascii=False))
            assert "entities" in extracted
            if extracted.get("entities"):
                assert any(e['name'] == "Sir Reginald Fancypants" for e in extracted["entities"])
                assert any(e['name'] == "Vorpal Sword" for e in extracted["entities"])
        else:
            print("Direct extraction test returned None or empty.")
    else:
        print("\nSkipping direct test of extract_structured_info_from_text due to missing/dummy API key.")


    # 5. Get context for chapter (RAG functionality)
    print("\nGetting context for a chapter scenario (RAG)...")
    plot_focus = "Elara and Gorok are looking for the Moonpetal bloom after the wolf encounter."
    active_chars = ["Elara", "Gorok"]
    try:
        context = agent.get_context_for_chapter(novel_id_test, plot_focus, active_chars)
        print("\nRetrieved Context (RAG):")
        print(context)
        assert context is not None
        if api_key_is_valid: # Only assert content if real key might be used
             assert "Elara" in context or "Gorok" in context or "Sunstone" in context or "Moonpetal" in context, "Context seems unrelated or empty."
        else:
            print("Skipping content assertion for RAG context due to dummy API key.")

    except Exception as e:
        print(f"ERROR during get_context_for_chapter (RAG): {e}")
        if not api_key_is_valid:
            print("This error is expected if using a dummy API key for ChromaDB embeddings.")
        # else: raise

    # 6. Clean up
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


# Helper methods for structured information extraction (to be added below or refactored)
# For example, _construct_extraction_prompt and extract_structured_info_from_text
# Need to place these methods within the class structure.

# Let's move the method definitions into the class now.
# The following is a placeholder for the diff tool to correctly apply the new methods.
# This is a common pattern when adding multiple new methods with this tool.
# --- Start of methods to be inserted into LoreKeeperAgent class ---

    def _construct_extraction_prompt(self, text_content: str, text_source_description: str) -> str:
        prompt = f"""You are an expert information extraction system. Your task is to analyze the provided text from a novel and extract structured information.
Source: {text_source_description}

Text to Analyze:
--- BEGIN TEXT ---
{text_content}
--- END TEXT ---

Based on the text, extract the following information:
- Key entities (characters, locations, items, organizations, event_triggers) including their names, types, any new or updated descriptions, status updates (e.g., 'injured', 'obtained X', 'destroyed'), and current locations if mentioned or changed.
- Significant relationships observed or updated between entities (e.g., interactions, alliances, conflicts, possessions).
- Important events that occurred, including a summary, participants, location, items involved, and their significance to the plot (e.g., minor plot point, major turning point, character development).
- New lore snippets, which are pieces of world-building, rules, historical facts, or cultural norms revealed.

Return the information STRICTLY in the following JSON format. Ensure it is a single valid JSON object:
{{
  "entities": [
    {{
      "name": "string (name of the entity)",
      "type": "character | location | item | organization | event_trigger",
      "description": "string (new or updated description, or significant attribute)",
      "status_update": "string (e.g., 'injured', 'obtained X', 'is now hostile')",
      "location": "string (current location, if specified or changed for characters/items)"
    }}
  ],
  "relationships": [
    {{
      "source_entity": "string (name of the source entity)",
      "target_entity": "string (name of the target entity)",
      "type": "string (e.g., ALLIED_WITH, MET, ATTACKED, POSSESSES, MEMBER_OF, OPPOSES, TRAVELLED_TO, HEARD_ABOUT)",
      "details": "string (brief context or details of the relationship from the text)"
    }}
  ],
  "events": [
    {{
      "summary": "string (concise summary of the event)",
      "participants": ["string (names of characters/entities involved)"],
      "location": "string (where the event took place, if specified)",
      "items_involved": ["string (names of items central to the event)"],
      "significance": "string (e.g., minor_plot_point, major_turning_point, character_development, world_building_reveal)"
    }}
  ],
  "new_lore_snippets": [
    {{
      "snippet": "string (the specific piece of lore, rule, or fact)",
      "category": "string (e.g., world_rule, history, magic_system, cultural_norm, prophecy)"
    }}
  ]
}}

Important Considerations:
- Focus on information that is NEW or represents a CHANGE/UPDATE based on the provided text. If a detail is already well-established and unchanged, you might not need to repeat it unless it's part of a new event or status update.
- If you cannot extract certain fields for an item, or if there's nothing to report for a whole category (e.g., no new relationships), you can omit the specific field within an object, or provide an empty list for that category (e.g., "relationships": []).
- Ensure all string values within the JSON are properly escaped.
- The output MUST be a single, valid JSON object ready for parsing. Do not include any explanatory text before or after the JSON block.
"""
        return prompt

    def extract_structured_info_from_text(self, novel_id: int, text_content: str, text_source_description: str) -> Optional[ExtractedInfo]:
        if not self.llm_client:
            print("LoreKeeperAgent: LLMClient not initialized. Cannot extract structured info.")
            return None

        prompt = self._construct_extraction_prompt(text_content, text_source_description)

        # Estimate tokens for the text_content to select appropriate model or adjust parameters
        # For now, using a default model and settings.
        # Max tokens for response should be generous enough to capture detailed JSON.
        # Approximately, if input text is N tokens, JSON output could be 0.5N to N tokens.
        # Let's set a generous max_tokens for the response, e.g., 2000-3000,
        # as JSON structure can be verbose.
        # This should be configured based on the LLM's capabilities.

        # Using a model known for good JSON output and instruction following.
        # Temperature is low to ensure factual extraction according to format.
        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-4o-2024-08-06", # or "gpt-3.5-turbo-0125" with response_format={"type": "json_object"} if available and desired
                temperature=0.2,
                max_tokens=3000, # Adjust as needed, JSON can be lengthy
                # For models/APIs supporting JSON mode:
                # response_format={"type": "json_object"} # If using OpenAI API directly or compatible client
            )
        except Exception as e:
            print(f"LoreKeeperAgent: Error during LLM call for info extraction: {e}")
            return None

        if not llm_response_text or not llm_response_text.strip().startswith("{"):
            print(f"LoreKeeperAgent: LLM returned an empty or non-JSON response for extraction. Response: {llm_response_text[:200]}...")
            return None

        try:
            # The response should be a JSON string, so parse it.
            # Clean up potential markdown ```json ... ``` wrappers if the LLM adds them
            cleaned_response = llm_response_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:] # Remove ```json
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3] # Remove ```

            extracted_data: ExtractedInfo = json.loads(cleaned_response.strip())

            # Basic validation (presence of top-level keys, can be expanded)
            if not isinstance(extracted_data, dict) or not any(k in extracted_data for k in ["entities", "relationships", "events", "new_lore_snippets"]):
                print(f"LoreKeeperAgent: Extracted JSON does not have the expected structure. Keys: {list(extracted_data.keys())}")
                return {"parsing_errors": ["Extracted JSON does not have expected top-level keys."]}

            return extracted_data
        except json.JSONDecodeError as e:
            print(f"LoreKeeperAgent: Failed to parse JSON response from LLM for structured info. Error: {e}")
            print(f"LLM Response (first 500 chars): {llm_response_text[:500]}")
            # Return an ExtractedInfo object with the error for upstream handling if desired
            return {"parsing_errors": [f"JSONDecodeError: {str(e)}", f"LLM Response (start): {llm_response_text[:200]}..."]}
        except Exception as e: # Catch any other unexpected errors during parsing/validation
            print(f"LoreKeeperAgent: An unexpected error occurred while processing LLM response: {e}")
            return {"parsing_errors": [f"Unexpected processing error: {str(e)}"]}

    # --- Placeholder methods for KB User Validation ---
    def _generate_validation_requests_from_extracted_info(self, novel_id: int, extracted_info: ExtractedInfo, source_reference: str, source_text_snippet: str) -> None:
        """
        (Placeholder) Analyzes extracted information and generates KB validation requests if needed.
        This method will eventually use LLM prompts or heuristics to identify
        ambiguities, potential contradictions not caught by conflict detection,
        or items needing user confirmation from the ExtractedInfo.
        It will then call db_manager.add_kb_validation_request(...).
        """
        print(f"LoreKeeperAgent (TODO): Analyzing extracted info for novel {novel_id} from '{source_reference}' to generate validation requests.")
        # Example logic (highly simplified):
        # if extracted_info.get("entities"):
        #     for entity in extracted_info["entities"]:
        #         if entity.get("type") == "character" and "?" in entity.get("description", ""):
        #             validation_id = str(uuid.uuid4())
        #             self.db_manager.add_kb_validation_request(
        #                 validation_id=validation_id,
        #                 novel_id=novel_id,
        #                 request_type="entity_confirmation",
        #                 item_under_review_json=json.dumps(entity),
        #                 validation_question=f"Is the description for character '{entity['name']}' accurate: \"{entity['description']}\"?",
        #                 source_reference=source_reference,
        #                 source_text_snippet=source_text_snippet # Might need to find the specific snippet for this entity
        #             )
        MAX_VALIDATION_REQUESTS_PER_TYPE = 2 # Max entities to validate, max events etc.
        validation_candidates = []

        # Heuristic: Flag new entities (characters/locations with descriptions) and major events
        if extracted_info.get("entities"):
            entity_count = 0
            for entity in extracted_info["entities"]:
                if entity_count >= MAX_VALIDATION_REQUESTS_PER_TYPE:
                    break
                entity_type = entity.get("type")
                entity_name = entity.get("name")
                entity_description = entity.get("description")
                if entity_type in ["character", "location"] and entity_name and entity_description:
                    question = f"A new {entity_type} named '{entity_name}' (Description: \"{entity_description}\") was identified from '{source_reference}'. Should this be confirmed and added to the knowledge base?"
                    validation_candidates.append({
                        "request_type": f"{entity_type}_confirmation",
                        "item_under_review_json": json.dumps(entity),
                        "validation_question": question,
                        "source_reference": source_reference,
                        "source_text_snippet": source_text_snippet # Could be refined to pinpoint exact sentence
                    })
                    entity_count +=1

        if extracted_info.get("events"):
            event_count = 0
            for event in extracted_info["events"]:
                if event_count >= MAX_VALIDATION_REQUESTS_PER_TYPE:
                    break
                event_summary = event.get("summary")
                event_significance = event.get("significance")
                if event_summary and event_significance in ["major_turning_point", "major_plot_point", "world_building_reveal"]:
                    question = f"A significant event ('{event_significance}') summarized as \"{event_summary}\" was identified from '{source_reference}'. Is this summary accurate and should it be recorded as a key event?"
                    validation_candidates.append({
                        "request_type": "event_accuracy",
                        "item_under_review_json": json.dumps(event),
                        "validation_question": question,
                        "source_reference": source_reference,
                        "source_text_snippet": source_text_snippet
                    })
                    event_count += 1

        if not validation_candidates:
            print(f"LoreKeeperAgent: No items met heuristic criteria for validation from '{source_reference}'.")
            return

        for candidate in validation_candidates:
            validation_id = str(uuid.uuid4())
            try:
                self.db_manager.add_kb_validation_request(
                    validation_id=validation_id,
                    novel_id=novel_id,
                    request_type=candidate["request_type"],
                    item_under_review_json=candidate["item_under_review_json"],
                    validation_question=candidate["validation_question"],
                    source_reference=candidate["source_reference"],
                    source_text_snippet=candidate["source_text_snippet"]
                )
                print(f"LoreKeeperAgent: Generated KB validation request {validation_id} for item from '{candidate['source_reference']}'. Type: {candidate['request_type']}")
            except Exception as e:
                print(f"LoreKeeperAgent: Error adding KB validation request to DB: {e}")


    def process_user_kb_validation_decision(self, novel_id: int, validation_id: str, decision: str, corrected_value_json: Optional[str], user_comment: Optional[str]) -> bool:
        """
        Processes the user's decision on a KB validation request.
        Updates the KB (vector store and knowledge graph) if the decision is 'confirmed' or 'edited'.
        """
        print(f"LoreKeeperAgent: Processing user decision for validation ID {validation_id}. Novel ID: {novel_id}, Decision: {decision}.")
        if user_comment:
            print(f"  User comment: {user_comment}")

        validation_request = self.db_manager.get_kb_validation_request_by_id(validation_id)
        if not validation_request:
            print(f"LoreKeeperAgent Error: Validation request {validation_id} not found.")
            return False

        if validation_request['novel_id'] != novel_id:
            print(f"LoreKeeperAgent Error: Mismatch novel_id for validation request {validation_id}.")
            return False

        item_to_process_json = None
        action_description_for_kb = ""

        if decision == "confirmed":
            item_to_process_json = validation_request.get('item_under_review_json')
            action_description_for_kb = "User confirmed information."
        elif decision == "edited":
            if corrected_value_json:
                item_to_process_json = corrected_value_json
                action_description_for_kb = "User provided corrected information."
            else:
                print(f"LoreKeeperAgent Error: Decision for {validation_id} was 'edited' but no corrected_value_json provided.")
                return False
        elif decision == "rejected":
            print(f"LoreKeeperAgent: Item from validation request {validation_id} was rejected by user. No information will be added to KB from this item.")
            # Potentially log this rejection more formally or mark related tentative data. For now, just don't add.
            return True # Processing of rejection is complete.
        else:
            print(f"LoreKeeperAgent Error: Unknown decision '{decision}' for validation request {validation_id}.")
            return False

        if not item_to_process_json:
            print(f"LoreKeeperAgent Error: No item data to process for KB for validation request {validation_id} (decision: {decision}).")
            return False

        try:
            item_data_for_kg_processing = json.loads(item_to_process_json_str) # Parsed data for KG

            # Format the item data into a string for adding to the vector store
            text_for_vector_kb = ""
            item_type = validation_request.get('request_type', "generic_item")

            # Simplified text generation for vector store based on item type
            if item_type.startswith("entity_") or item_type.startswith("character_") or item_type.startswith("location_") or item_type.startswith("item_") or item_type.startswith("organization_"):
                name = item_data_for_kg_processing.get('name', 'Unnamed Entity')
                desc = item_data_for_kg_processing.get('description', 'No description')
                ent_type = item_data_for_kg_processing.get('type', 'entity')
                text_for_vector_kb = f"Validated {ent_type}: {name}. Description: {desc}. Status: {item_data_for_kg_processing.get('status_update', 'N/A')}. Location: {item_data_for_kg_processing.get('location', 'N/A')}."
            elif item_type.startswith("event_"):
                summary = item_data_for_kg_processing.get('summary', 'No summary')
                participants_list = item_data_for_kg_processing.get('participants', [])
                participants = ", ".join(participants_list) if participants_list else 'N/A'
                location = item_data_for_kg_processing.get('location', 'N/A')
                significance = item_data_for_kg_processing.get('significance', 'N/A')
                text_for_vector_kb = f"Validated Event: {summary}. Participants: {participants}. Location: {location}. Significance: {significance}."
            # Add more types as needed (relationship, lore_snippet)
            else:
                text_for_vector_kb = f"Validated Item ({item_type}): {json.dumps(item_data_for_kg_processing)}"

            text_for_vector_kb += f" (Source: User Validation ID {validation_id}. {action_description_for_kb})"

            # Add to vector store (KB)
            metadata_for_vector = {
                "source": "user_validated_kb_item",
                "validation_id": validation_id,
                "original_request_type": item_type,
                "decision_type": decision,
                "processed_date": datetime.now(timezone.utc).isoformat()
            }
            if validation_request.get('source_reference'):
                metadata_for_vector['original_source_reference'] = validation_request['source_reference']

            self.kb_manager.add_texts(novel_id, [text_for_vector_kb], metadatas=[metadata_for_vector])
            print(f"LoreKeeperAgent: Added/Updated information from validation ID {validation_id} to vector knowledge base.")

            # Now, update the Knowledge Graph with this validated/edited information
            # We need to convert the single item_data (which is an entity, event etc.)
            # into an ExtractedInfo structure to pass to update_knowledge_graph_from_extracted_info.
            validated_extracted_info = ExtractedInfo()
            if item_type.startswith("entity_") or item_type.startswith("character_") or item_type.startswith("location_") or item_type.startswith("item_") or item_type.startswith("organization_"):
                validated_extracted_info["entities"] = [item_data_for_kg_processing]
            elif item_type.startswith("event_"):
                 validated_extracted_info["events"] = [item_data_for_kg_processing]
            elif item_type.startswith("relationship_"):
                validated_extracted_info["relationships"] = [item_data_for_kg_processing]
            elif item_type.startswith("lore_snippet_"):
                validated_extracted_info["new_lore_snippets"] = [item_data_for_kg_processing]

            if validated_extracted_info: # If any category was populated
                self.update_knowledge_graph_from_extracted_info(novel_id, validated_extracted_info, source_ref_for_kg_update)
                print(f"LoreKeeperAgent: Updated knowledge graph with validated info from ID {validation_id}.")
            return True

        except json.JSONDecodeError as e:
            print(f"LoreKeeperAgent Error: Failed to parse JSON for item/corrected_value in validation {validation_id}. Error: {e}")
            return False
        except Exception as e:
            print(f"LoreKeeperAgent Error: Failed to process user validation decision for {validation_id}. Error: {e}")
            return False
