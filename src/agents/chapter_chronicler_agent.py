import os
from typing import Optional
from datetime import datetime, timezone
from dotenv import load_dotenv

from src.llm_abstraction.llm_client import LLMClient
from src.persistence.database_manager import DatabaseManager
from src.core.models import Chapter

class ChapterChroniclerAgent:
    def __init__(self, db_name: str = "novel_mvp.db"):
        # LLMClient will load .env and check for OPENAI_API_KEY itself
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"Error initializing LLMClient in ChapterChroniclerAgent: {e}")
            print("Ensure OPENAI_API_KEY is set for LLMClient.")
            raise # Re-raise for clarity that agent cannot function
        self.db_manager = DatabaseManager(db_name=db_name)

    def _construct_prompt(self, chapter_brief: str, current_chapter_plot_summary: str, style_preferences: str) -> str:
        prompt = f"""
You are a master storyteller tasked with writing a chapter for an ongoing novel.
Carefully review the comprehensive Chapter Brief provided below, which contains overall novel context, previous events, character details, and relevant lore.

**Chapter Brief:**
---
{chapter_brief}
---

**Specific Instructions for this Chapter:**
1.  **Plot Focus:** The primary events of this chapter must align with the following summary: "{current_chapter_plot_summary}"
2.  **Writing Style:** Adhere to the following style preferences: "{style_preferences}"
3.  **Word Count:** Aim for approximately 500-1000 words for the chapter content.
4.  **Output Structure:** You MUST provide your response in the following exact format, with "Title:", "Content:", and "Summary:" as clear delimiters:

Title: [Your Generated Chapter Title Here]

Content:
[Your full chapter text goes here. Make sure it's engaging and moves the plot forward according to the plot focus.]

Summary: [Provide a concise summary (2-4 sentences) of the key events that transpired in this chapter.]

---
Begin writing the chapter now.
"""
        return prompt

    def _parse_llm_response(self, llm_response: str, novel_id: int, chapter_number: int) -> Optional[Chapter]:
        try:
            title_marker = "Title:"
            content_marker = "Content:"
            summary_marker = "Summary:"

            title_start = llm_response.find(title_marker)
            content_start = llm_response.find(content_marker)
            summary_start = llm_response.find(summary_marker)

            if not (title_start != -1 and content_start != -1 and summary_start != -1 and \
                    title_start < content_start < summary_start):
                print("Error: LLM response did not contain the expected 'Title:', 'Content:', and 'Summary:' markers in order.")
                return None

            extracted_title = llm_response[title_start + len(title_marker):content_start].strip()

            # Check if there's an empty line or more specific delimiter after title before content
            # This handles cases where Content: might be on the next line without a blank line after title text

            extracted_content = llm_response[content_start + len(content_marker):summary_start].strip()
            extracted_summary = llm_response[summary_start + len(summary_marker):].strip()

            if not extracted_title or not extracted_content or not extracted_summary:
                print("Error: Extracted title, content, or summary is empty.")
                return None

            return Chapter(
                id=0,  # Placeholder, will be updated after DB insertion
                novel_id=novel_id,
                chapter_number=chapter_number,
                title=extracted_title,
                content=extracted_content,
                summary=extracted_summary,
                creation_date=datetime.now(timezone.utc).isoformat()
            )
        except Exception as e:
            print(f"An error occurred during LLM response parsing: {e}")
            return None

    def generate_and_save_chapter(self, novel_id: int, chapter_number: int, chapter_brief: str,
                                  current_chapter_plot_summary: str, style_preferences: str) -> Optional[Chapter]:
        prompt = self._construct_prompt(chapter_brief, current_chapter_plot_summary, style_preferences)

        # --- Mock LLM Response for testing without actual LLM calls ---
        print("--- MOCKING LLM CALL for ChapterChroniclerAgent ---")
        # This mock response should match the structure expected by _parse_llm_response
        mock_llm_response_text = f"""
Title: The Shadow Protocol

Content:
The console flickered to life, casting eerie green shadows across Elara's determined face. "The Shadow Protocol," she murmured, her fingers dancing across the holographic interface. "If Zorg activated it, we're running out of time."
Gorok grunted from behind her, polishing his already gleaming axe. "Means more tin cans to crack," he said, not entirely unhappily.
Lyra consulted her datapad. "According to these schematics, the protocol reroutes primary power to Zorg's personal dreadnought, 'The Despoiler'. It also activates a cloaking field around his command fleet, making them nearly impossible to track."
"Nearly," Elara echoed, a glint in her eye. "But the Starlight Wand operates on cosmic frequencies, not standard tech. It might just give us the edge we need to find him before he consolidates his power."
Their small ship, 'The Wanderer', hummed through the void, a tiny speck against the vast, uncaring canvas of space. The fate of countless worlds rested on their desperate gamble.

Summary: Elara, Gorok, and Lyra learn that Zorg has activated the 'Shadow Protocol', rerouting power to his flagship and cloaking his fleet. They realize the Starlight Wand might be their only way to track him.
"""
        llm_response_text = mock_llm_response_text
        # To use actual LLM:
        # try:
        #     llm_response_text = self.llm_client.generate_text(prompt, max_tokens=1500) # Adjust max_tokens as needed
        # except Exception as e:
        #     print(f"Error calling LLM: {e}")
        #     return None
        # --- End Mock LLM Response ---

        if not llm_response_text:
            print("No response from LLM (or mock).")
            return None

        parsed_chapter = self._parse_llm_response(llm_response_text, novel_id, chapter_number)

        if parsed_chapter:
            try:
                new_chapter_id = self.db_manager.add_chapter(
                    novel_id=parsed_chapter['novel_id'],
                    chapter_number=parsed_chapter['chapter_number'],
                    title=parsed_chapter['title'],
                    content=parsed_chapter['content'],
                    summary=parsed_chapter['summary']
                    # creation_date is handled by add_chapter in db_manager based on its own logic or model default
                )
                parsed_chapter['id'] = new_chapter_id
                print(f"Chapter '{parsed_chapter['title']}' (Chapter {parsed_chapter['chapter_number']}) saved with ID {new_chapter_id} for Novel ID {novel_id}.")
                return parsed_chapter
            except Exception as e:
                print(f"Error saving chapter to database: {e}")
                return None
        else:
            print("Failed to parse LLM response into a chapter.")
            return None

if __name__ == "__main__":
    print("--- Testing ChapterChroniclerAgent ---")

    # API Key Check (LLMClient will need this, though it's mocked here)
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for testing ChapterChroniclerAgent (via LLMClient)...")
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEY=\"sk-dummykeyforchapterchroniclertesting\"\n")

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"): # LLMClient constructor will raise error if key not found
        print("CRITICAL: OPENAI_API_KEY not found. LLMClient initialization will fail.")
        print("Please ensure OPENAI_API_KEY is set in your environment or a .env file.")
        # Exiting because LLMClient is a direct dependency for __init__
        exit(1)
    elif "dummykey" in os.getenv("OPENAI_API_KEY", ""):
         print("WARNING: Using a dummy OPENAI_API_KEY. Actual LLM calls are mocked for this test.")


    test_sql_db_name = "test_chapter_agent.db"
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)

    # Initialize DatabaseManager for setup and agent
    db_mngr = DatabaseManager(db_name=test_sql_db_name) # Ensures tables are created

    # 1. Create a dummy novel
    novel_id_for_chapter_test = db_mngr.add_novel(
        user_theme="A quest to find a legendary artifact.",
        style_preferences="Epic fantasy, rich descriptions, character-driven."
    )
    print(f"Created Novel ID for testing: {novel_id_for_chapter_test}")

    # 2. Sample data for generating a chapter
    # In a real scenario, this brief would be generated by ContextSynthesizerAgent
    sample_chapter_brief = """
Novel Theme: A quest to find a legendary artifact.
Style: Epic fantasy, rich descriptions, character-driven.

Overall Outline: Heroes must find the Sunstone to dispel the encroaching darkness.
Worldview: A realm where magic is fading and ancient evils stir.
Main Plot Arc: The chosen heroes journey through perilous lands, face trials, and confront the Dark Lord.

Previous Events:
Chapter 1 (The Call to Adventure) Summary: The village elder reveals the prophecy of the Sunstone to Kaelen, a young warrior. A shadow creature attacks the village, solidifying the threat.

Focus Characters for this Chapter:
Character: Kaelen - Role: Protagonist. Description: Young, brave, but untested warrior from a small village.
Character: Lyra - Role: Mentor. Description: Wise sorceress, guides Kaelen, knows ancient lore.

Current Chapter Focus (Chapter 2): Kaelen and Lyra leave the village and begin their journey into the Whispering Woods, seeking the first map piece.

Relevant Lore and Context:
The Whispering Woods are rumored to be enchanted and guarded by ancient spirits. Map pieces are said to be hidden in places of power.
"""
    chapter_plot_summary = "Kaelen and Lyra enter the Whispering Woods. They face an illusion trial set by a forest spirit and successfully retrieve the first piece of the map to the Sunstone."
    novel_style_prefs = "Epic fantasy, vivid imagery, focus on character emotions and dialogue, moderate pacing."
    target_chapter_num = 2 # Assuming chapter 1 exists as per the brief

    # 3. Instantiate ChapterChroniclerAgent
    try:
        chronicler_agent = ChapterChroniclerAgent(db_name=test_sql_db_name)
        print("ChapterChroniclerAgent initialized.")
    except ValueError as e: # Catch error if LLMClient init fails due to API key
        print(f"Failed to initialize ChapterChroniclerAgent: {e}")
        if os.path.exists(test_sql_db_name): os.remove(test_sql_db_name)
        if os.path.exists(".env") and "dummykeyforchapterchroniclertesting" in open(".env").read(): os.remove(".env")
        exit(1)


    # 4. Generate and save the chapter
    print(f"\nGenerating Chapter {target_chapter_num} for Novel ID {novel_id_for_chapter_test}...")
    generated_chapter = chronicler_agent.generate_and_save_chapter(
        novel_id=novel_id_for_chapter_test,
        chapter_number=target_chapter_num,
        chapter_brief=sample_chapter_brief,
        current_chapter_plot_summary=chapter_plot_summary,
        style_preferences=novel_style_prefs
    )

    # 5. Print and verify
    if generated_chapter:
        print("\n--- Generated Chapter ---")
        print(f"ID: {generated_chapter['id']}")
        print(f"Novel ID: {generated_chapter['novel_id']}")
        print(f"Chapter Number: {generated_chapter['chapter_number']}")
        print(f"Title: {generated_chapter['title']}")
        print(f"Content (first 100 chars): {generated_chapter['content'][:100]}...")
        print(f"Summary: {generated_chapter['summary']}")
        print(f"Creation Date: {generated_chapter['creation_date']}")
        print("--- End of Generated Chapter ---")

        assert generated_chapter['id'] != 0, "Chapter ID was not updated after DB save."
        assert generated_chapter['novel_id'] == novel_id_for_chapter_test
        assert generated_chapter['chapter_number'] == target_chapter_num
        assert generated_chapter['title'] == "The Shadow Protocol" # From mock response
        assert "The console flickered to life" in generated_chapter['content'] # From mock response
        assert "Elara, Gorok, and Lyra learn that Zorg has activated" in generated_chapter['summary'] # From mock response

        # Verify in DB
        db_chapter = db_mngr.get_chapter_by_id(generated_chapter['id'])
        assert db_chapter is not None, "Chapter not found in DB by ID."
        if db_chapter: # mypy check
            assert db_chapter['title'] == generated_chapter['title'], "DB title mismatch."
            assert db_chapter['content'] == generated_chapter['content'], "DB content mismatch."
        print("\nChapter successfully generated, saved, and verified in DB.")
    else:
        print("\nChapter generation and saving failed.")
        # This assertion will fail if chapter generation failed, indicating a problem
        assert generated_chapter is not None, "Chapter generation returned None."


    # 6. Clean up
    print("\nCleaning up test database...")
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)
        print(f"Removed SQL DB: {test_sql_db_name}")

    if os.path.exists(".env") and "dummykeyforchapterchroniclertesting" in open(".env").read():
        print("Removing dummy .env file for ChapterChroniclerAgent test...")
        os.remove(".env")

    print("--- ChapterChroniclerAgent Test Finished ---")
