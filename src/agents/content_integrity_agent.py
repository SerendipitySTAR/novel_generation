import re
from typing import Dict, Any, List, Tuple
from src.llm_abstraction.llm_client import LLMClient
import os # For test block
from dotenv import load_dotenv # For test block
import openai # For test block

class ContentIntegrityAgent:
    """
    Agent responsible for reviewing content quality based on multiple dimensions.
    """

    # Define the 7 dimensions for scoring
    SCORING_DIMENSIONS = [
        ("Coherence", "Logical flow and connection of ideas within the text."),
        ("Consistency", "Uniformity of tone, style, character traits, and plot details."),
        ("Pacing", "The speed at which the story unfolds and events occur."),
        ("Engagement", "The ability of the content to capture and hold the reader's interest."),
        ("Originality", "Freshness of ideas, plot, characters, and world-building elements."),
        ("Detail", "Richness of description and sensory information that brings the story to life."),
        ("Grammar", "Correctness of grammar, spelling, punctuation, and syntax.")
    ]

    def __init__(self, llm_client: LLMClient = None):
        try:
            self.llm_client = llm_client if llm_client else LLMClient()
        except ValueError as e: # Raised by LLMClient if API key is missing
            print(f"ContentIntegrityAgent Error: LLMClient initialization failed. {e}")
            raise
        except Exception as e:
            print(f"ContentIntegrityAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise

    def _construct_review_prompt(self, content: str, content_type: str = "chapter") -> str:
        dimension_prompts = "\n".join([
            f"- {name} (Definition: {desc}): [Score 1-10]"
            for name, desc in self.SCORING_DIMENSIONS
        ])

        prompt = f"""
You are a meticulous editor and content quality analyst. Review the following {content_type} based on the 7 dimensions listed below.
For each dimension, provide a score from 1 (Very Poor) to 10 (Excellent).
After scoring, provide a brief overall justification for your scores (3-5 sentences).

Content to Review (approx. {len(content.split())} words):
---
{content[:2000]}... (Content may be truncated for brevity in this prompt if very long)
---

Scoring Dimensions:
{dimension_prompts}

Overall Score: [Calculate as the average of the 7 dimension scores, rounded to one decimal place]
Justification: [Your brief overall justification here.]

Please format your review EXACTLY as shown above, with each item on a new line.
Begin your review now:
"""
        return prompt

    def _parse_review_response(self, response_text: str) -> Dict[str, Any]:
        review: Dict[str, Any] = {
            "scores": {},
            "overall_score": None,
            "justification": "Could not parse justification."
        }
        parsed_scores_count = 0
        total_score_sum = 0

        for dim_name, _ in self.SCORING_DIMENSIONS:
            try:
                # Regex to find "Dimension Name: [Score]" (removed problematic .*?)
                match = re.search(rf"{re.escape(dim_name)}\s*:\s*([0-9]+(?:\.[0-9]+)?)", response_text, re.IGNORECASE)
                if match:
                    score = float(match.group(1))
                    # Clamp score between 1 and 10
                    score = max(1.0, min(10.0, score))
                    review["scores"][dim_name] = score
                    total_score_sum += score
                    parsed_scores_count += 1
                else:
                    review["scores"][dim_name] = None
                    print(f"ContentIntegrityAgent: Warning - Could not parse score for dimension: {dim_name}")
            except Exception as e:
                review["scores"][dim_name] = None
                print(f"ContentIntegrityAgent: Error parsing score for {dim_name} - {e}")

        try:
            overall_match = re.search(r"Overall Score:\s*([0-9]+(?:\.[0-9]+)?)", response_text, re.IGNORECASE)
            if overall_match:
                review["overall_score"] = float(overall_match.group(1))
            elif parsed_scores_count > 0: # Calculate if not found but individual scores exist
                review["overall_score"] = round(total_score_sum / parsed_scores_count, 1)
                print(f"ContentIntegrityAgent: Calculated overall score as {review['overall_score']} from {parsed_scores_count} dimensions.")
        except Exception as e:
            print(f"ContentIntegrityAgent: Error parsing or calculating overall score - {e}")


        justification_match = re.search(r"Justification:\s*(.*)", response_text, re.IGNORECASE | re.DOTALL)
        if justification_match:
            justification_text = justification_match.group(1).strip()
            review["justification"] = justification_text

        if parsed_scores_count < len(self.SCORING_DIMENSIONS):
            print(f"ContentIntegrityAgent: Warning - Parsed {parsed_scores_count}/{len(self.SCORING_DIMENSIONS)} dimension scores.")
        if review["justification"] == "Could not parse justification." and response_text.strip():
             print(f"ContentIntegrityAgent: Warning - Justification might be missing or unparsed. Raw response (first 300 chars): {response_text[:300]}")

        return review

    def review_content(self, content: str, content_type: str = "chapter") -> Dict[str, Any]:
        if not content or not content.strip():
            print(f"ContentIntegrityAgent: Error - Content for {content_type} cannot be empty.")
            return {
                "scores": {dim_name: 0 for dim_name, _ in self.SCORING_DIMENSIONS},
                "overall_score": 0.0,
                "justification": f"{content_type.capitalize()} content was empty.",
                "error": "Empty content"
            }

        prompt = self._construct_review_prompt(content, content_type)
        # print(f"ContentIntegrityAgent: Sending {content_type} review prompt to LLM (prompt length: {len(prompt)}).")

        try:
            # Consider max_tokens carefully based on content length + prompt length + expected response size
            # Response is ~100-200 tokens. Prompt can be large if content is large.
            # LLMClient default max_tokens might be too small if content is very long.
            # For now, let's assume LLMClient handles token limits or we manage content truncation.
            response_text = self.llm_client.generate_text(prompt, max_tokens=3000) # Increased max_tokens for response
            # print(f"ContentIntegrityAgent: Received review response from LLM for {content_type}.")
        except openai.APIError as e: # Catch API errors specifically
            print(f"ContentIntegrityAgent: OpenAI API Error during LLM call for {content_type} review - {e}")
            return {
                "scores": {dim_name: 0 for dim_name, _ in self.SCORING_DIMENSIONS},
                "overall_score": 0.0,
                "justification": f"LLM API call failed: {e}",
                "error": f"LLM API Error: {e}"
            }
        except Exception as e:
            print(f"ContentIntegrityAgent: General Error during LLM call for {content_type} review - {e}")
            return {
                "scores": {dim_name: 0 for dim_name, _ in self.SCORING_DIMENSIONS},
                "overall_score": 0.0,
                "justification": f"LLM call failed: {e}",
                "error": f"LLM Call Error: {e}"
            }

        parsed_review = self._parse_review_response(response_text)

        # Ensure overall_score is calculated if not parsed directly
        if parsed_review.get("overall_score") is None:
            total_score_sum = sum(s for s in parsed_review.get("scores", {}).values() if s is not None)
            num_valid_scores = sum(1 for s in parsed_review.get("scores", {}).values() if s is not None)
            if num_valid_scores > 0:
                parsed_review["overall_score"] = round(total_score_sum / num_valid_scores, 1)
            else:
                parsed_review["overall_score"] = 0.0

        return parsed_review

if __name__ == '__main__':
    load_dotenv()
    api_key_present = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here")

    print(f"--- ContentIntegrityAgent Test ---")
    print(f"OpenAI API Key Present: {api_key_present}")

    if not api_key_present:
        print("WARNING: OPENAI_API_KEY not found or is a placeholder. LLM calls will fail.")
        # Mock LLMClient if no API key to avoid crashing
        class MockLLMClient:
            def generate_text(self, prompt: str, max_tokens: int):
                print("MockLLMClient: generate_text called. Returning dummy response.")
                # Simulate a plausible response structure
                dummy_response = ""
                for dim_name, _ in ContentIntegrityAgent.SCORING_DIMENSIONS:
                    dummy_response += f"{dim_name}: {os.urandom(1)[0] % 10 + 1}\n" # Random score 1-10
                dummy_response += "Overall Score: 7.5\n"
                dummy_response += "Justification: This is a mocked justification for testing purposes.\n"
                return dummy_response
        agent = ContentIntegrityAgent(llm_client=MockLLMClient())
    else:
        try:
            agent = ContentIntegrityAgent()
        except Exception as e:
            print(f"Error initializing ContentIntegrityAgent for live test: {e}")
            agent = None


    if agent:
        sample_chapter_content = (
            "The old house stood on a hill overlooking the town. It had been empty for years, "
            "and people said it was haunted. One night, a group of teenagers decided to explore it. "
            "They climbed the creaky stairs, their flashlights casting long, dancing shadows. "
            "A sudden noise made them jump. Was it the wind, or something else? The air grew cold. "
            "Suddenly, a door slammed shut behind them, plunging them into darkness. Panic set in. "
            "They fumbled for their phones, their hands shaking too much to dial. A whisper echoed from the hallway."
            "This chapter is very short and lacks originality but has some atmosphere."
        )

        print(f"\nReviewing sample chapter content (live call: {api_key_present})...")
        review_result = agent.review_content(sample_chapter_content, content_type="Sample Chapter")

        print("\n--- Review Result ---")
        if review_result:
            print(f"  Overall Score: {review_result.get('overall_score')}")
            print(f"  Justification: {review_result.get('justification')}")
            print("  Individual Scores:")
            for dim, score in review_result.get("scores", {}).items():
                print(f"    {dim}: {score}")
            if review_result.get('error'):
                print(f"  Error: {review_result.get('error')}")
        else:
            print("  No review result obtained.")

        print("\nReviewing empty content...")
        empty_review = agent.review_content("", content_type="Empty Chapter")
        print("\n--- Empty Content Review Result ---")
        if empty_review:
            print(f"  Overall Score: {empty_review.get('overall_score')}")
            print(f"  Justification: {empty_review.get('justification')}")
            if empty_review.get('error'):
                print(f"  Error: {empty_review.get('error')}")

    else:
        print("Could not run tests as ContentIntegrityAgent failed to initialize.")

    print(f"\n--- ContentIntegrityAgent Test Finished ---")
