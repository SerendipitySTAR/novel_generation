from typing import List
from datetime import datetime, timezone
from src.llm_abstraction.llm_client import LLMClient
from src.core.models import Character
from src.persistence.database_manager import DatabaseManager
import os # For API key check in test block

class CharacterSculptorAgent:
    def __init__(self, db_name="novel_mvp.db"):
        try:
            self.llm_client = LLMClient()
        except ValueError as e: # This is raised by LLMClient if API key is missing
            print(f"CharacterSculptorAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise
        except Exception as e:
            print(f"CharacterSculptorAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise
        self.db_manager = DatabaseManager(db_name=db_name)

    def _construct_prompt(self, narrative_outline: str, worldview_data: str, plot_summary: str, num_characters: int = 2) -> str:
        prompt = f"""
Based on the following narrative elements:
Narrative Outline:
{narrative_outline}

Worldview:
{worldview_data}

Plot Summary:
{plot_summary}

Please generate {num_characters} distinct and compelling characters that would fit well into this story.
For each character, provide the following information in the specified format:

Character 1:
Name: [Character Name]
Description: [Brief description of appearance, personality, and background relevant to the story]
Role: [Their role in the story, e.g., protagonist, antagonist, mentor, foil, love interest, supporting character]
"""
        # Adjust prompt for more than 1 character, assuming Character 1 is already templated
        if num_characters == 1: # If only one character, the template above is fine.
             pass # No need to add more character blocks if only one is requested.
        elif num_characters > 1:
            # Add block for Character 2 if not already fully covered by default prompt
            if not "Character 2:" in prompt: # Basic check, could be more robust
                 prompt += """
Character 2:
Name: [Character Name]
Description: [Brief description of appearance, personality, and background relevant to the story]
Role: [Their role in the story]
"""
            # Add blocks for characters beyond 2
            if num_characters > 2:
                for i in range(3, num_characters + 1):
                    prompt += f"""
Character {i}:
Name: [Character Name]
Description: [Brief description of appearance, personality, and background relevant to the story]
Role: [Their role in the story]
"""
        prompt += "\nEnsure each character's details are clearly separated."
        return prompt

    def _parse_llm_response(self, llm_response: str, novel_id: int) -> List[Character]:
        characters: List[Character] = []
        # Split the response into blocks for each character.
        character_blocks = llm_response.strip().split("Character ")[1:]

        if not character_blocks and llm_response.strip(): # If split yields nothing but there is content
            # This might happen if the "Character X:" prefix is missing for the first character
            # or if the LLM just provides one character without the "Character 1:" prefix.
            # Try to parse as a single block if specific markers are present.
            if "Name:" in llm_response and "Description:" in llm_response and "Role:" in llm_response:
                 print("CharacterSculptorAgent: Parsing LLM response as a single character block (no 'Character X:' prefix found).")
                 character_blocks = [llm_response.strip()] # Treat the whole response as one block
            else: # If markers are also missing, cannot reliably parse
                print("CharacterSculptorAgent: LLM response does not contain 'Character X:' delimiters and lacks clear markers for a single character. Parsing failed.")
                return []


        for block_content in character_blocks:
            if not block_content.strip():
                continue

            # Remove the "X:" part from the first line if the block_content starts with it
            # e.g. if block_content is "1:\nName: Foo..."
            block_text = re.sub(r"^\d+:\s*\n?", "", block_content.strip(), count=1)

            name = "Unknown"
            description = "No description provided"
            role = "Undefined"

            lines = block_text.strip().split('\n')

            for line in lines:
                if line.startswith("Name:"):
                    name = line.replace("Name:", "").strip()
                elif line.startswith("Description:"):
                    description = line.replace("Description:", "").strip()
                elif line.startswith("Role:"):
                    role = line.replace("Role:", "").strip()

            # Basic validation: if critical fields are default, parsing might have been poor
            if name == "Unknown" and description == "No description provided" and role == "Undefined":
                print(f"CharacterSculptorAgent: Warning - Could not extract structured Name/Description/Role for a character block. Content: '{block_text[:100]}...'")
                # Decide if to skip this character or add with defaults
                continue # Skip adding this poorly parsed character

            characters.append(Character(
                id=0,
                novel_id=novel_id,
                name=name,
                description=description,
                role_in_story=role,
                creation_date=datetime.now(timezone.utc).isoformat()
            ))
        return characters

    def generate_and_save_characters(self, novel_id: int, narrative_outline: str, worldview_data: str, plot_summary: str, num_characters: int = 2) -> List[Character]:
        if num_characters <=0:
            print("CharacterSculptorAgent: Number of characters must be positive.")
            return []

        prompt = self._construct_prompt(narrative_outline, worldview_data, plot_summary, num_characters)

        print(f"CharacterSculptorAgent: Sending prompt for {num_characters} characters to LLM.")
        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-3.5-turbo", # Or make configurable
                max_tokens=300 * num_characters # Increased estimate: 300 tokens per character
            )
            print("CharacterSculptorAgent: Received response from LLM.")
        except Exception as e:
            print(f"CharacterSculptorAgent: Error during LLM call - {e}")
            return [] # Return empty list on LLM error

        if not llm_response_text:
            print("CharacterSculptorAgent: LLM returned an empty response.")
            return []

        parsed_characters = self._parse_llm_response(llm_response_text, novel_id)

        if not parsed_characters:
            print(f"CharacterSculptorAgent: Failed to parse characters from LLM response. Raw response snippet: {llm_response_text[:300]}...")
            return []

        saved_characters: List[Character] = []
        for char_data in parsed_characters:
            try:
                new_char_id = self.db_manager.add_character(
                    novel_id=char_data['novel_id'],
                    name=char_data['name'],
                    description=char_data['description'],
                    role_in_story=char_data['role_in_story']
                )
                char_data['id'] = new_char_id
                saved_characters.append(char_data)
                print(f"Saved character '{char_data['name']}' with ID {new_char_id} to DB.")
            except Exception as e:
                print(f"Error saving character {char_data['name']} to DB: {e}")
                # Optionally, decide if to continue saving others or fail all

        return saved_characters

if __name__ == "__main__":
    print("--- Testing CharacterSculptorAgent (Live LLM Call) ---")
    # This test now REQUIRES a valid OPENAI_API_KEY to be set in the environment or a .env file.
    # If a dummy key is used, the LLMClient initialization or the API call will fail.
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        print("Attempting to run with potentially dummy/invalid key. LLM calls WILL FAIL if key is not valid.")
        # Forcing exit if a purely dummy key is detected, as this test is for live calls.
        if "dummykeyforcharactersculptortesting" in os.getenv("OPENAI_API_KEY","") or \
           "dummykey" == os.getenv("OPENAI_API_KEY","").lower() : # common dummy patterns
            print("ERROR: Test cannot proceed with known dummy key patterns. Please set a real API key for live testing.")
            exit(1)


    test_db_name = "test_live_character_agent.db"
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    db_mngr = DatabaseManager(db_name=test_db_name)

    try:
        novel_id_1 = db_mngr.add_novel(
            user_theme="A cyberpunk detective investigating AI consciousness.",
            style_preferences="Noir, philosophical, gritty."
        )
        print(f"Dummy Novel created with ID: {novel_id_1}")

        sample_outline = "The detective, Kaito, is hired to find a rogue AI. He delves into the digital underworld, questioning what it means to be alive."
        sample_worldview = "Neo-Kyoto, 2077. A city of neon and shadows, where cybernetics are ubiquitous and AI are second-class citizens. The digital realm (Cyberspace) is a vast, unregulated frontier."
        sample_plot_summary = "Kaito's investigation leads him through AI speakeasies and encounters with digital revolutionaries, forcing him to confront his own prejudices about AI."

        agent = CharacterSculptorAgent(db_name=test_db_name)
        print("CharacterSculptorAgent initialized for live test.")

        print(f"\n--- Generating 2 characters for Novel ID: {novel_id_1} (Live Call) ---")
        generated_characters = agent.generate_and_save_characters(
            novel_id=novel_id_1,
            narrative_outline=sample_outline,
            worldview_data=sample_worldview,
            plot_summary=sample_plot_summary,
            num_characters=2
        )

        print("\nGenerated and Saved Characters:")
        if generated_characters:
            for char in generated_characters:
                print(f"  ID: {char['id']}, Name: {char['name']}, Role: {char['role_in_story']}")
            assert len(generated_characters) > 0, "Expected at least one character to be generated."
            assert generated_characters[0]['id'] != 0
            assert generated_characters[0]['novel_id'] == novel_id_1
        else:
            print("No characters were generated. This might be due to API key issues or LLM problems.")
            # This will likely fail if the API call failed.
            assert len(generated_characters) > 0, "Character generation failed, list is empty."


        # Verify in DB
        db_characters = db_mngr.get_characters_for_novel(novel_id_1)
        print(f"\nCharacters retrieved from DB for Novel {novel_id_1}: {len(db_characters)}")
        assert len(db_characters) == len(generated_characters)

    except ValueError as ve: # Raised by LLMClient or Agent if config is bad
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred during agent testing: {e}")
    finally:
        if os.path.exists(test_db_name):
            print(f"\nCleaning up test database: {test_db_name}")
            os.remove(test_db_name)
        else:
            print(f"\nTest database {test_db_name} not found or already cleaned up.")

    print("\n--- CharacterSculptorAgent (Live LLM Call) Test Finished ---")
