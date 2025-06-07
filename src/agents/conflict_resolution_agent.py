# src/agents/conflict_resolution_agent.py
from typing import Dict, Any, List, Optional
import logging
import re # Added for parsing LLM suggestions

logger = logging.getLogger(__name__)

class ConflictResolutionAgent:
    def __init__(self, llm_client = None, db_name: Optional[str] = None):
        self.llm_client = llm_client
        self.db_name = db_name
        logger.info(f"ConflictResolutionAgent initialized. DB name: {self.db_name}")

    def attempt_auto_resolve(self, novel_id: int, chapter_text: str, conflicts: List[Dict[str, Any]], novel_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        modified_text = chapter_text
        text_was_changed = False
        logger.info(f"Attempting LLM-based auto-resolution for {len(conflicts)} conflicts in novel {novel_id}, chapter (original text length: {len(chapter_text)}).")

        if not self.llm_client:
            logger.error("LLMClient not available in ConflictResolutionAgent. Cannot attempt auto-resolve.")
            return chapter_text # Return original text

        if not conflicts:
            logger.info("No conflicts provided to auto-resolve.") # Changed from previous log to be more specific
            return chapter_text

        for conflict in conflicts:
            original_excerpt = conflict.get("excerpt")

            if not original_excerpt or not isinstance(original_excerpt, str) or not original_excerpt.strip():
                logger.warning(f"Skipping conflict due to missing or invalid excerpt: {conflict.get('description')}")
                continue

            # Find the excerpt in the *current* state of modified_text
            excerpt_start_index = modified_text.find(original_excerpt)
            if excerpt_start_index == -1:
                logger.warning(f"Could not find original excerpt \"{original_excerpt}\" in (potentially modified) chapter text for conflict: {conflict.get('description')}. Skipping this conflict's resolution.")
                continue

            # Define a context window around the excerpt for the LLM
            window_chars = 150  # Characters on each side
            context_start_for_llm = max(0, excerpt_start_index - window_chars)
            context_end_for_llm = min(len(modified_text), excerpt_start_index + len(original_excerpt) + window_chars)
            text_window_for_llm = modified_text[context_start_for_llm:context_end_for_llm]

            prompt = (
                f"A chapter text contains a conflict that needs to be resolved.\n"
                f"Novel Context (Theme/Style): {novel_context.get('theme', 'N/A') if novel_context else 'N/A'} / {novel_context.get('style_preferences', 'N/A') if novel_context else 'N/A'}\n"
                f"Conflict Type: {conflict.get('type', 'N/A')}\n"
                f"Conflict Description: {conflict.get('description', 'N/A')}\n"
                f"Knowledge Base Reference (if any): {conflict.get('kb_reference', 'N/A')}\n\n"
                f"The problematic excerpt is: \"{original_excerpt}\"\n\n"
                f"This excerpt appears in the following broader context from the chapter:\n"
                f"--- CONTEXT BEGIN ---\n{text_window_for_llm}\n--- CONTEXT END ---\n\n"
                f"Your task: Rewrite ONLY the problematic excerpt (i.e., \"{original_excerpt}\") "
                f"to resolve the described conflict. Ensure the revision fits naturally into the surrounding context, "
                f"maintains the narrative style, and is grammatically correct. "
                f"Return ONLY the revised version of the excerpt. "
                f"If you believe the original excerpt doesn't need to be changed to resolve this specific conflict, "
                f"or if a minimal targeted change to only the excerpt cannot resolve it, "
                f"return the original excerpt verbatim: \"{original_excerpt}\""
            )

            try:
                estimated_max_tokens = int(len(original_excerpt.split()) * 2.5) + 60 # Adjusted buffer
                revised_excerpt_llm = self.llm_client.generate_text(
                    prompt,
                    max_tokens=max(50, estimated_max_tokens), # Ensure at least 50 tokens
                    temperature=0.6
                )
                revised_excerpt_llm = revised_excerpt_llm.strip().replace('"', '') # Basic cleaning

                if revised_excerpt_llm and revised_excerpt_llm != original_excerpt and len(revised_excerpt_llm) > 0:
                    # Replace the original_excerpt at its specific location
                    before_excerpt = modified_text[:excerpt_start_index]
                    after_excerpt = modified_text[excerpt_start_index + len(original_excerpt):]
                    modified_text = before_excerpt + revised_excerpt_llm + after_excerpt

                    logger.info(f"Conflict '{conflict.get('description')}' auto-resolved. Original: '{original_excerpt}' -> Revised: '{revised_excerpt_llm}'")
                    text_was_changed = True
                elif revised_excerpt_llm == original_excerpt:
                    logger.info(f"LLM suggested no change for conflict '{conflict.get('description')}' with excerpt '{original_excerpt}'.")
                else:
                    logger.warning(f"LLM returned an empty or unsuitable response for excerpt '{original_excerpt}': '{revised_excerpt_llm}'")
            except Exception as e:
                logger.error(f"Error during LLM call or processing for conflict '{conflict.get('description')}': {e}")
                # Decide if we should continue with other conflicts or stop
                continue # For now, try next conflict

        if text_was_changed:
            logger.info("ConflictResolutionAgent.attempt_auto_resolve: Text was modified.")
            return modified_text
        else:
            logger.info("ConflictResolutionAgent.attempt_auto_resolve: No changes made to the text after processing all conflicts.")
            return chapter_text # Return original if no changes from input text

    def suggest_revisions_for_human_review(self, novel_id: int, chapter_text: str, conflicts: List[Dict[str, Any]], novel_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        logger.info(f"Preparing LLM-based suggestions for {len(conflicts)} conflicts in novel {novel_id}.")

        if not self.llm_client:
            logger.error("LLMClient not available. Cannot generate LLM-based suggestions.")
            augmented_conflicts_error = []
            for conflict in conflicts:
                conflict_copy = conflict.copy()
                conflict_copy["llm_suggestions"] = ["LLM suggestions unavailable due to missing client."]
                augmented_conflicts_error.append(conflict_copy)
            return augmented_conflicts_error

        if not conflicts:
            return []

        augmented_conflicts: List[Dict[str, Any]] = []
        for conflict in conflicts:
            conflict_copy = conflict.copy()
            logger.info(f"Generating LLM suggestions for conflict ID {conflict.get('conflict_id')}: {conflict.get('description')}")

            original_excerpt = conflict.get("excerpt")
            if not original_excerpt or not isinstance(original_excerpt, str) or not original_excerpt.strip():
                logger.warning(f"Conflict ID {conflict.get('conflict_id')} has no valid excerpt. Skipping LLM suggestion.")
                conflict_copy["llm_suggestions"] = ["No excerpt provided to base suggestions on."]
                augmented_conflicts.append(conflict_copy)
                continue

            start_index = chapter_text.find(original_excerpt)
            if start_index == -1:
                logger.warning(f"Original excerpt for conflict ID {conflict.get('conflict_id')} not found in chapter text. Cannot generate targeted suggestions. Excerpt: {original_excerpt[:100]}...")
                conflict_copy["llm_suggestions"] = ["Original excerpt not found in chapter text for targeted suggestion generation."]
                augmented_conflicts.append(conflict_copy)
                continue

            window_chars = 300 # Characters on each side for context
            context_start = max(0, start_index - window_chars)
            context_end = min(len(chapter_text), start_index + len(original_excerpt) + window_chars)
            context_window_text = chapter_text[context_start:context_end]

            prompt = (
                f"A novel chapter has the following conflict:\n"
                f"Conflict Type: {conflict.get('type', 'N/A')}\n"
                f"Conflict Severity: {conflict.get('severity', 'N/A')}\n"
                f"Conflict Description: {conflict.get('description', 'N/A')}\n"
                f"Problematic Excerpt from chapter: \"{original_excerpt}\"\n"
                f"Knowledge Base Reference (if any): {conflict.get('kb_reference', 'N/A')}\n\n"
                f"Wider context from the chapter around the excerpt:\n"
                f"--- BEGIN CONTEXT WINDOW ---\n{context_window_text}\n--- END CONTEXT WINDOW ---\n\n"
                f"Your task is to provide one or two distinct, concise suggestions for how to rewrite ONLY the problematic excerpt (\"{original_excerpt}\") to resolve the conflict.\n"
                f"The suggestions should maintain the original style and tone of the chapter and fit naturally into the context.\n"
                f"Prefix each suggestion clearly, like \"Suggestion 1: [Rewritten excerpt]\" or \"Suggestion: [Rewritten excerpt]\".\n"
                f"If providing two suggestions, separate them with '---' (three hyphens).\n"
                f"If you believe no change to the excerpt is necessary or cannot formulate a good targeted suggestion for just the excerpt, respond with \"No specific rewrite suggestion for this excerpt.\"\n\n"
                f"Suggestions:"
            )

            try:
                max_tokens_for_suggestions = int(len(original_excerpt.split()) * 2.5 * 2) + 150 # Allow for two suggestions, some formatting, and buffer
                llm_suggestions_text = self.llm_client.generate_text(
                    prompt,
                    max_tokens=max(100, max_tokens_for_suggestions), # Ensure reasonable minimum
                    temperature=0.65
                )

                parsed_suggestions = []
                clean_llm_output = llm_suggestions_text.strip()

                if "no specific rewrite suggestion" in clean_llm_output.lower():
                    parsed_suggestions.append("LLM indicated no specific rewrite suggestion needed for the excerpt.")
                else:
                    # Split by "---" for multiple suggestions, then process each part
                    suggestion_parts = clean_llm_output.split("---")
                    for part in suggestion_parts:
                        part = part.strip()
                        if not part:
                            continue
                        # Remove "Suggestion X:" prefix if present
                        cleaned_suggestion = re.sub(r"Suggestion\s*\d*:\s*", "", part, flags=re.IGNORECASE).strip()
                        if cleaned_suggestion:
                            parsed_suggestions.append(cleaned_suggestion)

                    if not parsed_suggestions and clean_llm_output: # If splitting failed but there's text
                        parsed_suggestions.append(clean_llm_output) # Add raw cleaned output as one suggestion

                conflict_copy["llm_suggestions"] = parsed_suggestions if parsed_suggestions else ["LLM response did not yield parseable suggestions."]

            except Exception as e:
                logger.error(f"Error during LLM call for conflict ID {conflict.get('conflict_id')} suggestions: {e}")
                conflict_copy["llm_suggestions"] = [f"Error generating suggestions from LLM: {e}"]

            # Remove old stub fields
            conflict_copy.pop("suggested_action_placeholder", None)
            conflict_copy.pop("status_for_review", None)

            augmented_conflicts.append(conflict_copy)

        return augmented_conflicts
