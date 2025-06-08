import os
from dotenv import load_dotenv

from src.llm_abstraction.llm_client import LLMClient
from src.persistence.database_manager import DatabaseManager
# Not importing LoreKeeperAgent or KnowledgeBaseManager for now

class PolishRefinementAgent:
    def __init__(self, db_name: str = "novel_mvp.db"):
        try:
            self.llm_client = LLMClient()
        except ValueError as e:
            print(f"PolishRefinementAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise
        except Exception as e:
            print(f"PolishRefinementAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise
        self.db_manager = DatabaseManager(db_name=db_name)

    def _construct_prompt(self, original_chapter_content: str, novel_style: str, polish_mode: str, polish_intensity: str) -> str:
        intensity_instructions = {
            "light": "Make only essential and subtle changes, focusing on clarity and minor improvements. Preserve the original author's voice as much as possible.",
            "medium": "Moderately enhance and rephrase where beneficial for flow, impact, and consistency. Improve descriptions and dialogue while respecting the original narrative structure.",
            "deep": "Perform a comprehensive refinement, significantly improving prose, dialogue, and descriptions. This may involve more substantial rephrasing and restructuring of sentences and paragraphs to achieve a higher literary quality, while strictly preserving the core plot, character actions, and motivations found in the original text."
        }

        mode_instructions = {
            "enhance_descriptions": "Focus particularly on enriching descriptive passages, making settings more vivid and sensory details more impactful.",
            "optimize_dialogue": "Refine dialogue to be more crisp, natural, and character-revealing. Ensure pacing and subtext are effective.",
            "unify_style": f"Adjust the chapter's style to consistently embody the specified novel style: '{novel_style}'. Pay attention to tone, vocabulary, and sentence structure.",
            "grammar_correction": "Primarily correct grammatical errors, punctuation, and awkward phrasing. This is a technical polish.",
            "overall_literary_quality": "Holistically improve the chapter's literary merit, including prose fluency, pacing, emotional impact, and narrative engagement. Apply your best judgment as a literary editor."
        }

        prompt = f"""You are a文笔精湛的文学润色师 (accomplished literary polisher). Your task is to refine the following chapter content.
Novel Style: {novel_style}
Polish Mode: {polish_mode}
Polish Intensity: {polish_intensity}

Instructions:
1.  Adhere to the specified Novel Style throughout your revisions.
2.  Focus your polishing efforts based on the Polish Mode: {mode_instructions.get(polish_mode, "Apply general literary improvements.")}
3.  Apply changes according to the Polish Intensity: {intensity_instructions.get(polish_intensity, "Apply moderate enhancements.")}
4.  IMPORTANT: Ensure the polished text maintains the original plot, events, character actions, and motivations absolutely. The goal is to enhance the writing, not to change the story.
5.  Return *only* the polished chapter text. Do not include any preambles, apologies, or post-text commentary.

Original Chapter Content:
--- BEGIN ORIGINAL CONTENT ---
{original_chapter_content}
--- END ORIGINAL CONTENT ---

Polished Chapter Content:
"""
        return prompt

    def polish_chapter(self, original_chapter_content: str, novel_id: int, novel_style: str, polish_mode: str, polish_intensity: str) -> str:
        # novel_id is available for future enhancements (e.g., fetching specific character voice, worldview details)
        # For now, novel_style is passed directly and used.

        prompt = self._construct_prompt(original_chapter_content, novel_style, polish_mode, polish_intensity)

        # Estimate tokens for original content to help set max_tokens for LLM response
        # A simple heuristic: response might be similar length to original, plus some overhead for prompt.
        # This needs refinement based on typical LLM behavior.
        # For now, let's assume polished content is roughly same length as original.
        # A more robust approach would be to use a tokenizer.
        estimated_input_tokens = len(original_chapter_content.split()) # Rough word count
        max_tokens_for_response = int(estimated_input_tokens * 1.5) + 500 # Allow for some expansion and prompt overhead
        if max_tokens_for_response < 1000: # Ensure a minimum
            max_tokens_for_response = 1000
        if max_tokens_for_response > 4000: # Cap at a reasonable max for typical models if not using context window optimized ones
             max_tokens_for_response = 4000 # Adjust based on model, e.g. GPT-4 can handle more.

        print(f"PolishRefinementAgent: Sending prompt for polishing (mode: {polish_mode}, intensity: {polish_intensity}) to LLM.")
        print(f"Estimated input tokens (words): {estimated_input_tokens}, Max tokens for response: {max_tokens_for_response}")
        try:
            llm_response_text = self.llm_client.generate_text(
                prompt=prompt,
                model_name="gpt-4o-2024-08-06", # Or your preferred model for polishing
                temperature=0.5, # Lower temperature for more focused, less creative changes
                max_tokens=max_tokens_for_response
            )
            print(f"PolishRefinementAgent: Received response from LLM.")
        except Exception as e:
            print(f"PolishRefinementAgent: Error during LLM call - {e}")
            return original_chapter_content # Return original on error

        if not llm_response_text or llm_response_text.strip() == "":
            print(f"PolishRefinementAgent: LLM returned an empty response. Returning original content.")
            return original_chapter_content

        return llm_response_text.strip()

if __name__ == "__main__":
    load_dotenv()
    print("--- Testing PolishRefinementAgent ---")

    if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
        print("WARNING: A valid OpenAI API key is required for this test to properly interact with the LLM.")
        if "dummykey" in os.getenv("OPENAI_API_KEY",""):
             print("ERROR: Test cannot reliably proceed with a known dummy key pattern. Please set a real API key.")
             # exit(1) # Commenting out exit to allow testing structure without live calls if key is missing

    # Sample data for testing
    sample_novel_id = 1 # Dummy ID for now
    sample_novel_style = "Hard-boiled detective noir, with a touch of cynical humor and fast-paced dialogue. Descriptions should be gritty and evocative of a rain-slicked 1940s city."
    sample_chapter_content = """
The dame walked into my office, all legs and trouble. Rain was beatin' a sad rhythm on the window.
"I need your help, Mr. Diamond," she said, her voice like cheap whiskey.
My head was still poundin' from last night's altercation with a bottle of bourbon and a bad idea.
"What kind of trouble are you in, dollface?" I asked, trying to sound tougher than I felt.
She looked around, nervous like. "It's my husband. He's gone missing."
I sighed. Another missing husband. The city was full of 'em.
"Alright, I'll take the case," I said. "But it'll cost ya."
Her eyes, the color of a stormy sea, met mine. "I can pay."
I believed her. The kind of trouble she was in usually came with a fat wallet.
"""

    modes_to_test = ["enhance_descriptions", "optimize_dialogue", "unify_style", "grammar_correction", "overall_literary_quality"]
    intensities_to_test = ["light", "medium", "deep"]

    agent = PolishRefinementAgent(db_name="test_polish_agent.db") # Use a test DB if needed, though not heavily used yet

    for mode in modes_to_test:
        for intensity in intensities_to_test:
            print(f"\n--- Testing Polish Mode: '{mode}', Intensity: '{intensity}' ---")
            print("Original Content:")
            print(sample_chapter_content)

            # Check for API key before making a call
            if not os.getenv("OPENAI_API_KEY") or "dummy" in os.getenv("OPENAI_API_KEY", "").lower():
                print("\nSKIPPING LLM CALL: API Key not valid or not found. Cannot perform live polish test.")
                print("This test run will only verify class structure and prompt construction logic.")
                # Construct prompt to test that part
                test_prompt = agent._construct_prompt(sample_chapter_content, sample_novel_style, mode, intensity)
                print("\nConstructed Prompt (for verification):")
                print(test_prompt[:1000] + "...") # Print first 1000 chars of prompt
                continue # Skip to next iteration

            try:
                polished_content = agent.polish_chapter(
                    original_chapter_content=sample_chapter_content,
                    novel_id=sample_novel_id,
                    novel_style=sample_novel_style,
                    polish_mode=mode,
                    polish_intensity=intensity
                )
                print("\nPolished Content:")
                print(polished_content)

                # Basic assertion: polished content should not be empty if LLM call was made
                if polished_content.strip() == "" or polished_content == sample_chapter_content:
                    print("WARNING: Polished content is empty or same as original. Check LLM response or prompt.")

            except Exception as e:
                print(f"Error during polish_chapter call for mode '{mode}', intensity '{intensity}': {e}")

    # Clean up dummy db if created and not needed
    if os.path.exists("test_polish_agent.db"):
        # os.remove("test_polish_agent.db") # Uncomment if you want to clean up
        pass

    print("\n--- PolishRefinementAgent Test Finished ---")
