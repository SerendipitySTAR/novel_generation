import re
import json # For serializing to DB
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from src.llm_abstraction.llm_client import LLMClient
from src.core.models import Character, DetailedCharacterProfile # Updated imports
from src.persistence.database_manager import DatabaseManager
import os
from dotenv import load_dotenv
import openai

class CharacterSculptorAgent:
    """
    Generates one or more detailed character profiles based on narrative context
    and specific character concepts. Saves these profiles to the database.
    """
    def __init__(self, db_name="novel_mvp.db"):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"CharacterSculptorAgent Error: LLMClient initialization failed. {e}")
            raise
        except Exception as e:
            print(f"CharacterSculptorAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise
        self.db_manager = DatabaseManager(db_name=db_name)

    def _construct_prompt(self, narrative_outline: str, worldview_data_core_concept: str, plot_summary_str: str, character_concept: str) -> str:
        prompt = f"""You are a master character designer. Based on the provided story details, create a comprehensive profile for ONE character.
The character concept is: {character_concept}.

Story Context:
Narrative Outline: {narrative_outline}
Worldview Core Concept: {worldview_data_core_concept}
Overall Plot Summary: {plot_summary_str}

Please generate the character profile using the following fields, with each field on a new line, using the exact heading provided:

BEGIN CHARACTER PROFILE:
Name: [Character Name - try to make it fitting for the concept and story]
Gender: [Gender]
Age: [Age description, e.g., "20s", "Elderly", "Ageless"]
Race_or_Species: [Race or species, consistent with worldview]
Appearance_Summary: [Detailed physical appearance, 1-2 sentences]
Clothing_Style: [Typical attire, 1-2 sentences]
Background_Story: [Key history, origin, significant life events relevant to the story's context. 2-4 sentences]
Personality_Traits: [Comma-separated list of 3-5 key personality traits, e.g., Brave, Witty, Secretive]
Values_and_Beliefs: [What the character holds important, their moral compass. 1-2 sentences]
Strengths: [Comma-separated list of 2-3 key strengths]
Weaknesses: [Comma-separated list of 2-3 key weaknesses]
Quirks_or_Mannerisms: [Comma-separated list of 1-2 distinctive habits or mannerisms. If none, state "None".]
Catchphrase_or_Verbal_Style: [A typical saying or description of their speech style. If none, state "None".]
Skills_and_Abilities: [Comma-separated list of notable skills/abilities, e.g., Swordsmanship (Expert), Persuasion (Adept). If none, state "None".]
Special_Powers: [Comma-separated list of any special powers, aligned with worldview. If none, state "None".]
Power_Level_Assessment: [e.g., "Novice mage", "Seasoned warrior", "Powerful but untrained". If not applicable, state "N/A".]
Motivations_Deep_Drive: [The character's fundamental, core motivation. 1-2 sentences]
Goal_Short_Term: [An immediate objective within the likely scope of the story. 1 sentence]
Goal_Long_Term: [An ultimate ambition or desire. 1 sentence]
Character_Arc_Potential: [How this character might evolve or change throughout the story. 1-2 sentences]
Relationships_Initial_Notes: [Brief ideas on how this character might relate to other types of characters (e.g., a hero, a villain, a mentor) or specific story elements. 1-2 sentences]
Role_in_Story: [Briefly restate or refine their primary role based on the details generated, e.g., Protagonist, Antagonist, Mentor, Catalyst]
END CHARACTER PROFILE:

# General Guidance for Content Quality - Added to improve character depth and internal consistency.
General Guidance for Content Quality:
- Internal Consistency: Ensure the character's Background_Story clearly informs their Personality_Traits, Values_and_Beliefs, Motivations_Deep_Drive, and Goals.
- World Alignment: Skills_and_Abilities and Special_Powers should be consistent with their Background_Story and the established Worldview Data provided in the Story Context. If listing powers, briefly note their origin or nature if unique.
- Character Growth: For Character_Arc_Potential, describe a plausible growth trajectory or change this character might undergo, considering their stated strengths, weaknesses, and motivations.
- Relational Potential: For Relationships_Initial_Notes, suggest how this character's personality and goals might lead to specific types of interactions (alliances, conflicts, friendships, rivalries) with other potential characters or story elements.
- Overall: Create a character that is not only detailed but also feels internally consistent and has clear potential to contribute meaningfully to the provided Narrative Outline and Overall Plot Summary.

Provide detailed and creative information for each field. Ensure all requested fields are present and adhere to the content quality guidance.
"""
        return prompt

    def _parse_llm_response(self, llm_response: str, novel_id: int) -> Optional[DetailedCharacterProfile]:
        # Helper to parse comma-separated list fields, handles "None" or empty.
        def parse_list_field(text_value: Optional[str]) -> Optional[List[str]]:
            if text_value and text_value.lower() not in ["none", "n/a", ""]:
                return [s.strip() for s in text_value.split(',') if s.strip()]
            return None # Return None if "None", "N/A", or empty, to distinguish from an empty list from empty value

        try:
            profile_block_match = re.search(r"BEGIN CHARACTER PROFILE:(.*?)END CHARACTER PROFILE:", llm_response, re.DOTALL | re.IGNORECASE)
            if not profile_block_match:
                print(f"CharacterSculptorAgent: Error - Could not find 'BEGIN CHARACTER PROFILE:' and 'END CHARACTER PROFILE:' delimiters. Response: {llm_response[:500]}")
                return None

            block_text = profile_block_match.group(1).strip()

            # Initialize profile with defaults, including novel_id and creation_date
            profile_data = DetailedCharacterProfile(
                character_id=None, novel_id=novel_id, creation_date=datetime.now(timezone.utc).isoformat(),
                name="Unknown", gender=None, age=None, race_or_species=None, appearance_summary=None,
                clothing_style=None, background_story=None, personality_traits=None, values_and_beliefs=None,
                strengths=[], weaknesses=[], quirks_or_mannerisms=[], catchphrase_or_verbal_style=None,
                skills_and_abilities=[], special_powers=[], power_level_assessment=None,
                motivations_deep_drive=None, goal_short_term=None, goal_long_term=None,
                character_arc_potential=None, relationships_initial_notes=None, role_in_story="Unknown Role",
                raw_llm_output_for_character=block_text # Store the raw block for debugging
            )

            # Helper for flexible field extraction
            def get_flexible_field(field_variations: List[str], text: str, is_list_field: bool = False) -> Optional[Any]:
                # Pattern: (PRIMARY_HEADING|ALT_HEADING1|ALT_HEADING2):\s*(.*?)(?=\n\s*\w[\w\s()\-]*:|$)
                # Captures content until the next potential field heading or end of string.
                regex_str = r"^(?:" + "|".join(re.escape(v) for v in field_variations) + r"):\s*(.*?)(?=\n\s*\w[\w\s()\-]*:|$)"
                match = re.search(regex_str, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)

                field_display_name = field_variations[0]

                if match:
                    value = match.group(1).strip()
                    if not value:
                        print(f"CharacterSculptorAgent: Warning - Field '{field_display_name}' found but content is empty.")
                        return [] if is_list_field else None

                    if is_list_field:
                        if value.lower() in ["none", "n/a"]: return [] # Explicit "None" means empty list

                        # Attempt comma separation
                        items = [s.strip() for s in value.split(',') if s.strip()]

                        # If comma results in one item with newlines, try newline splitting
                        if len(items) == 1 and '\n' in items[0]:
                            print(f"CharacterSculptorAgent: Info - Field '{field_display_name}' has single comma-item with newlines, trying newline split.")
                            newline_items = []
                            for line_item in items[0].split('\n'):
                                line_item_stripped = line_item.strip()
                                # Remove leading bullets/numbers
                                line_item_cleaned = re.sub(r"^\s*[-*\d]+\.?\s*", "", line_item_stripped)
                                if line_item_cleaned:
                                    newline_items.append(line_item_cleaned)
                            if newline_items: return newline_items
                            else: # Fallback to the single comma-item if newline split fails
                                 print(f"CharacterSculptorAgent: Warning - Field '{field_display_name}' newline split for list resulted in no items. Original: '{items[0]}'")
                                 return items if items[0] else []
                        return items
                    return value
                else:
                    print(f"CharacterSculptorAgent: Warning - Field '{field_display_name}' not found in profile block. Block snippet: '{text[:100]}...'")
                    return [] if is_list_field else None

            # Define field variations for parsing
            field_map: Dict[str, List[str]] = {
                'name': ["Name"],
                'gender': ["Gender"],
                'age': ["Age"],
                'race_or_species': ["Race_or_Species", "Race/Species", "Species"],
                'appearance_summary': ["Appearance_Summary", "Appearance"],
                'clothing_style': ["Clothing_Style", "Attire"],
                'background_story': ["Background_Story", "Background", "History", "Backstory"],
                'personality_traits': ["Personality_Traits", "Personality"], # Will be treated as string, can be list in other contexts
                'values_and_beliefs': ["Values_and_Beliefs", "Values", "Beliefs"],
                'strengths': ["Strengths"], # List field
                'weaknesses': ["Weaknesses"], # List field
                'quirks_or_mannerisms': ["Quirks_or_Mannerisms", "Quirks", "Mannerisms"], # List field
                'catchphrase_or_verbal_style': ["Catchphrase_or_Verbal_Style", "Verbal Style", "Catchphrase"],
                'skills_and_abilities': ["Skills_and_Abilities", "Skills", "Abilities"], # List field
                'special_powers': ["Special_Powers", "Powers"], # List field
                'power_level_assessment': ["Power_Level_Assessment", "Power Level"],
                'motivations_deep_drive': ["Motivations_Deep_Drive", "Motivation", "Core Drive"],
                'goal_short_term': ["Goal_Short_Term", "Short-Term Goal"],
                'goal_long_term': ["Goal_Long_Term", "Long-Term Goal"],
                'character_arc_potential': ["Character_Arc_Potential", "Character Arc", "Potential Arc"],
                'relationships_initial_notes': ["Relationships_Initial_Notes", "Relationships"],
                'role_in_story': ["Role_in_Story", "Role"]
            }

            list_type_keys = ['strengths', 'weaknesses', 'quirks_or_mannerisms', 'skills_and_abilities', 'special_powers']

            for key, variations in field_map.items():
                is_list = key in list_type_keys
                parsed_value = get_flexible_field(variations, block_text, is_list_field=is_list)
                if parsed_value is not None: # Assign if not None (empty list is not None)
                    profile_data[key] = parsed_value
                elif is_list: # Ensure list fields are at least empty lists if not found
                    profile_data[key] = []


            # Final check for critical fields like name
            if not profile_data.get('name') or profile_data['name'] == "Unknown":
                print(f"CharacterSculptorAgent: Critical parsing failure - Name not found or is 'Unknown'. Block: {block_text[:200]}")
                return None

            return profile

        except Exception as e:
            print(f"CharacterSculptorAgent: Exception during LLM response parsing - {e}. Response: {llm_response[:500]}")
            return None

    def generate_and_save_characters(self, novel_id: int, narrative_outline: str, worldview_data_core_concept: str, plot_summary_str: str, character_concepts: List[str]) -> List[DetailedCharacterProfile]:
        generated_detailed_profiles: List[DetailedCharacterProfile] = []

        for concept in character_concepts:
            print(f"\nCharacterSculptorAgent: Generating character for concept: '{concept}'")
            prompt = self._construct_prompt(narrative_outline, worldview_data_core_concept, plot_summary_str, concept)

            try:
                llm_response_text = self.llm_client.generate_text(
                    prompt=prompt,
                    model_name="gpt-3.5-turbo",
                    max_tokens=2000 # Increased for detailed profile
                )
                print(f"CharacterSculptorAgent: Received response from LLM for concept '{concept}'.")
            except Exception as e:
                print(f"CharacterSculptorAgent: Error during LLM call for concept '{concept}' - {e}")
                continue # Skip to next concept

            if not llm_response_text:
                print(f"CharacterSculptorAgent: LLM returned an empty response for concept '{concept}'.")
                continue

            parsed_profile = self._parse_llm_response(llm_response_text, novel_id)

            if parsed_profile:
                # Serialize the detailed profile for the description field, excluding DB-managed fields
                profile_to_serialize = {k: v for k, v in parsed_profile.items() if k not in ['character_id', 'novel_id', 'creation_date']}
                description_json = json.dumps(profile_to_serialize)

                char_name = parsed_profile.get('name', 'Unnamed Character')
                char_role = parsed_profile.get('role_in_story', 'Unknown Role')

                try:
                    db_id = self.db_manager.add_character(
                        novel_id=novel_id,
                        name=char_name,
                        description=description_json, # Store JSON in description
                        role_in_story=char_role
                    )
                    parsed_profile['character_id'] = db_id # Update with DB ID
                    # The creation_date from db_manager.add_character is the one stored in DB
                    # We can fetch the character to get the DB creation_date if strict sync is needed here
                    # For now, the one set by parser is fine for the returned object.

                    generated_detailed_profiles.append(parsed_profile)
                    print(f"Saved character '{char_name}' (Concept: {concept}) with DB ID {db_id}.")
                except Exception as e:
                    print(f"Error saving character '{char_name}' (Concept: {concept}) to DB: {e}")
            else:
                print(f"CharacterSculptorAgent: Failed to parse character profile for concept '{concept}'. Raw response snippet: {llm_response_text[:300]}...")

        return generated_detailed_profiles

if __name__ == "__main__":
    print("--- Testing CharacterSculptorAgent (Detailed Profile - Live LLM Call) ---")
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or "dummykey" in api_key.lower() or api_key == "your_openai_api_key_here":
        print("WARNING: A real OPENAI_API_KEY is required for this test.")
        print("If a dummy/placeholder key is used, LLM calls will fail.")
        # Allow test to proceed to catch LLMClient init error if key is totally missing

    test_db_name = "test_detailed_character_agent.db"
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    db_mngr = DatabaseManager(db_name=test_db_name)
    novel_id_test = -1

    try:
        novel_id_test = db_mngr.add_novel(
            user_theme="A group of explorers discovers a hidden civilization in the Amazon rainforest.",
            style_preferences="Adventure, mystery, with detailed descriptions of nature."
        )
        print(f"Dummy Novel created with ID: {novel_id_test}")

        sample_outline = "Explorers venture deep into uncharted Amazon, facing natural perils and hints of a lost tribe. They find a hidden city, must decide whether to reveal it to the world or protect its secrecy."
        sample_worldview = "The Amazon, 2042. Vast, largely unexplored regions still exist. The hidden city, 'Elara', has unique bio-luminescent flora and a culture that lives in harmony with nature, wary of outsiders."
        sample_plot = "The team, led by Dr. Aris Thorne, follows ancient maps. They overcome challenges like treacherous rivers and territorial wildlife. They finally locate Elara, are initially met with suspicion, then learn about their unique way of life and the threat from illegal logging operations encroaching on their territory."

        character_concepts_to_generate = [
            "the determined expedition leader, haunted by a past failure",
            "a cynical botanist who initially only cares about scientific discovery but grows to respect Elara's culture",
            "the main antagonist, a ruthless CEO of the logging company"
        ]

        agent = CharacterSculptorAgent(db_name=test_db_name)
        print("CharacterSculptorAgent initialized.")

        print(f"\n--- Generating {len(character_concepts_to_generate)} detailed characters for Novel ID: {novel_id_test} (Live Call) ---")

        generated_profiles = agent.generate_and_save_characters(
            novel_id=novel_id_test,
            narrative_outline=sample_outline,
            worldview_data_core_concept=sample_worldview, # Pass core concept or relevant summary
            plot_summary_str=sample_plot,
            character_concepts=character_concepts_to_generate
        )

        print("\n--- Generated and Saved Detailed Character Profiles ---")
        if generated_profiles:
            for profile in generated_profiles:
                print(f"\n--- Character ID: {profile.get('character_id')} (Novel ID: {profile.get('novel_id')}) ---")
                # Print all fields from DetailedCharacterProfile
                for key, value in profile.items():
                     print(f"  {key.replace('_', ' ').capitalize()}: {value}")

                # Verify from DB
                if profile.get('character_id'):
                    char_from_db = db_mngr.get_character_by_id(profile['character_id'])
                    assert char_from_db is not None
                    print(f"  VERIFIED: Found character '{char_from_db['name']}' in DB.")
                    # print(f"  DB Description (JSON): {char_from_db['description'][:200]}...") # Verify JSON storage
                    try:
                        desc_json = json.loads(char_from_db['description'])
                        assert desc_json['name'] == profile['name'] # Check one field from JSON
                        print("  DB Description JSON successfully loaded and name matches.")
                    except Exception as e:
                        print(f"  Error checking DB description JSON: {e}")


            assert len(generated_profiles) == len(character_concepts_to_generate), \
                f"Expected {len(character_concepts_to_generate)} profiles, got {len(generated_profiles)}"
        else:
            print("No detailed character profiles were generated.")
            if not (api_key and api_key != "your_openai_api_key_here" and "dummykey" not in api_key.lower()):
                 print("This is expected if a valid API key was not available.")
            else:
                assert False, "Character generation failed even with a potentially valid API key."


    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except openai.APIError as apie:
        print(f"OpenAI API Error during test: {apie}")
    except Exception as e:
        print(f"An unexpected error occurred during agent testing: {e}")
        traceback.print_exc()
    finally:
        if os.path.exists(test_db_name):
            print(f"\nCleaning up test database: {test_db_name}")
            os.remove(test_db_name)

    print("\n--- CharacterSculptorAgent (Detailed Profile) Test Finished ---")
