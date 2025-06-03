import os
import re
from typing import Optional, Dict, Any
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
        # Prompt refined to be more explicit about using the plot summary and brief,
        # and the RAG context if demarcated in the brief.
        prompt = f"""You are a novelist writing a chapter. Adhere to the style: {style_preferences}.

        Chapter Brief (context, characters, lore):
        --- BEGIN CHAPTER BRIEF ---
        {chapter_brief}
        --- END CHAPTER BRIEF ---

        Specific Plot for THIS Chapter: {current_chapter_plot_summary}

        Your primary goal for this chapter's content is to flesh out the 'Specific Plot for THIS Chapter'.
        Use the 'Chapter Brief' for essential background, character states, and relevant lore to ensure consistency.
        Weave these elements together to write a compelling narrative for this chapter.
        Refer to any 'Relevant Lore and Context' (often demarcated by '--- RELEVANT LORE AND CONTEXT ---') provided in the brief.

        Your output MUST be structured with these exact headings on new lines:
        Title:
        [A compelling title for this chapter. Single line.]

        # Instructions for Content generation - focused on improving narrative quality.
        Content:
        [The full chapter text. Aim for approximately 700-1000 words.
        It is CRUCIAL that the Content directly enacts and expands upon the 'Specific Plot for THIS Chapter' provided.
        - Show, Don't Tell: Focus on vivid descriptions of settings, character actions, and emotions.
        - Dialogue: Incorporate meaningful dialogue that reveals character personality, motivations, and advances the plot.
        - Character Consistency: Ensure character behaviors, decisions, and speech patterns are consistent with their detailed profiles and motivations as described in the 'Chapter Brief'.
        - Utilize Context: If the 'Chapter Brief' includes a 'RELEVANT LORE AND CONTEXT (from Knowledge Base)' section, subtly weave these details into the narrative where appropriate to enhance world-building and consistency. Avoid large blocks of exposition (info-dumping).
        - Pacing and Flow: Maintain a good narrative pace suitable for the chapter's events and tone.]

        Summary:
        [A concise 2-3 sentence summary of the key plot advancements, character developments, and critical outcomes that occurred *within this chapter's Content only*.]

        Ensure "Title:", "Content:", and "Summary:" are on their own lines. Do not add any other text before "Title:", or after the "Summary:" text.
        """
        return prompt

    def _parse_llm_response(self, llm_response: str, novel_id: int, chapter_number: int) -> Optional[Dict[str, Any]]:
        parsing_log_prefix = f"ChapterChroniclerAgent (Ch {chapter_number}):"
        try:
            title = f"Chapter {chapter_number} (Untitled)"
            content = "Content not generated."
            summary = "Summary not generated."
            parse_path = "Initial" # To log parsing attempts

            # Robust regex for Title, Content, Summary
            # Allow for potential whitespace variations and ensure markers are at the start of a line.
            # Capture content non-greedily.
            title_regex = r"^\s*Title:(.*?)$"
            # Content: captures everything until "Summary:" or end of string if "Summary:" is missing
            content_regex = r"^\s*Content:(.*?)(?=(?:\n\s*Summary:)|$)"
            summary_regex = r"^\s*Summary:(.*)$"

            title_match = re.search(title_regex, llm_response, re.MULTILINE | re.IGNORECASE | re.DOTALL)
            content_match = re.search(content_regex, llm_response, re.MULTILINE | re.IGNORECASE | re.DOTALL)
            summary_match = re.search(summary_regex, llm_response, re.MULTILINE | re.IGNORECASE | re.DOTALL)

            if title_match:
                title_text = title_match.group(1).strip()
                if title_text:
                    title = title_text
                    parse_path += "->TitleOK"
                else:
                    parse_path += "->TitleEmpty"
                    print(f"{parsing_log_prefix} Info - 'Title:' marker found but content is empty. Using default.")
            else:
                parse_path += "->TitleFail"
                print(f"{parsing_log_prefix} Warning - 'Title:' marker not found or not at start of a line.")

            if content_match:
                content_text = content_match.group(1).strip()
                if content_text:
                    content = content_text
                    parse_path += "->ContentOK"
                else:
                    parse_path += "->ContentEmpty"
                    print(f"{parsing_log_prefix} Warning - 'Content:' marker found but content is empty.")
            else:
                parse_path += "->ContentFail"
                print(f"{parsing_log_prefix} Warning - 'Content:' marker not found or structured incorrectly relative to 'Summary:'.")

            if summary_match:
                summary_text = summary_match.group(1).strip()
                if summary_text:
                    summary = summary_text
                    parse_path += "->SummaryOK"
                else:
                    parse_path += "->SummaryEmpty"
                    print(f"{parsing_log_prefix} Info - 'Summary:' marker found but content is empty. Using default.")
            else:
                parse_path += "->SummaryFail"
                print(f"{parsing_log_prefix} Warning - 'Summary:' marker not found or not at start of a line.")

            # Desperate Parse Fallback Logic
            if content == "Content not generated." and llm_response.strip():
                parse_path += "->DesperateParse"
                print(f"{parsing_log_prefix} Info - Content not found via primary parsing. Attempting desperate fallback.")

                temp_content = llm_response # Start with the full response

                # If title was found, try to remove it and anything before it
                if title_match and title_match.group(0) in temp_content:
                    temp_content = temp_content.split(title_match.group(0), 1)[-1]
                    parse_path += "->DP_TitleStrip"

                # If summary was found, try to remove it and anything after it
                # This is tricky if summary is embedded within content.
                # We assume if Summary marker was found, it's *after* the main content.
                if summary_match and summary_match.group(0) in temp_content:
                    temp_content = temp_content.split(summary_match.group(0), 1)[0]
                    parse_path += "->DP_SummaryStrip"

                # Remove "Content:" marker itself if it's at the beginning of what's left
                temp_content = re.sub(r"^\s*Content:\s*", "", temp_content.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()

                if temp_content:
                    content = temp_content
                    parse_path += "->DP_ContentFound"
                    print(f"{parsing_log_prefix} Info - Desperate parse assigned remaining text to content.")
                else:
                    parse_path += "->DP_ContentFail"
                    print(f"{parsing_log_prefix} Error - Desperate parse for content also resulted in empty content.")

            # Final check: If title was NOT found, but content was (either normally or via desperate parse)
            if not title_match and content != "Content not generated.":
                parse_path += "->TitleMissingContentExists"
                print(f"{parsing_log_prefix} Info - Title was not parsed, but content exists. Using default title.")
                # Title remains the default "Chapter X (Untitled)"

            if content == "Content not generated.":
                 print(f"{parsing_log_prefix} Error - Content section remains empty after all parsing attempts. Response (first 500 chars): {llm_response[:500]}")
                 print(f"{parsing_log_prefix} Final Parse Path: {parse_path}")
                 return None

            print(f"{parsing_log_prefix} Final Parse Path: {parse_path}")
            return {
                "id": 0, "novel_id": novel_id, "chapter_number": chapter_number,
                "title": title, "content": content, "summary": summary,
                "creation_date": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            print(f"{parsing_log_prefix} Exception during LLM response parsing - {e}. Response (first 500 chars): {llm_response[:500]}")
            return None

    def generate_and_save_chapter(self, novel_id: int, chapter_number: int, chapter_brief: str,
                                  current_chapter_plot_summary: str, style_preferences: str) -> Optional[Chapter]:
        prompt = self._construct_prompt(chapter_brief, current_chapter_plot_summary, style_preferences)

        print(f"ChapterChroniclerAgent: Sending prompt for Chapter {chapter_number} to LLM.")
        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt, model_name="gpt-3.5-turbo", temperature=0.7, max_tokens=2000
            )
            print(f"ChapterChroniclerAgent: Received response from LLM for Chapter {chapter_number}.")
        except Exception as e:
            print(f"ChapterChroniclerAgent: Error during LLM call for Chapter {chapter_number} - {e}")
            return None

        if not llm_response_text:
            print(f"ChapterChroniclerAgent: LLM returned an empty response for Chapter {chapter_number}.")
            return None

        parsed_chapter_data = self._parse_llm_response(llm_response_text, novel_id, chapter_number)

        if parsed_chapter_data:
            try:
                new_chapter_id = self.db_manager.add_chapter(
                    novel_id=parsed_chapter_data['novel_id'],
                    chapter_number=parsed_chapter_data['chapter_number'],
                    title=parsed_chapter_data['title'],
                    content=parsed_chapter_data['content'],
                    summary=parsed_chapter_data['summary']
                )
                final_chapter_obj = Chapter(
                    id=new_chapter_id,
                    novel_id=parsed_chapter_data['novel_id'],
                    chapter_number=parsed_chapter_data['chapter_number'],
                    title=parsed_chapter_data['title'],
                    content=parsed_chapter_data['content'],
                    summary=parsed_chapter_data['summary'],
                    creation_date=parsed_chapter_data['creation_date']
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
    print("--- Testing ChapterChroniclerAgent (Live LLM Call with Refined Parsing) ---")
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        if "dummykey" in os.getenv("OPENAI_API_KEY",""):
             print("ERROR: Test cannot reliably proceed with a known dummy key pattern. Please set a real API key.")
             exit(1)

    test_sql_db_name = "test_live_chapter_agent_refined_v2.db"
    if os.path.exists(test_sql_db_name):
        os.remove(test_sql_db_name)

    db_mngr = DatabaseManager(db_name=test_sql_db_name)
    novel_id_for_test = -1

    try:
        novel_id_for_test = db_mngr.add_novel(
            user_theme="A clockmaker in a steampunk city discovers a device that can manipulate short intervals of time.",
            style_preferences="Steampunk, mystery, fast-paced, with detailed descriptions of clockwork mechanisms."
        )
        print(f"Created Novel ID for testing: {novel_id_for_test}")

        sample_brief = f"""
Novel Theme: A clockmaker in a steampunk city discovers a device that can manipulate short intervals of time.
Style: Steampunk, mystery, fast-paced, with detailed descriptions of clockwork mechanisms.
Overall Outline: Alistair, a reclusive clockmaker, finds a strange chronometer. He learns it can 'loop' a few seconds. A shadowy guild of 'Timekeepers' hunts him, believing such devices disrupt the true flow of time. He must master the device to protect himself and uncover why it was created.
Worldview: The city of Cogsworth is run by intricate clockwork systems, from public transport to information networks. Time is a revered, almost sacred concept, managed by the elite Timekeepers Guild.
Main Plot Arc: Discovery -> Experimentation & Minor Abuse -> First Encounter with Timekeepers -> Understanding the Stakes -> Using device for a heist/escape -> Confrontation with Guild Leader.
Previous Events: This is Chapter 1.
Focus Characters for this Chapter:
Character: Alistair Finch - Role: Protagonist. Description: Brilliant but socially awkward clockmaker, mid-30s, prefers machines to people. Fascinated by temporal mechanics.
--- RELEVANT LORE AND CONTEXT (from Knowledge Base) ---
The Timekeepers Guild values precision above all. They view temporal anomalies as a disease.
Chronometers are usually powered by miniature cavorite springs, but this one seems different.
--- END LORE AND CONTEXT ---
"""
        chapter_plot_summary = "Alistair discovers an odd, pulsing chronometer in a box of antique clock parts. Intrigued, he takes it to his workbench. While examining it, he accidentally activates it and experiences a brief, disorienting loop of the last few seconds: a dropped tool clattering to the floor three times in quick succession before he realizes what happened."
        novel_style = "Steampunk, detailed mechanical descriptions, slightly tense, discovery-focused."
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
            print(f"Title: {generated_chapter['title']}")
            print(f"Content (first 300 chars): {generated_chapter['content'][:300]}...")
            print(f"Summary: {generated_chapter['summary']}")

            assert generated_chapter['id'] != 0
            assert len(generated_chapter['title']) > 0 and generated_chapter['title'] != f"Chapter {target_chapter_number} (Untitled)"
            assert len(generated_chapter['content']) > 100 and generated_chapter['content'] != "Content not generated."
            assert len(generated_chapter['summary']) > 10 and generated_chapter['summary'] != "Summary not generated."

            db_chapter = db_mngr.get_chapter_by_id(generated_chapter['id'])
            assert db_chapter is not None
            if db_chapter:
                assert db_chapter['title'] == generated_chapter['title']
            print("\nChapter successfully generated, saved, and minimally verified in DB.")
        else:
            print("\nChapter generation and saving FAILED.")
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

    print("\n--- ChapterChroniclerAgent (Live LLM Call with Refined Parsing) Test Finished ---")
