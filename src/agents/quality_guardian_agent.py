import re
from typing import Dict, Any
from src.llm_abstraction.llm_client import LLMClient # Ensure this path is correct
import os # For test block
from dotenv import load_dotenv # For test block
import openai # For test block, to catch openai.APIError

class QualityGuardianAgent:
    def __init__(self):
        try:
            self.llm_client = LLMClient()
        except ValueError as e: # Raised by LLMClient if API key is missing
            print(f"QualityGuardianAgent Error: LLMClient initialization failed. {e}")
            print("Please ensure OPENAI_API_KEY is set in your environment or .env file.")
            raise
        except Exception as e:
            print(f"QualityGuardianAgent Error: An unexpected error occurred during LLMClient initialization: {e}")
            raise

    def _construct_prompt_for_outline_review(self, outline_text: str) -> str:
        prompt = f"""You are a literary critic and editor. Review the following novel outline based on the criteria below.
Provide a score from 1 (Poor) to 10 (Excellent) for each criterion.
Also, provide a brief overall justification for your scores (2-3 sentences).

Outline to Review:
---
{outline_text}
---

Please format your review EXACTLY as follows, with each item on a new line:
Clarity: [1-10]
Originality: [1-10]
Conflict Potential: [1-10]
Overall Score: [1-10]
Justification: [Your brief justification here.]

Begin your review now:
"""
        return prompt

    def _parse_review_response(self, response_text: str) -> Dict[str, Any]:
        review: Dict[str, Any] = {
            "clarity": None,
            "originality": None,
            "conflict_potential": None,
            "overall_score": None,
            "justification": "Could not parse justification."
        }
        try:
            # Updated regex to capture 1-10 (or single digit)
            clarity_match = re.search(r"Clarity:\s*(\d0?|[\d])", response_text, re.IGNORECASE)
            if clarity_match: review["clarity"] = int(clarity_match.group(1))

            originality_match = re.search(r"Originality:\s*(\d0?|[\d])", response_text, re.IGNORECASE)
            if originality_match: review["originality"] = int(originality_match.group(1))

            conflict_match = re.search(r"Conflict Potential:\s*(\d0?|[\d])", response_text, re.IGNORECASE)
            if conflict_match: review["conflict_potential"] = int(conflict_match.group(1))

            overall_match = re.search(r"Overall Score:\s*(\d0?|[\d])", response_text, re.IGNORECASE)
            if overall_match: review["overall_score"] = int(overall_match.group(1))

            # Use re.DOTALL for justification as it might be multi-line or have newlines before it.
            # Look for "Justification:" potentially at the start of a line (re.MULTILINE if needed, but DOTALL often sufficient)
            justification_match = re.search(r"Justification:\s*(.*)", response_text, re.IGNORECASE | re.DOTALL)
            if justification_match:
                justification_text = justification_match.group(1).strip()
                review["justification"] = justification_text[:500] if len(justification_text) > 500 else justification_text

            parsed_scores = sum(1 for k in ["clarity", "originality", "conflict_potential", "overall_score"] if review[k] is not None)
            if parsed_scores < 4: # If not all 4 scores were parsed
                print(f"QualityGuardianAgent: Warning - Not all scores were parsed. Found {parsed_scores}/4. Raw response (first 300 chars): {response_text[:300]}")
            elif review["justification"] == "Could not parse justification." and response_text.strip(): # If scores parsed but justification didn't
                 print(f"QualityGuardianAgent: Warning - Scores parsed, but justification might be missing or unparsed. Raw response (first 300 chars): {response_text[:300]}")


        except Exception as e:
            print(f"QualityGuardianAgent: Error parsing review response - {e}. Raw response: {response_text[:300]}")

        return review

    def review_outline(self, outline_text: str) -> Dict[str, Any]:
        if not outline_text or not outline_text.strip():
            print("QualityGuardianAgent: Error - Outline text cannot be empty.")
            return {
                "clarity": 0, "originality": 0, "conflict_potential": 0,
                "overall_score": 0, "justification": "Outline text was empty."
            }

        prompt = self._construct_prompt_for_outline_review(outline_text)

        print("QualityGuardianAgent: Sending outline review prompt to LLM.")
        try:
            # max_tokens for review: outline can be long, review itself is short.
            # LLMClient default is 1500. Prompt includes the outline.
            # A 300-word outline is ~400 tokens. Review text is <100 tokens.
            # 500-700 should be safe for the response part.
            response_text = self.llm_client.generate_text(prompt, max_tokens=32768)
            print("QualityGuardianAgent: Received review response from LLM.")
        except Exception as e:
            print(f"QualityGuardianAgent: Error during LLM call for outline review - {e}")
            return {
                "clarity": 0, "originality": 0, "conflict_potential": 0,
                "overall_score": 0, "justification": f"LLM call failed: {e}"
            }

        return self._parse_review_response(response_text)

if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or "dummykey" in api_key.lower() or api_key == "your_openai_api_key_here":
        print("----------------------------------------------------------------------")
        print("WARNING: A real OPENAI_API_KEY is required to test QualityGuardianAgent thoroughly.")
        print("Attempting to run with potentially limited functionality or errors.")
        print("If API call fails, default/error values will be shown for review_result.")
        print("----------------------------------------------------------------------")

    agent = QualityGuardianAgent() # Will fail here if API key is not set at all due to LLMClient

    sample_outline_valid = (
        "In a city powered by sentient crystals, a young artisan discovers she can "
        "communicate with a dying 'mother crystal' that holds the city's life force. "
        "A corporation exploiting the crystals for energy is causing the decay. "
        "She must convince the city council and find a way to heal the mother crystal "
        "before the city (and its crystal-based inhabitants) fade away, while evading "
        "corporate agents who want to silence her and accelerate the crystal extraction."
    )
    sample_outline_empty = ""
    sample_outline_short = "A wizard finds a cat."

    outlines_to_test = [
        {"name": "Valid Outline", "text": sample_outline_valid},
        {"name": "Empty Outline", "text": sample_outline_empty},
        {"name": "Short Outline", "text": sample_outline_short}
    ]

    for test_case in outlines_to_test:
        print(f"\n--- Reviewing Test Case: {test_case['name']} ---")
        print(f"Outline Text:\n'''{test_case['text']}'''\n")

        try:
            review_result = agent.review_outline(test_case['text'])
        except openai.APIError as e: # Catch API errors if LLMClient re-raises them
            print(f"OpenAI API Error during review: {e}")
            review_result = {"error": str(e)} # Simulate an error result
        except Exception as e:
            print(f"Unexpected error during review: {e}")
            review_result = {"error": str(e)}

        print("\nReview Result:")
        if review_result:
            for key, value in review_result.items():
                print(f"  {key}: {value}")
        else:
            print("No review result was obtained (agent returned None or empty).")
        print("--------------------")

    print("\n--- QualityGuardianAgent Test Finished ---")
