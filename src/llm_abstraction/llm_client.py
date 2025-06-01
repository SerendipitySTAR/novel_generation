import openai
import os
from dotenv import load_dotenv

class LLMClient:
    def __init__(self):
        load_dotenv()  # Load environment variables from .env file if present
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not found.")
        openai.api_key = self.api_key

    def generate_text(self, prompt: str, model_name: str = "gpt-3.5-turbo", temperature: float = 0.7, max_tokens: int = 1500) -> str:
        """
        Generates text using the specified OpenAI model.
        """
        try:
            response = openai.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("API response content is None.")
            return content.strip()
        except openai.APIError as e:
            print(f"OpenAI API Error: {e}")
            # Potentially re-raise or handle more gracefully
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise

if __name__ == "__main__":
    # This is an example of how to use the LLMClient
    # For this to run, you need to have an OPENAI_API_KEY set in your environment
    # or in a .env file in the root of the project.

    # Create a .env file in the root of your project with:
    # OPENAI_API_KEY="your_actual_openai_api_key"

    print("Attempting to initialize LLMClient...")
    try:
        client = LLMClient()
        print("LLMClient initialized successfully.")
        sample_prompt = "Write a short story about a robot who discovers music."
        print(f"Sending prompt to OpenAI: '{sample_prompt}'")
        response_text = client.generate_text(sample_prompt, max_tokens=150)
        print("\nGenerated Text:")
        print(response_text)
    except ValueError as ve:
        print(f"Configuration Error: {ve}")
        print("Please ensure your OPENAI_API_KEY is correctly set in a .env file or as an environment variable.")
    except openai.APIError as apie:
        print(f"OpenAI API Error during example execution: {apie}")
        print("This might be due to network issues, an invalid API key, or problems with the OpenAI service.")
    except Exception as e:
        print(f"An error occurred during example execution: {e}")
