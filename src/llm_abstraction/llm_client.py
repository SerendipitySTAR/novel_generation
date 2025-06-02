import openai
import os
from dotenv import load_dotenv

class LLMClient:
    def __init__(self):
        load_dotenv()  # Load environment variables from .env file if present
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not found. Please ensure it is set.")
        # Note: openai.api_key = self.api_key is for older versions.
        # For openai > 1.0, the key is passed to the client instance.
        # However, the current create call doesn't use an explicit client instance,
        # relying on the global openai.api_key or environment variable.
        # For clarity and future-proofing, it's better to instantiate a client if possible,
        # but the existing code structure for openai.chat.completions.create() might implicitly use it.
        # For now, let's ensure the global is set if that's what the library version expects.
        openai.api_key = self.api_key


    def generate_text(self, prompt: str, model_name: str = "gpt-3.5-turbo", temperature: float = 0.7, max_tokens: int = 1500) -> str:
        """
        Generates text using the specified OpenAI model.
        """
        try:
            response = openai.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for creative writing."}, # Updated system prompt
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                print(f"LLMClient: Error - API response content is None. Full response: {response}")
                raise ValueError("API response content is None.")
            return content.strip()
        except openai.BadRequestError as e:
            error_message = f"OpenAI API BadRequestError: {e}"
            print(error_message)
            print(f"LLMClient: Details for BadRequestError - Model: {model_name}, Max Tokens: {max_tokens}, Prompt Length: {len(prompt)} chars")
            prompt_snippet = prompt[:200] + "..." if len(prompt) > 200 else prompt
            print(f"LLMClient: Prompt Snippet for BadRequestError: {prompt_snippet}")
            # print(f"LLMClient: Error Body for BadRequestError: {e.body}") # Uncomment if e.body is confirmed useful
            raise
        except openai.APIError as e:
            error_message = f"OpenAI APIError (Non-BadRequest): {e}"
            print(error_message)
            print(f"LLMClient: Details for APIError - Model: {model_name}")
            raise
        except Exception as e:
            error_message = f"LLMClient: An unexpected error occurred: {e}"
            print(error_message)
            print(f"LLMClient: Details for Unexpected Error - Model: {model_name}, Prompt Length: {len(prompt)} chars")
            prompt_snippet = prompt[:200] + "..." if len(prompt) > 200 else prompt
            print(f"LLMClient: Prompt Snippet for Unexpected Error: {prompt_snippet}")
            raise

if __name__ == "__main__":
    print("Attempting to initialize LLMClient...")
    try:
        client = LLMClient()
        print("LLMClient initialized successfully.")
        sample_prompt = "Write a short story about a robot who discovers music, but make it less than 50 words."
        print(f"Sending prompt to OpenAI: '{sample_prompt}'")

        # Test with a model that might be more restricted or cause different errors if not configured
        # Forcing a smaller max_tokens to test potential BadRequestError if prompt is too long for it (unlikely here)
        response_text = client.generate_text(sample_prompt, model_name="gpt-3.5-turbo", max_tokens=60)
        print("\nGenerated Text (gpt-3.5-turbo):")
        print(response_text)

        # Example of a prompt that could be too long if max_tokens is very small
        # long_prompt_test = "Once upon a time " * 1000 # Approx 5000 chars, ~1250 tokens
        # print(f"\nTesting with potentially long prompt (length: {len(long_prompt_test)} chars)...")
        # try:
        #    response_long = client.generate_text(long_prompt_test, max_tokens=100) # Small max_tokens
        #    print(response_long)
        # except openai.BadRequestError as bre:
        #    print(f"Successfully caught expected BadRequestError for long prompt: {bre}")


    except ValueError as ve:
        print(f"Configuration Error: {ve}")
        print("Please ensure your OPENAI_API_KEY is correctly set in a .env file or as an environment variable.")
    except openai.APIError as apie: # Catching APIError specifically if it's not caught by generate_text's more specific handlers
        print(f"OpenAI API Error during example execution: {apie}")
        print("This might be due to network issues, an invalid API key, or problems with the OpenAI service.")
    except Exception as e:
        print(f"An error occurred during example execution: {e}")
