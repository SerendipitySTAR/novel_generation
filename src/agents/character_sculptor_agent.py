from typing import List
from datetime import datetime, timezone
from src.llm_abstraction.llm_client import LLMClient # Assuming LLMClient is in this path
from src.core.models import Character
from src.persistence.database_manager import DatabaseManager

class CharacterSculptorAgent:
    def __init__(self, db_name="novel_mvp.db"): # Added db_name parameter
        self.llm_client = LLMClient()
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

Character 2:
Name: [Character Name]
Description: [Brief description of appearance, personality, and background relevant to the story]
Role: [Their role in the story]
"""
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
        # Assuming "Character X:" is a reliable delimiter.
        character_blocks = llm_response.strip().split("Character ")[1:] # Skip the first empty part if response starts with "Character "

        for block in character_blocks:
            if not block.strip():
                continue

            name = "Unknown"
            description = "No description provided"
            role = "Undefined"

            lines = block.strip().split('\n')
            # Remove the "X:" part from the first line if present
            # lines[0] might be "1:", "2:", etc. or part of the name if not formatted perfectly

            current_line_idx = 0
            if ':' in lines[0] and lines[0].split(':')[0].strip().isdigit(): # Handles "1:", "2:", etc.
                current_line_idx = 0 # Start from the line that should contain "Name:"

            for line in lines[current_line_idx:]:
                if line.startswith("Name:"):
                    name = line.replace("Name:", "").strip()
                elif line.startswith("Description:"):
                    description = line.replace("Description:", "").strip()
                elif line.startswith("Role:"):
                    role = line.replace("Role:", "").strip()

            if name == "Unknown" and "Name:" not in block: # Fallback if parsing failed
                # Try a more lenient parse if structure is slightly off
                # This is a basic fallback, more robust parsing might be needed for varied LLM outputs
                potential_name_line = lines[0] if lines else ""
                if ':' in potential_name_line and not potential_name_line.split(':')[0].strip().isdigit():
                     name = potential_name_line.split(':',1)[1].strip() if len(potential_name_line.split(':',1)) > 1 else "Unknown"
                elif not ':' in potential_name_line: # If the first line is just the name
                    name = potential_name_line.strip()


            characters.append(Character(
                id=0, # Placeholder, will be updated after DB insertion
                novel_id=novel_id,
                name=name,
                description=description,
                role_in_story=role,
                creation_date=datetime.now(timezone.utc).isoformat()
            ))
        return characters

    def generate_and_save_characters(self, novel_id: int, narrative_outline: str, worldview_data: str, plot_summary: str, num_characters: int = 2) -> List[Character]:
        prompt = self._construct_prompt(narrative_outline, worldview_data, plot_summary, num_characters)

        # In a real scenario, you might need to handle potential errors from the LLM client
        # For now, we assume it returns a string.
        # llm_response = self.llm_client.generate_text(prompt, max_tokens=150 * num_characters) # Adjust max_tokens as needed

        # --- Mock LLM Response for testing without actual LLM calls ---
        print("--- MOCKING LLM CALL ---")
        mock_llm_responses = [
            f"""
Character 1:
Name: Commander Eva Rostova
Description: A stern but fair leader of the starship 'Odyssey', with piercing blue eyes and a scar above her left eyebrow from a past conflict. Haunted by a mission gone wrong.
Role: Protagonist

Character 2:
Name: Xylar
Description: A mysterious alien emissary from the Kepler-186f system, tall and slender with skin that shimmers with a faint bioluminescence. Their motives are unclear.
Role: Antagonist/Ally
            """,
            f"""
Character 1:
Name: Anya Sharma
Description: A brilliant young scientist, driven by curiosity and a desire to save her dying home world. Wears practical lab coats over colorful, mismatched socks.
Role: Protagonist

Character 2:
Name: General Vorlag
Description: A ruthless warlord from a rival faction, believes Anya's research is a threat to his power. Imposing figure, always clad in dark armor.
Role: Antagonist
            """
        ]
        llm_response = mock_llm_responses[novel_id % len(mock_llm_responses)] # Cycle through responses based on novel_id for variety in tests
        print(f"Mock LLM Response for novel_id {novel_id}:\n{llm_response}")
        # --- End Mock LLM Response ---

        parsed_characters = self._parse_llm_response(llm_response, novel_id)

        saved_characters: List[Character] = []
        for char_data in parsed_characters:
            try:
                # add_character should return the ID of the newly inserted character
                new_char_id = self.db_manager.add_character(
                    novel_id=char_data['novel_id'],
                    name=char_data['name'],
                    description=char_data['description'],
                    role_in_story=char_data['role_in_story']
                    # creation_date is handled by add_character in db_manager
                )
                # Update the character object with the ID returned from the database
                char_data['id'] = new_char_id
                saved_characters.append(char_data)
                print(f"Saved character '{char_data['name']}' with ID {new_char_id} to DB.")
            except Exception as e:
                print(f"Error saving character {char_data['name']}: {e}")
                # Optionally, re-raise or handle more gracefully

        return saved_characters

if __name__ == "__main__":
    print("--- Testing CharacterSculptorAgent ---")
    test_db_name = "test_character_agent.db"
    import os
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    # Initialize DatabaseManager for setting up test data
    db_mngr = DatabaseManager(db_name=test_db_name)

    # 1. Create a dummy novel
    print("Creating a dummy novel for testing...")
    try:
        novel_id_1 = db_mngr.add_novel(
            user_theme="A space opera about a lost colony.",
            style_preferences="Epic, with a touch of mystery."
        )
        print(f"Dummy Novel 1 created with ID: {novel_id_1}")

        novel_id_2 = db_mngr.add_novel(
            user_theme="A fantasy story about a magical artifact.",
            style_preferences="High fantasy, descriptive."
        )
        print(f"Dummy Novel 2 created with ID: {novel_id_2}")

    except Exception as e:
        print(f"Error creating dummy novel: {e}")
        # Clean up before exiting if novel creation fails
        if os.path.exists(test_db_name):
            os.remove(test_db_name)
        raise

    # Sample data for the agent
    narrative_outline_1 = "The colony ship 'Hope' crash-lands on an uncharted planet. Survivors must adapt and explore."
    worldview_data_1 = "The planet is lush and teeming with alien life, some hostile, some benign. Ancient ruins hint at a lost civilization."
    plot_summary_1 = "The colonists, led by a reluctant captain, search for a way to signal Earth while battling internal strife and external threats."

    narrative_outline_2 = "A young sorceress discovers a powerful, ancient staff."
    worldview_data_2 = "A realm where magic is fading, and technology is slowly rising. The staff is a relic from the Age of Mages."
    plot_summary_2 = "The sorceress must learn to control the staff's power and protect it from those who would misuse it, including a technologically advanced empire."

    # Instantiate the agent
    agent = CharacterSculptorAgent(db_name=test_db_name)

    # Generate and save characters for Novel 1
    print(f"\n--- Generating characters for Novel ID: {novel_id_1} ---")
    generated_characters_1 = agent.generate_and_save_characters(
        novel_id=novel_id_1,
        narrative_outline=narrative_outline_1,
        worldview_data=worldview_data_1,
        plot_summary=plot_summary_1,
        num_characters=2
    )
    print("\nGenerated and Saved Characters for Novel 1:")
    for char in generated_characters_1:
        print(f"  ID: {char['id']}, Name: {char['name']}, Role: {char['role_in_story']}")

    assert len(generated_characters_1) == 2
    assert generated_characters_1[0]['id'] != 0 # Should have a DB ID
    assert generated_characters_1[0]['novel_id'] == novel_id_1

    # Verify in DB for Novel 1
    db_characters_1 = db_mngr.get_characters_for_novel(novel_id_1)
    print(f"\nCharacters retrieved from DB for Novel {novel_id_1}: {len(db_characters_1)}")
    assert len(db_characters_1) == 2
    # Check if names match (order might vary based on DB retrieval, so check existence)
    db_char_names_1 = {c['name'] for c in db_characters_1}
    gen_char_names_1 = {c['name'] for c in generated_characters_1}
    assert db_char_names_1 == gen_char_names_1


    # Generate and save characters for Novel 2
    print(f"\n--- Generating characters for Novel ID: {novel_id_2} ---")
    generated_characters_2 = agent.generate_and_save_characters(
        novel_id=novel_id_2,
        narrative_outline=narrative_outline_2,
        worldview_data=worldview_data_2,
        plot_summary=plot_summary_2,
        num_characters=2 # Using the second mock response
    )
    print("\nGenerated and Saved Characters for Novel 2:")
    for char in generated_characters_2:
        print(f"  ID: {char['id']}, Name: {char['name']}, Role: {char['role_in_story']}")

    assert len(generated_characters_2) == 2
    assert generated_characters_2[0]['id'] != 0
    assert generated_characters_2[0]['novel_id'] == novel_id_2

    # Verify in DB for Novel 2
    db_characters_2 = db_mngr.get_characters_for_novel(novel_id_2)
    print(f"\nCharacters retrieved from DB for Novel {novel_id_2}: {len(db_characters_2)}")
    assert len(db_characters_2) == 2
    db_char_names_2 = {c['name'] for c in db_characters_2}
    gen_char_names_2 = {c['name'] for c in generated_characters_2}
    assert db_char_names_2 == gen_char_names_2


    # Clean up test database
    print("\nCleaning up test database...")
    if os.path.exists(test_db_name):
        os.remove(test_db_name)
    print(f"Removed '{test_db_name}'.")
    print("--- CharacterSculptorAgent Test Finished ---")
