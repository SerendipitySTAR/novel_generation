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

Provide detailed and creative information for each field. Ensure all requested fields are present.
"""
        return prompt

    def _parse_llm_response(self, llm_response: str, novel_id: int) -> Optional[DetailedCharacterProfile]:
        # Helper to parse comma-separated list fields, handles "None" or empty.
        def parse_list_field(text_value: Optional[str]) -> Optional[List[str]]:
            if text_value and text_value.lower() not in ["none", "n/a", ""]:
                return [s.strip() for s in text_value.split(',') if s.strip()]
            return None # Return None if "None", "N/A", or empty, to distinguish from an empty list from empty value

        try:
            # Ensure the entire profile block is captured first
            profile_block_match = re.search(r"BEGIN CHARACTER PROFILE:(.*?)END CHARACTER PROFILE:", llm_response, re.DOTALL | re.IGNORECASE)
            if not profile_block_match:
                print(f"CharacterSculptorAgent: Error - Could not find 'BEGIN CHARACTER PROFILE:' and 'END CHARACTER PROFILE:' delimiters. Response: {llm_response[:500]}")
                return None

            block_text = profile_block_match.group(1).strip()

            profile = DetailedCharacterProfile(
                character_id=None, novel_id=novel_id, creation_date=datetime.now(timezone.utc).isoformat(),
                name="Unknown", gender=None, age=None, race_or_species=None, appearance_summary=None,
                clothing_style=None, background_story=None, personality_traits=None, values_and_beliefs=None,
                strengths=None, weaknesses=None, quirks_or_mannerisms=None, catchphrase_or_verbal_style=None,
                skills_and_abilities=None, special_powers=None, power_level_assessment=None,
                motivations_deep_drive=None, goal_short_term=None, goal_long_term=None,
                character_arc_potential=None, relationships_initial_notes=None, role_in_story="Unknown Role",
                raw_llm_output_for_character=block_text
            )

            # Regex to capture field content: "FieldName:\s*(.*?)(?=\n[A-Z_][\w\s]+:|$)"
            # This looks for "FieldName:", captures content (.*?), until a lookahead finds a newline,
            # followed by another capitalized field name and colon, or end of string.
            def get_field(field_name: str, text_block: str) -> Optional[str]:
                match = re.search(rf"^{field_name}:\s*(.*?)(?=\n[A-Z_][\w\s()]*:|$)", text_block, re.IGNORECASE | re.DOTALL | re.MULTILINE)
                return match.group(1).strip() if match else None

            profile['name'] = get_field("Name", block_text) or profile['name']
            profile['gender'] = get_field("Gender", block_text)
            profile['age'] = get_field("Age", block_text)
            profile['race_or_species'] = get_field("Race_or_Species", block_text)
            profile['appearance_summary'] = get_field("Appearance_Summary", block_text)
            profile['clothing_style'] = get_field("Clothing_Style", block_text)
            profile['background_story'] = get_field("Background_Story", block_text)
            profile['personality_traits'] = get_field("Personality_Traits", block_text) # Kept as string for now, can be list too
            profile['values_and_beliefs'] = get_field("Values_and_Beliefs", block_text)

            profile['strengths'] = parse_list_field(get_field("Strengths", block_text))
            profile['weaknesses'] = parse_list_field(get_field("Weaknesses", block_text))
            profile['quirks_or_mannerisms'] = parse_list_field(get_field("Quirks_or_Mannerisms", block_text))

            profile['catchphrase_or_verbal_style'] = get_field("Catchphrase_or_Verbal_Style", block_text)
            profile['skills_and_abilities'] = parse_list_field(get_field("Skills_and_Abilities", block_text))
            profile['special_powers'] = parse_list_field(get_field("Special_Powers", block_text))
            profile['power_level_assessment'] = get_field("Power_Level_Assessment", block_text)
            profile['motivations_deep_drive'] = get_field("Motivations_Deep_Drive", block_text)
            profile['goal_short_term'] = get_field("Goal_Short_Term", block_text)
            profile['goal_long_term'] = get_field("Goal_Long_Term", block_text)
            profile['character_arc_potential'] = get_field("Character_Arc_Potential", block_text)
            profile['relationships_initial_notes'] = get_field("Relationships_Initial_Notes", block_text)
            profile['role_in_story'] = get_field("Role_in_Story", block_text) or profile['role_in_story']

            if profile['name'] == "Unknown": # If name wasn't parsed, it's a critical failure
                print(f"CharacterSculptorAgent: Critical parsing failure - Name not found. Block: {block_text[:200]}")
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
