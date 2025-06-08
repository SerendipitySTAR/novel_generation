import os
import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dotenv import load_dotenv

from src.llm_abstraction.llm_client import LLMClient
from src.persistence.database_manager import DatabaseManager
from src.core.models import Chapter
from src.utils.dynamic_token_config import get_dynamic_max_tokens, log_token_usage

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

    def _construct_prompt(self, chapter_brief: str, current_chapter_plot_summary: str, style_preferences: str, words_per_chapter: int = 1000) -> str:
        # Prompt refined to be more explicit about using the plot summary and brief,
        # and the RAG context if demarcated in the brief.
        prompt = f"""You are a novelist writing a chapter. Adhere to the style: {style_preferences}.

Chapter Brief (context, characters, lore):
--- BEGIN CHAPTER BRIEF ---
{chapter_brief}
--- END CHAPTER BRIEF ---

Specific Plot for THIS Chapter: {current_chapter_plot_summary}

Your primary goal for this chapter's content is to flesh out the 'Specific Plot for THIS Chapter'. This is the driving force of the chapter.
Use the 'Chapter Brief' for essential background, character states, and relevant lore to ensure consistency.
If the 'Chapter Brief' includes a 'RELEVANT LORE AND CONTEXT (from Knowledge Base)' section, subtly integrate these facts/lore snippets where they naturally fit within the narrative flow. Do not list them or directly refer to them as 'lore' or 'from the knowledge base'. The integration should feel organic and enhance the story.
Weave all these elements together to write a compelling narrative for this chapter.

IMPORTANT: Your response must follow this EXACT format. Do not include any other text or explanations:

Title:
[Write a compelling title for this chapter here]

Content:
[Write the full chapter text here. Aim for approximately {words_per_chapter} words.
- Show, Don't Tell: Focus on vivid descriptions of settings, character actions, and emotions.
- Dialogue: Incorporate meaningful dialogue that reveals character personality, motivations, and advances the plot.
- Character Consistency: Ensure character behaviors, decisions, and speech patterns are consistent with their detailed profiles and motivations as described in the 'Chapter Brief'.
- Utilize Context: If the 'Chapter Brief' includes a 'RELEVANT LORE AND CONTEXT (from Knowledge Base)' section, subtly weave these details into the narrative where appropriate to enhance world-building and consistency. Avoid large blocks of exposition (info-dumping). Ensure all provided RAG context is used effectively and subtly.
- Pacing and Flow: Maintain a good narrative pace suitable for the chapter's events and tone.]

Self-Correction Checklist (Before Finalizing):
- Is dialogue impactful and character-revealing?
- Are descriptions vivid and immersive?
- Is all provided RAG context used effectively and subtly?
- Does the chapter primarily advance the 'Specific Plot for THIS Chapter'?

Summary:
[Write a concise 2-3 sentence summary of the key plot advancements, character developments, and critical outcomes that occurred within this chapter only]

Remember: Start with "Title:" on the first line, then "Content:" on a new line, then "Summary:" on a new line. Do not add any other text before or after these sections."""
        return prompt

    def _parse_llm_response(self, llm_response: str, novel_id: int, chapter_number: int) -> Optional[Dict[str, Any]]:
        parsing_log_prefix = f"ChapterChroniclerAgent (Ch {chapter_number}):"
        try:
            title = f"Chapter {chapter_number} (Untitled)"
            content = "Content not generated."
            summary = "Summary not generated."
            parse_path = "Initial" # To log parsing attempts

            # Clean the response first
            cleaned_response = llm_response.strip()

            # More robust regex patterns
            # Title: captures everything after "Title:" until next section or newline
            title_regex = r"^\s*Title:\s*(.*?)(?=\n\s*Content:|\n\s*Summary:|$)"
            # Content: captures everything after "Content:" until "Summary:" or end
            content_regex = r"^\s*Content:\s*(.*?)(?=\n\s*Summary:|$)"
            # Summary: captures everything after "Summary:" until end
            summary_regex = r"^\s*Summary:\s*(.*?)$"

            title_match = re.search(title_regex, cleaned_response, re.MULTILINE | re.IGNORECASE | re.DOTALL)
            content_match = re.search(content_regex, cleaned_response, re.MULTILINE | re.IGNORECASE | re.DOTALL)
            summary_match = re.search(summary_regex, cleaned_response, re.MULTILINE | re.IGNORECASE | re.DOTALL)

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

            # Enhanced Fallback Logic
            if content == "Content not generated." and cleaned_response.strip():
                parse_path += "->EnhancedFallback"
                print(f"{parsing_log_prefix} Info - Content not found via primary parsing. Attempting enhanced fallback.")

                # Try alternative parsing strategies
                lines = cleaned_response.split('\n')
                title_found = False
                content_found = False
                summary_found = False
                current_section = None
                temp_content_lines = []
                temp_title = ""
                temp_summary = ""

                for line in lines:
                    line_stripped = line.strip()

                    # Check for section markers
                    if re.match(r'^\s*title\s*:', line_stripped, re.IGNORECASE):
                        current_section = 'title'
                        title_found = True
                        # Extract title from same line if present
                        title_content = re.sub(r'^\s*title\s*:\s*', '', line_stripped, flags=re.IGNORECASE)
                        if title_content:
                            temp_title = title_content
                        continue
                    elif re.match(r'^\s*content\s*:', line_stripped, re.IGNORECASE):
                        current_section = 'content'
                        content_found = True
                        # Extract content from same line if present
                        content_line = re.sub(r'^\s*content\s*:\s*', '', line_stripped, flags=re.IGNORECASE)
                        if content_line:
                            temp_content_lines.append(content_line)
                        continue
                    elif re.match(r'^\s*summary\s*:', line_stripped, re.IGNORECASE):
                        current_section = 'summary'
                        summary_found = True
                        # Extract summary from same line if present
                        summary_content = re.sub(r'^\s*summary\s*:\s*', '', line_stripped, flags=re.IGNORECASE)
                        if summary_content:
                            temp_summary = summary_content
                        continue

                    # Add content to current section
                    if current_section == 'title' and line_stripped:
                        temp_title = line_stripped
                    elif current_section == 'content' and line_stripped:
                        temp_content_lines.append(line)
                    elif current_section == 'summary' and line_stripped:
                        if temp_summary:
                            temp_summary += " " + line_stripped
                        else:
                            temp_summary = line_stripped

                # Apply fallback results
                if temp_title and not title_match:
                    title = temp_title
                    parse_path += "->FB_TitleFound"

                if temp_content_lines:
                    content = '\n'.join(temp_content_lines).strip()
                    parse_path += "->FB_ContentFound"

                if temp_summary and not summary_match:
                    summary = temp_summary
                    parse_path += "->FB_SummaryFound"

                # Last resort: use entire response as content if nothing else worked
                if content == "Content not generated." and cleaned_response:
                    # Remove any section headers and use the rest
                    clean_content = re.sub(r'^\s*(title|content|summary)\s*:\s*', '', cleaned_response, flags=re.IGNORECASE | re.MULTILINE)
                    if clean_content.strip():
                        content = clean_content.strip()
                        parse_path += "->FB_LastResort"
                        print(f"{parsing_log_prefix} Info - Using entire response as content (last resort).")

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
                                  current_chapter_plot_summary: str, style_preferences: str,
                                  words_per_chapter: int = 1000) -> Optional[Chapter]:
        prompt = self._construct_prompt(chapter_brief, current_chapter_plot_summary, style_preferences, words_per_chapter)

        # Calculate dynamic max_tokens based on content and requirements
        context = {
            "brief": chapter_brief,
            "words_per_chapter": words_per_chapter
        }
        max_tokens = get_dynamic_max_tokens("chapter_chronicler", context)
        log_token_usage("chapter_chronicler", max_tokens, context)

        print(f"ChapterChroniclerAgent: Sending prompt for Chapter {chapter_number} to LLM.")
        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt, model_name="gpt-4o-2024-08-06", temperature=0.7, max_tokens=max_tokens
            )
            print(f"ChapterChroniclerAgent: Received response from LLM for Chapter {chapter_number}.")
        except Exception as e:
            print(f"ChapterChroniclerAgent: Error during LLM call for Chapter {chapter_number} - {e}")
            return None

        if not llm_response_text:
            print(f"ChapterChroniclerAgent: LLM returned an empty response for Chapter {chapter_number}.")
            return None

        # Debug: Log the raw response for troubleshooting
        print(f"ChapterChroniclerAgent: Raw LLM response length: {len(llm_response_text)} characters")
        print(f"ChapterChroniclerAgent: Response preview (first 200 chars): {llm_response_text[:200]}...")

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
