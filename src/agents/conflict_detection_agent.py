from typing import Dict, Any, List, Optional
import uuid

# Placeholder for LoreKeeperAgent and LLMClient to avoid circular dependencies
import re
from src.agents.lore_keeper_agent import LoreKeeperAgent
# from src.llm_abstraction.llm_client import LLMClient # Already effectively imported via Optional[Any] type hint

class ConflictDetectionAgent:
    """
    Agent responsible for detecting inconsistencies and contradictions in novel content,
    leveraging Knowledge Base context.
    """

    def __init__(self, llm_client: Optional[Any] = None, lore_keeper: Optional[Any] = None, db_name: Optional[str] = None):
        """
        Initializes the ConflictDetectionAgent.

        Args:
            llm_client: An instance of LLMClient or a similar interface for LLM interaction.
            lore_keeper: An instance of LoreKeeperAgent. If not provided, one might be instantiated if db_name is given.
            db_name: Database name, used for instantiating LoreKeeperAgent if `lore_keeper` is None.
        """
        self.llm_client = llm_client
        self.lore_keeper = lore_keeper # This can be a pre-initialized LoreKeeperAgent instance
        self.db_name = db_name # Store db_name for on-demand LoreKeeper instantiation

        if self.llm_client:
            print("ConflictDetectionAgent initialized with LLMClient.")
        if self.lore_keeper:
            print("ConflictDetectionAgent initialized with a pre-existing LoreKeeper instance.")
        elif self.db_name:
            print(f"ConflictDetectionAgent initialized with db_name='{self.db_name}'. LoreKeeper will be instantiated on demand if needed.")

        if not self.llm_client:
            print("ConflictDetectionAgent: Warning - LLMClient not provided. Detection capabilities will be limited.")
        if not self.lore_keeper and not self.db_name:
            print("ConflictDetectionAgent: Warning - Neither LoreKeeper instance nor db_name provided. KB context will be unavailable.")

    def _extract_key_entities_for_kb_query(self, chapter_text: str) -> List[str]:
        """
        Extracts key entities (characters, locations, items) from chapter text for targeted KB queries.
        """
        if not self.llm_client:
            print("ConflictDetectionAgent: LLMClient not available for entity extraction.")
            return []

        prompt = f"""Given the following chapter text, list the key character names, important locations, and crucial items or unique concepts mentioned that would be most relevant for checking against a knowledge base for consistency.
Focus on proper nouns and elements central to the plot or descriptions in this text.
Return a comma-separated list of these entities. If no specific entities stand out, return an empty string.

Text:
---
{chapter_text[:2000]}
---
Entities:""" # Limit text length to manage LLM token usage for this quick extraction

        try:
            response_text = self.llm_client.generate_text(prompt, max_tokens=150, temperature=0.3)
            if response_text:
                entities = [e.strip() for e in response_text.split(',') if e.strip()]
                if entities:
                    print(f"ConflictDetectionAgent: Extracted key entities for KB query: {entities}")
                    return entities
                else:
                    print("ConflictDetectionAgent: No specific entities extracted by LLM for targeted KB query.")
                    return []
            else:
                print("ConflictDetectionAgent: LLM returned no response for entity extraction.")
                return []
        except Exception as e:
            print(f"ConflictDetectionAgent: Error during LLM call for entity extraction: {e}")
            return []

    def _construct_conflict_prompt(self, chapter_number: int, chapter_text: str, kb_context_str: str, novel_theme_style: Optional[Dict[str, Any]]) -> str:
        theme_style_info = ""
        if novel_theme_style:
            theme = novel_theme_style.get('theme', 'Not specified')
            style = novel_theme_style.get('style_preferences', 'Not specified')
            theme_style_info = f"Novel Theme: {theme}\nNovel Style: {style}\n"

        prompt = f"""You are an expert content reviewer for novels. Your task is to identify conflicts and inconsistencies in the provided chapter text.
Review Chapter {chapter_number} for:
1. Internal inconsistencies within the chapter itself.
2. Contradictions or inconsistencies when compared against the provided Knowledge Base Context.
Consider the overall novel theme and style for context.

{theme_style_info}
Knowledge Base Context:
---
{kb_context_str}
---

Chapter {chapter_number} Text:
---
{chapter_text}
---

For each conflict found, provide the following details in the specified format:
Conflict X:
  Description: [A clear explanation of the conflict.]
  Excerpt: [The specific excerpt from the chapter text that is problematic. Quote it directly.]
  KB_Reference (Optional): [Specific part of KB context that it conflicts with, if applicable. Quote it or summarize.]
  Conflict_Type: [Categorize from: "Plot Contradiction", "Character Inconsistency", "Timeline Error", "World Rule Violation", "Factual Inconsistency with KB", "Internal Inconsistency"]
  Severity: [Assess as: "Low", "Medium", "High"]
---

If no significant conflicts are detected, respond ONLY with the phrase: "No significant conflicts detected."
Do not add any preamble or explanation if no conflicts are found.
List all conflicts you find.
"""
        return prompt

    def _parse_conflict_response(self, response_text: str, chapter_number: int) -> List[Dict[str, Any]]:
        conflicts: List[Dict[str, Any]] = []
        if "no significant conflicts detected" in response_text.lower() and not response_text.strip().startswith("Conflict"):
            return conflicts

        # Split conflicts by "---" separator, handling potential empty strings from split
        conflict_blocks = [block.strip() for block in response_text.split("---") if block.strip()]

        for block in conflict_blocks:
            conflict_data: Dict[str, Any] = {"chapter_source": chapter_number, "kb_reference": None} # Default kb_reference

            # Attempt to extract conflict ID (e.g., "Conflict 1:")
            id_match = re.search(r"Conflict\s*\d+:", block, re.IGNORECASE)
            if id_match:
                # We generate our own UUID, so this is mostly for parsing structure
                block_content_after_id = block[id_match.end():].strip()
            else:
                block_content_after_id = block # Assume block starts directly with fields if no "Conflict X:"

            conflict_data["conflict_id"] = str(uuid.uuid4())

            fields_map = {
                "Description": None, "Excerpt": None, "KB_Reference": None,
                "Conflict_Type": None, "Severity": None
            }

            # Use regex to find each field. This is more robust to ordering and missing fields.
            for field_name in fields_map.keys():
                # Regex to find "Field_Name: value" and capture value. Handles multiline values for Description, Excerpt, KB_Reference.
                # For KB_Reference, make it optional in the pattern.
                # Pattern tries to capture until the next field name or end of block.
                pattern = rf"{field_name.replace('_', r'[\s_]*')}\s*:\s*(.*?)(?=\n\s*(?:Description|Excerpt|KB_Reference|Conflict_Type|Severity)\s*:|\Z)"
                match = re.search(pattern, block_content_after_id, re.IGNORECASE | re.DOTALL)
                if match:
                    value = match.group(1).strip()
                    # Clean up common LLM artifacts like "Optional):" from the value if necessary
                    value = re.sub(r"^\(Optional\)\s*:\s*", "", value, flags=re.IGNORECASE).strip()
                    fields_map[field_name] = value

            conflict_data.update({k.lower().replace(" ", "_"): v for k, v in fields_map.items() if v is not None})

            # Ensure essential fields have at least a placeholder if not found
            if not conflict_data.get("description"):
                conflict_data["description"] = "Description not clearly parsed from LLM output."
            if not conflict_data.get("type"): # Mapped from Conflict_Type
                 conflict_data["type"] = "Uncategorized"
            if not conflict_data.get("severity"):
                 conflict_data["severity"] = "Unknown"


            # Only add if a description was found or if other key fields are present
            if conflict_data.get("description") != "Description not clearly parsed from LLM output." or \
               conflict_data.get("excerpt") or conflict_data.get("type") != "Uncategorized":
                conflicts.append(conflict_data)
            elif not conflicts and block: # If it's the only block and something is there but not parsed
                print(f"ConflictDetectionAgent: Could not parse any structured fields from block: '{block[:100]}...' - adding as generic conflict.")
                conflicts.append({
                    "conflict_id": str(uuid.uuid4()),
                    "type": "Parsing Error",
                    "description": f"Could not parse LLM response block: {block}",
                    "severity": "Low",
                    "chapter_source": chapter_number,
                })


        if not conflicts and response_text.strip() and "no significant conflicts detected" not in response_text.lower():
            print(f"ConflictDetectionAgent: LLM response was not 'no conflicts' but parser found none. Adding raw response as generic conflict. Response: {response_text[:200]}")
            conflicts.append({
                "conflict_id": str(uuid.uuid4()),
                "type": "Unparsed LLM Output",
                "description": f"LLM flagged potential issues, but they could not be parsed: {response_text}",
                "severity": "Medium", # Needs review
                "chapter_source": chapter_number,
            })

        return conflicts


    def detect_conflicts(
        self,
        novel_id: int,
        current_chapter_text: str,
        current_chapter_number: int,
        novel_context: Optional[Dict[str, Any]] = None # theme, style
    ) -> List[Dict[str, Any]]:
        """
        Detects conflicts in the current chapter using KB context and LLM analysis.

        Args:
            novel_id: The ID of the current novel.
            current_chapter_text: The text of the most recently generated chapter.
            current_chapter_number: The number of the current chapter.
            novel_context: General novel information (theme, style).

        Returns:
            A list of dictionaries, where each dictionary represents a detected conflict.
            Returns an empty list if no conflicts are detected.
        """
        print(f"ConflictDetectionAgent: Starting enhanced conflict detection for Novel ID {novel_id}, Chapter {current_chapter_number}.")

        if not current_chapter_text:
            print("ConflictDetectionAgent: Current chapter text is empty, cannot detect conflicts.")
            return []

        if not self.llm_client:
            print("ConflictDetectionAgent: LLMClient not available. Cannot perform conflict detection.")
            return [{"conflict_id": str(uuid.uuid4()), "type": "Setup Error", "description": "LLMClient not configured for ConflictDetectionAgent.", "severity": "High", "chapter_source": current_chapter_number}]

        # Instantiate LoreKeeperAgent if necessary
        lore_keeper_instance = self.lore_keeper
        if not lore_keeper_instance and self.db_name:
            try:
                lore_keeper_instance = LoreKeeperAgent(db_name=self.db_name, llm_client=self.llm_client) # Pass LLM if needed by LKA's init or methods
                print("ConflictDetectionAgent: Dynamically instantiated LoreKeeperAgent.")
            except Exception as e:
                print(f"ConflictDetectionAgent: Error instantiating LoreKeeperAgent: {e}. Proceeding without KB context.")
                lore_keeper_instance = None
        elif not lore_keeper_instance and not self.db_name:
             print("ConflictDetectionAgent: Warning - db_name not set, cannot initialize LoreKeeperAgent. Proceeding without KB context.")
             lore_keeper_instance = None


        # Retrieve Knowledge Base Context
        retrieved_kb_context_str = "Knowledge Base context not available."
        all_kb_chunks_with_scores: Dict[str, float] = {} # Use dict to store unique doc content and its highest score

        if lore_keeper_instance and hasattr(lore_keeper_instance, 'kb_manager') and lore_keeper_instance.kb_manager:
            try:
                # 1. Targeted Entity Queries
                extracted_entities = self._extract_key_entities_for_kb_query(current_chapter_text)
                if extracted_entities:
                    print(f"ConflictDetectionAgent: Performing targeted KB queries for entities: {extracted_entities}")
                    for entity in set(extracted_entities): # Use set to avoid duplicate queries for same entity
                        if not entity: continue
                        entity_query_results = lore_keeper_instance.kb_manager.query_knowledge_base(
                            novel_id,
                            f"Detailed information about '{entity}' including relationships, characteristics, and past events.",
                            n_results=2 # Fetch a few relevant snippets per entity
                        )
                        if entity_query_results:
                            for doc, score in entity_query_results:
                                if doc not in all_kb_chunks_with_scores or score > all_kb_chunks_with_scores[doc]:
                                    all_kb_chunks_with_scores[doc] = score
                            print(f"ConflictDetectionAgent: Found {len(entity_query_results)} KB snippets for entity '{entity}'.")

                # 2. Broad Context Query
                print(f"ConflictDetectionAgent: Performing broad KB query for Chapter {current_chapter_number} content.")
                broad_query_text = current_chapter_text[:1500] # Query with start of chapter
                broad_kb_results = lore_keeper_instance.kb_manager.query_knowledge_base(
                    novel_id,
                    broad_query_text,
                    n_results=4 # Reduced from 7, as targeted queries supplement
                )
                if broad_kb_results:
                    for doc, score in broad_kb_results:
                        if doc not in all_kb_chunks_with_scores or score > all_kb_chunks_with_scores[doc]:
                            all_kb_chunks_with_scores[doc] = score
                    print(f"ConflictDetectionAgent: Found {len(broad_kb_results)} KB snippets from broad query.")

                # 3. Format and Combine
                if all_kb_chunks_with_scores:
                    # Sort by score descending to prioritize more relevant info if context gets too long
                    sorted_kb_items = sorted(all_kb_chunks_with_scores.items(), key=lambda item: item[1], reverse=True)

                    formatted_results = []
                    for doc, score in sorted_kb_items:
                        formatted_results.append(f"- {doc} (Similarity: {score:.2f})")
                    retrieved_kb_context_str = "\n".join(formatted_results)
                    print(f"ConflictDetectionAgent: Total unique KB items for context: {len(sorted_kb_items)}.")
                else:
                    retrieved_kb_context_str = "No specific information retrieved from Knowledge Base for this chapter context."
                    print("ConflictDetectionAgent: No items retrieved from KB from any query type.")

            except Exception as e:
                print(f"ConflictDetectionAgent: Error querying Knowledge Base: {e}. Proceeding with limited context.")
                retrieved_kb_context_str = f"Error accessing Knowledge Base: {e}"
        else:
            print("ConflictDetectionAgent: LoreKeeperAgent or KBManager not available. Skipping KB queries.")


        # Construct and Execute LLM Prompt
        prompt = self._construct_conflict_prompt(current_chapter_number, current_chapter_text, retrieved_kb_context_str, novel_context)

        print("ConflictDetectionAgent: Sending prompt to LLM for conflict analysis...")
        try:
            llm_response_text = self.llm_client.generate_text(prompt, max_tokens=1000) # Increased max_tokens for potentially many conflicts
        except Exception as e:
            print(f"ConflictDetectionAgent: Error during LLM call for conflict analysis: {e}")
            return [{"conflict_id": str(uuid.uuid4()), "type": "LLM Error", "description": f"LLM call failed: {e}", "severity": "High", "chapter_source": current_chapter_number}]

        print("ConflictDetectionAgent: Received LLM response. Parsing conflicts...")
        # Parse LLM Response
        parsed_conflicts = self._parse_conflict_response(llm_response_text, current_chapter_number)

        if parsed_conflicts:
            print(f"ConflictDetectionAgent: Detected {len(parsed_conflicts)} conflict(s) in Chapter {current_chapter_number} after LLM analysis.")
        else:
            print(f"ConflictDetectionAgent: No conflicts detected in Chapter {current_chapter_number} by LLM or parser found none from response: '{llm_response_text[:100]}...'")

        return parsed_conflicts


if __name__ == '__main__':
    # Basic test for the shell
    # A mock LLM client for testing purposes
    class MockLLMClientForConflict:
        def __init__(self, fixed_response=None):
            self.fixed_response = fixed_response

        def generate_text(self, prompt: str, max_tokens: int) -> str:
            if self.fixed_response:
                return self.fixed_response
            # Simple rule-based responses for testing different scenarios
            if "Character Z is blue" in prompt and "Character Z is red" in prompt:
                return """Conflict 1:
  Description: Character Z is described as blue in KB but red in chapter.
  Excerpt: Character Z is red.
  KB_Reference: Character Z is blue
  Conflict_Type: Factual Inconsistency with KB
  Severity: Medium
---"""
            if "magic suddenly failed" in prompt: # Old test case, adapt if needed
                return """Conflict 1:
  Description: Magic failing abruptly in a world where it's fundamental might be a plot hole if not explained.
  Excerpt: magic suddenly failed for no reason
  KB_Reference: World rules state magic is ever-present.
  Conflict_Type: World Rule Violation
  Severity: High
---"""
            return "No significant conflicts detected."

    # Mock LoreKeeper and its KnowledgeBaseManager
    class MockKnowledgeBaseManager:
        def query_knowledge_base(self, novel_id: int, query_text: str, n_results: int = 3) -> List[tuple[str, float]]:
            print(f"MockKBManager: Querying for novel {novel_id} with query '{query_text[:60]}...' (n_results={n_results})")
            if "Character Z" in query_text or "blue" in query_text.lower():
                return [("KB: Character Z is consistently portrayed as blue.", 0.95),
                        ("KB: Character Z is known for their calm demeanor.", 0.80)]
            if "fairies" in query_text.lower():
                 return [("KB: Fairies are mythical creatures in this world, rarely seen.", 0.90)]
            if "hero" in query_text.lower():
                return [("KB: The prophecy states only the chosen hero can defeat the dragon.", 0.88),
                        ("KB: Heroes in this land are always male, by ancient decree.", 0.75)]
            # Default for broad query if no specific match
            if "Character Z, who was famously red" in query_text: # Simulating broad query from chapter text
                 return [("KB: General world lore snippet about colors and their meanings.", 0.70)]
            return []

    class MockLoreKeeperAgent:
        def __init__(self, db_name: Optional[str] = None, llm_client: Optional[Any] = None): # llm_client param added to match LKA's potential init
            self.kb_manager = MockKnowledgeBaseManager()
            # self.llm_client = llm_client # Store if LKA uses it directly, though CDA passes its own for entity extraction
            print(f"MockLoreKeeperAgent initialized (db_name='{db_name}')")

    # Updated MockLLMClient to handle entity extraction prompt
    class MockLLMClientForConflict:
        def __init__(self, fixed_response_conflict=None, fixed_response_entities=None):
            self.fixed_response_conflict = fixed_response_conflict
            self.fixed_response_entities = fixed_response_entities
            self.call_count = 0

        def generate_text(self, prompt: str, max_tokens: int, temperature: Optional[float]=None) -> str:
            self.call_count += 1
            if "Entities:" in prompt: # This is the entity extraction call
                print(f"MockLLMClient (Entity Extraction call {self.call_count}): Received entity prompt.")
                if self.fixed_response_entities is not None:
                    return self.fixed_response_entities
                if "Character Z" in prompt and "Fairies" in prompt:
                    return "Character Z, Fairies"
                if "Maria" in prompt:
                    return "Maria"
                return "" # Default no entities
            else: # This is the conflict detection call
                print(f"MockLLMClient (Conflict Detection call {self.call_count}): Received conflict prompt.")
                if self.fixed_response_conflict:
                    return self.fixed_response_conflict
                if "Character Z is blue" in prompt and "Character Z is red" in prompt: # Check if KB context made it to prompt
                    return """Conflict 1:
      Description: Character Z is described as blue in KB but red in chapter.
      Excerpt: Character Z is red.
      KB_Reference: KB: Character Z is consistently portrayed as blue.
      Conflict_Type: Factual Inconsistency with KB
      Severity: Medium
    ---"""
                return "No significant conflicts detected."


    # Test Case 1: Contradiction with KB (testing new entity extraction path)
    print("\n--- Test Case 1: Contradiction with KB (with Entity Extraction) ---")
    # Specific fixed responses for this test:
    # 1. For entity extraction: "Character Z, Fairies"
    # 2. For conflict detection: The detailed conflict string
    llm_conflict_response_tc1 = """Conflict 1:
  Description: Character Z is described as blue in the Knowledge Base, but the chapter states they are red.
  Excerpt: "Character Z, who was famously red, entered the room."
  KB_Reference: "KB: Character Z is consistently portrayed as blue."
  Conflict_Type: Factual Inconsistency with KB
  Severity: Medium
---"""
    llm_client_tc1 = MockLLMClientForConflict(
        fixed_response_conflict=llm_conflict_response_tc1,
        fixed_response_entities="Character Z, Fairies" # Entities LLM should extract
    )
    agent1 = ConflictDetectionAgent(llm_client=llm_client_tc1, lore_keeper=MockLoreKeeperAgent(db_name="test_db_tc1"))
    novel_context1 = {"theme": "Fantasy", "style_preferences": "Epic"}
    chapter_text1 = "Character Z, who was famously red, entered the room. Fairies danced around."

    conflicts1 = agent1.detect_conflicts(novel_id=1, current_chapter_text=chapter_text1, current_chapter_number=1, novel_context=novel_context1)
    print(f"Found conflicts for TC1: {len(conflicts1)}")
    for conflict in conflicts1: print(conflict)
    assert len(conflicts1) == 1
    assert conflicts1[0]['description'] == "Character Z is described as blue in the Knowledge Base, but the chapter states they are red."
    assert llm_client_tc1.call_count == 2 # 1 for entities, 1 for conflict

    # Test Case 2: No conflicts (ensure entity extraction still runs)
    print("\n--- Test Case 2: No Conflicts (with Entity Extraction) ---")
    llm_client_tc2 = MockLLMClientForConflict(
        fixed_response_conflict="No significant conflicts detected.",
        fixed_response_entities="Some Entity" # Simulate some entity being extracted
    )
    agent2 = ConflictDetectionAgent(llm_client=llm_client_tc2, lore_keeper=MockLoreKeeperAgent(db_name="test_db_tc2"))
    chapter_text2 = "The weather was pleasant, and everyone had a good day. Some Entity was there."
    conflicts2 = agent2.detect_conflicts(novel_id=1, current_chapter_text=chapter_text2, current_chapter_number=2, novel_context=novel_context1)
    print(f"Found conflicts: {len(conflicts2)}")
    for conflict in conflicts2: print(conflict)

    # Test Case 3: Internal Inconsistency
    print("\n--- Test Case 3: Internal Inconsistency ---")
    llm_client_internal_conflict = MockLLMClientForConflict(fixed_response="""Conflict 1:
  Description: The character is stated to be alone, but then speaks to another character.
  Excerpt: "He was utterly alone in the vast chamber. 'Are you there?' he whispered to Maria."
  Conflict_Type: Internal Inconsistency
  Severity: High
---""")
    agent3 = ConflictDetectionAgent(llm_client=llm_client_internal_conflict, lore_keeper=MockLoreKeeperAgent(db_name="test_db"))
    chapter_text3 = "He was utterly alone in the vast chamber. 'Are you there?' he whispered to Maria."
    conflicts3 = agent3.detect_conflicts(novel_id=1, current_chapter_text=chapter_text3, current_chapter_number=3)
    print(f"Found conflicts: {len(conflicts3)}")
    for conflict in conflicts3: print(conflict)

    # Test Case 4: Unparseable but not "no conflicts"
    print("\n--- Test Case 4: Unparseable response ---")
    llm_client_unparseable = MockLLMClientForConflict(fixed_response="Something seems off with the timeline, check dates.")
    agent4 = ConflictDetectionAgent(llm_client=llm_client_unparseable, lore_keeper=MockLoreKeeperAgent(db_name="test_db"))
    chapter_text4 = "It was Monday, then it was Friday."
    conflicts4 = agent4.detect_conflicts(novel_id=1, current_chapter_text=chapter_text4, current_chapter_number=4)
    print(f"Found conflicts: {len(conflicts4)}")
    for conflict in conflicts4: print(conflict)

    # Test Case 5: No LLM Client
    print("\n--- Test Case 5: No LLM Client ---")
    agent5 = ConflictDetectionAgent(llm_client=None, lore_keeper=MockLoreKeeperAgent(db_name="test_db"))
    conflicts5 = agent5.detect_conflicts(novel_id=1, current_chapter_text=chapter_text1, current_chapter_number=5)
    print(f"Found conflicts: {len(conflicts5)}")
    for conflict in conflicts5: print(conflict)

    # Test Case 6: Dynamic LoreKeeper instantiation
    print("\n--- Test Case 6: Dynamic LoreKeeper with db_name ---")
    # This test relies on the actual LoreKeeperAgent and its dependencies (like ChromaDB)
    # being available if db_name is used for real. For a unit test, MockLoreKeeperAgent should be used.
    # We can simulate this by checking if the dynamic instantiation path is taken.
    # For true unit testing of this path, we'd mock LoreKeeperAgent itself when imported.
    agent6 = ConflictDetectionAgent(llm_client=llm_client_no_conflict, db_name="mock_dynamic.db") # lore_keeper is None
    # To truly test dynamic instantiation, we'd need to ensure LoreKeeperAgent import works
    # and possibly mock its constructor if it does heavy lifting.
    # For this test, the print statements in the constructor will indicate if it tries.
    # The kb_results will be empty because MockLoreKeeperAgent is not globally patched here.
    conflicts6 = agent6.detect_conflicts(novel_id=2, current_chapter_text="The hero arrived.", current_chapter_number=1)
    print(f"Found conflicts for agent6: {len(conflicts6)}")


    # Test Case 7: Multi-field parsing
    print("\n--- Test Case 7: Multi-field conflict parsing ---")
    multi_field_response = """Conflict 1:
  Description: Character Anna is stated to have green eyes in the KB, but the chapter says her eyes are blue.
  Excerpt: "Anna's blue eyes sparkled."
  KB_Reference: "Anna (Eyes: Green, Hair: Blonde)"
  Conflict_Type: Factual Inconsistency with KB
  Severity: Medium
---
Conflict 2:
  Description: The scene is set during a harsh winter, but the character is wearing summer clothes.
  Excerpt: "She wore a light cotton sundress despite the blizzard."
  Conflict_Type: Internal Inconsistency
  Severity: High
---
Conflict 3:
  Description: Timeline issue. Event A is said to happen before Event B in KB, but chapter implies reverse.
  Excerpt: "After Event B, they prepared for Event A."
  KB_Reference: "Timeline: Event A -> Event C -> Event B"
  Conflict_Type: Timeline Error
  Severity: Medium
"""
    llm_client_multi = MockLLMClientForConflict(fixed_response=multi_field_response)
    agent7 = ConflictDetectionAgent(llm_client=llm_client_multi, lore_keeper=MockLoreKeeperAgent(db_name="test_db"))
    chapter_text7 = "Anna's blue eyes sparkled. She wore a light cotton sundress despite the blizzard. After Event B, they prepared for Event A."
    conflicts7 = agent7.detect_conflicts(novel_id=3, current_chapter_text=chapter_text7, current_chapter_number=1)
    print(f"Found conflicts: {len(conflicts7)}")
    assert len(conflicts7) == 3
    for i, c in enumerate(conflicts7):
        print(f"  Conflict {i+1}:")
        for k,v in c.items(): print(f"    {k}: {v}")
    assert conflicts7[0]['type'] == "Factual Inconsistency with KB"
    assert "Anna's blue eyes sparkled." in conflicts7[0]['excerpt']
    assert conflicts7[1]['severity'] == "High"
    assert conflicts7[2]['kb_reference'] is not None

    print("Done with ConflictDetectionAgent tests.")
