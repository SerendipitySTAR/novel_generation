import os
import re
from typing import Optional, Dict, Any # Added Dict, Any for TypedDict compatibility
from datetime import datetime, timezone
from dotenv import load_dotenv

from src.llm_abstraction.llm_client import LLMClient
from src.persistence.database_manager import DatabaseManager
from src.core.models import Chapter

class ChapterChroniclerAgent:
    def __init__(self, db_name: str = "novel_mvp.db"):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"ChapterChroniclerAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise
        except Exception as e:
            print(f"ChapterChroniclerAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise
        self.db_manager = DatabaseManager(db_name=db_name)

    def _construct_prompt(self, chapter_brief: str, current_chapter_plot_summary: str, style_preferences: str) -> str:
        # Refined prompt
        prompt = f"""You are a master storyteller tasked with writing a chapter for an ongoing novel.
Your goal is to produce engaging narrative content that adheres strictly to the provided plot points and established style.

**Chapter Brief:**
---
{chapter_brief}
---

**Specific Instructions for this Chapter:**
1.  **Plot Adherence:** The events of this chapter MUST precisely follow this plot summary: "{current_chapter_plot_summary}". Do not deviate, introduce unasked-for plot twists, or leave out key events from this summary.
2.  **Writing Style:** Maintain the following style: "{style_preferences}". This includes tone, pacing, vocabulary, and narrative perspective.
3.  **Content Focus:** Concentrate on developing the scenes and interactions described in the plot summary for this chapter. Show, don't just tell.
4.  **Word Count:** Target a chapter length of approximately 700-1200 words.
5.  **Output Format:** You MUST provide your response in the following exact format, with "Title:", "Content:", and "Summary:" as clear section delimiters. Each delimiter must be on its own line.

Title: [Your Generated Chapter Title Here]

Content:
[Your full chapter text goes here. Ensure it is well-formatted with paragraphs.]

Summary: [Provide a concise summary (2-4 sentences) of ONLY the key events that transpired in THIS chapter, as you have written them.]

---
Begin writing the chapter now, following all instructions carefully.
"""
        return prompt

    def _parse_llm_response(self, llm_response: str, novel_id: int, chapter_number: int) -> Optional[Dict[str, Any]]: # Return type changed to Dict for Chapter TypedDict
        try:
            # Make regex non-greedy for title and content to avoid over-matching if Summary is missing.
            # Using re.IGNORECASE to be more robust against "title:" vs "Title:"
            title_match = re.search(r"Title:(.*?)Content:", llm_response, re.DOTALL | re.IGNORECASE)
            content_match = re.search(r"Content:(.*?)Summary:", llm_response, re.DOTALL | re.IGNORECASE)
            summary_match = re.search(r"Summary:(.*)", llm_response, re.DOTALL | re.IGNORECASE)

            if title_match and content_match and summary_match:
                title = title_match.group(1).strip()
                content = content_match.group(1).strip()
                summary = summary_match.group(1).strip()

                if not title : title = f"Chapter {chapter_number} (Untitled)"
                if not content:
                    print("ChapterChroniclerAgent: Warning - Parsed empty string for content.")
                    # Fallback: take everything after title if content and summary parsing failed but title worked
                    if not summary_match and title_match: # This condition might be tricky if title_match implies content_match should also be there
                        print("ChapterChroniclerAgent: Using fallback for content: everything after Title marker (ends before Summary if Summary exists, else to end).")
                        # If summary_match failed, content is everything after "Title:[title]\nContent:"
                        # This needs careful splitting if Summary marker is truly absent.
                        # A simpler robust fallback if content is empty:
                        temp_content_start = re.search(r"Content:", llm_response, re.IGNORECASE)
                        if temp_content_start:
                            content = llm_response[temp_content_start.end():].strip() # Takes all after "Content:"
                            # If summary was also not found, this content will include whatever was meant for summary.
                            # This might be acceptable if summary is optional or can be re-generated.
                            if summary_match: # If summary was found, try to trim it from content
                                content = content.split(summary_match.group(0))[0].strip()

                        if not content: # If still no content
                             print("ChapterChroniclerAgent: Error - Content is essential and could not be parsed or recovered.")
                             return None
                    else: # Content is empty, but summary_match exists, this is problematic.
                         print("ChapterChroniclerAgent: Error - Content is empty but Summary marker was found. Cannot proceed.")
                         return None
                if not summary: summary = "Summary was not generated by LLM or parsing failed."

                # Return as dict compatible with Chapter TypedDict
                return {
                    "id": 0,
                    "novel_id": novel_id,
                    "chapter_number": chapter_number,
                    "title": title,
                    "content": content,
                    "summary": summary,
                    "creation_date": datetime.now(timezone.utc).isoformat()
                }
            else:
                missing_parts = []
                if not title_match: missing_parts.append("Title")
                if not content_match: missing_parts.append("Content")
                if not summary_match: missing_parts.append("Summary")
                print(f"ChapterChroniclerAgent: Error - Could not parse [{', '.join(missing_parts)}] from LLM response. Response (first 500 chars): {llm_response[:500]}")
                # Attempt a more desperate parse if all else fails, looking for any text
                if llm_response.strip():
                    print("ChapterChroniclerAgent: Attempting desperate parse - using whole response as content.")
                    return {
                        "id": 0, "novel_id": novel_id, "chapter_number": chapter_number,
                        "title": f"Chapter {chapter_number} (Parsing Failed)",
                        "content": llm_response.strip(),
                        "summary": "Full response used as content due to parsing failure.",
                        "creation_date": datetime.now(timezone.utc).isoformat()
                    }
                return None
        except Exception as e:
            print(f"ChapterChroniclerAgent: Exception during LLM response parsing - {e}")
            return None

    def generate_and_save_chapter(self, novel_id: int, chapter_number: int, chapter_brief: str,
                                  current_chapter_plot_summary: str, style_preferences: str) -> Optional[Chapter]:
        prompt = self._construct_prompt(chapter_brief, current_chapter_plot_summary, style_preferences)

        print(f"ChapterChroniclerAgent: Sending prompt for Chapter {chapter_number} to LLM.")
        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-3.5-turbo",
                temperature=0.7,
                max_tokens=2000
            )
            print(f"ChapterChroniclerAgent: Received response from LLM for Chapter {chapter_number}.")
        except Exception as e:
            print(f"ChapterChroniclerAgent: Error during LLM call for Chapter {chapter_number} - {e}")
            return None

        if not llm_response_text:
            print(f"ChapterChroniclerAgent: LLM returned an empty response for Chapter {chapter_number}.")
            return None

        # The _parse_llm_response now returns a Dict, so we need to cast/convert it if Chapter object is strictly needed here
        parsed_chapter_data = self._parse_llm_response(llm_response_text, novel_id, chapter_number)

        if parsed_chapter_data:
            # Convert dict to Chapter TypedDict for type consistency if needed, or use as is if methods accept Dict.
            # For DatabaseManager.add_chapter, it expects individual args matching Chapter fields.
            try:
                new_chapter_id = self.db_manager.add_chapter(
                    novel_id=parsed_chapter_data['novel_id'],
                    chapter_number=parsed_chapter_data['chapter_number'],
                    title=parsed_chapter_data['title'],
                    content=parsed_chapter_data['content'],
                    summary=parsed_chapter_data['summary']
                    # creation_date is handled by db_manager.add_chapter's internal logic
                )
                # Create the final Chapter object with the new ID
                final_chapter_obj = Chapter(
                    id=new_chapter_id,
                    novel_id=parsed_chapter_data['novel_id'],
                    chapter_number=parsed_chapter_data['chapter_number'],
                    title=parsed_chapter_data['title'],
                    content=parsed_chapter_data['content'],
                    summary=parsed_chapter_data['summary'],
                    creation_date=parsed_chapter_data['creation_date'] # Use parsed creation date
                )
                print(f"Chapter '{final_chapter_obj['title']}' (Chapter {final_chapter_obj['chapter_number']}) saved with ID {new_chapter_id} for Novel ID {novel_id}.")
                return final_chapter_obj
            except Exception as e:
                print(f"ChapterChroniclerAgent: Error saving chapter {chapter_number} to database: {e}")
                return None
        else:
            print(f"ChapterChroniclerAgent: Failed to parse LLM response into Chapter {chapter_number}. Raw response snippet: {llm_response_text[:300]}")
            return None

if __name__ == "__main__":
    print("--- Testing ChapterChroniclerAgent (Live LLM Call) ---")
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        if "dummykey" in os.getenv("OPENAI_API_KEY",""): # More generic dummy check
             print("ERROR: Test cannot reliably proceed with a known dummy key pattern. Please set a real API key.")
             exit(1)

    test_sql_db_name = "test_live_chapter_agent_refined.db"
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)

    db_mngr = DatabaseManager(db_name=test_sql_db_name)
    novel_id_for_test = -1

    try:
        novel_id_for_test = db_mngr.add_novel(
            user_theme="A haunted library where books write their own stories, and a young librarian must uncover the library's oldest secret.",
            style_preferences="Gothic mystery with elements of magical realism, atmospheric, detailed descriptions, character-focused narrative."
        )
        print(f"Created Novel ID for testing: {novel_id_for_test}")

        sample_brief = f"""
Novel Theme: A haunted library where books write their own stories, and a young librarian must uncover the library's oldest secret.
Style: Gothic mystery with elements of magical realism, atmospheric, detailed descriptions, character-focused narrative.
Overall Outline: Elara, a new librarian, notices books changing. She investigates, discovering the library is sentient and powered by a trapped spirit. She must choose to free the spirit or preserve the library's magic.
Worldview: The Library of Alexandria was not destroyed but hidden, its consciousness growing over millennia. It manifests new wings, corridors, and books based on the collective unconscious. Its magic is subtle, usually.
Main Plot Arc: Discovery of changing books -> Investigation of library's hidden sections -> Encounter with manifestations of the library's consciousness -> Uncovering the trapped spirit's story -> Climax involving a choice that affects the library and Elara.
Previous Events: This is the first chapter. No prior events in this novel's timeline.
Focus Characters for this Chapter:
Character: Elara - Role: Protagonist. Description: Young, inquisitive, loves books more than people. Inherited the librarian post from a distant aunt. Skeptical but open-minded.
Relevant Lore and Context: The library is known as the "Whispering Athenaeum." Locals avoid it. Legends say it chooses its librarian.
"""
        chapter_plot_summary = "Elara arrives at the imposing, ancient library. She meets the only other staff member, the cryptic groundskeeper Mr. Hemlock. During her first night shift, she witnesses a book's title changing on its spine and then its content altering when she opens it."
        novel_style = "Gothic mystery, atmospheric, detailed descriptions, character-focused narrative, slow-burn suspense."
        target_chapter_number = 1

        agent = ChapterChroniclerAgent(db_name=test_sql_db_name)
        print("ChapterChroniclerAgent initialized for live test.")

        print(f"\nGenerating Chapter {target_chapter_number} for Novel ID {novel_id_for_test} (Live Call)...")
        generated_chapter = agent.generate_and_save_chapter(
            novel_id=novel_id_for_test,
            chapter_number=target_chapter_number,
            chapter_brief=sample_brief,
            current_chapter_plot_summary=chapter_plot_summary,
            style_preferences=novel_style
        )

        if generated_chapter:
            print("\n--- Generated Chapter ---")
            print(f"ID: {generated_chapter['id']}")
            print(f"Novel ID: {generated_chapter['novel_id']}")
            print(f"Chapter Number: {generated_chapter['chapter_number']}")
            print(f"Title: {generated_chapter['title']}")
            print(f"Content (first 300 chars): {generated_chapter['content'][:300]}...")
            print(f"Summary: {generated_chapter['summary']}")
            print(f"Creation Date: {generated_chapter['creation_date']}")

            assert generated_chapter['id'] != 0
            assert len(generated_chapter['title']) > 0
            assert len(generated_chapter['content']) > 100 # Expect more than a short paragraph
            assert len(generated_chapter['summary']) > 10

            db_chapter = db_mngr.get_chapter_by_id(generated_chapter['id'])
            assert db_chapter is not None
            if db_chapter:
                assert db_chapter['title'] == generated_chapter['title']
            print("\nChapter successfully generated, saved, and minimally verified in DB.")
        else:
            print("\nChapter generation and saving FAILED. This might be due to API key issues or LLM problems.")
            assert generated_chapter is not None, "Chapter generation returned None."

    except ValueError as ve:
        print(f"Configuration or Input Error: {ve}")
    except Exception as e:
        print(f"An error occurred during agent testing: {e}")
        print("Ensure your OPENAI_API_KEY is correctly set and valid.")
    finally:
        if os.path.exists(test_sql_db_name):
            print(f"\nCleaning up test database: {test_sql_db_name}")
            os.remove(test_sql_db_name)
        else:
            print(f"\nTest database {test_sql_db_name} not found or already cleaned up.")

    print("\n--- ChapterChroniclerAgent (Live LLM Call) Test Finished ---")
