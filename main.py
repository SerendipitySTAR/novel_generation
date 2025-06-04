#!/usr/bin/env python3
import os
import json
import argparse
from dotenv import load_dotenv

from src.orchestration.workflow_manager import WorkflowManager, NovelWorkflowState # Assuming NovelWorkflowState is importable
from src.persistence.database_manager import DatabaseManager # For direct DB access in main for final output
from src.utils.token_calculator import NovelGenerationCostEstimator

def setup_dummy_api_key():
    """
    Checks for OPENAI_API_KEY. If not found, and no .env file with it exists,
    creates a .env file with a dummy key to allow components to initialize.
    """
    load_dotenv() # Try loading existing .env first
    if not os.getenv("OPENAI_API_KEY"):
        env_file_exists = os.path.exists(".env")
        key_in_env_file = False
        if env_file_exists:
            with open(".env", "r") as f:
                if "OPENAI_API_KEY" in f.read():
                    key_in_env_file = True

        if not env_file_exists or not key_in_env_file:
            print("INFO: OPENAI_API_KEY not found in environment or .env file.")
            print("INFO: Creating a .env file with a DUMMY OpenAI API key (sk-dummyclikey...) for initialization purposes.")
            print("INFO: This dummy key will NOT work for actual OpenAI API calls.")
            print("INFO: Please set a valid OPENAI_API_KEY in your .env file or environment for full functionality.")
            with open(".env", "w") as f:
                f.write("OPENAI_API_KEY=\"sk-dummyclikeyformainexecution\"\n")

    load_dotenv() # Load again to pick up newly created .env if any
    # Final check, though LLMClients will do their own validation too
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: Failed to set up or load OPENAI_API_KEY. Application might not run correctly.")
    else:
        print(f"INFO: OPENAI_API_KEY is set (Value starts with: {os.getenv('OPENAI_API_KEY')[:10]}...).")
        if "dummyclikeyformainexecution" in os.getenv("OPENAI_API_KEY"): # Match the exact dummy key
            print("INFO: Using a DUMMY API key. LLM-dependent features will use mocks or fail if not mocked.")

def parse_arguments() -> dict:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Novel Generation CLI")
    parser.add_argument("--theme", type=str, required=True, help="The theme for your novel.")
    parser.add_argument("--style", type=str, default="general fiction", help="Style preferences (e.g., 'fantasy, dark humor'). Defaults to 'general fiction'.")
    parser.add_argument("--chapters", type=int, default=3, help="Number of chapters to generate (default: 3, min: 1, max: 15).")
    parser.add_argument("--words-per-chapter", type=int, default=1000, help="Target words per chapter (default: 1000, min: 300, max: 3000).")
    parser.add_argument("--skip-cost-estimate", action="store_true", help="Skip the token cost estimation and proceed directly to generation.")
    parser.add_argument("--auto-mode", action="store_true", help="Enable automatic mode: skip user interactions and use default selections.")
    args = parser.parse_args()

    # Validate chapters argument
    if args.chapters < 1:
        print("Error: Number of chapters must be at least 1.")
        exit(1)
    elif args.chapters > 15:
        print("Error: Number of chapters cannot exceed 15 for quality and performance reasons.")
        exit(1)

    # Validate words per chapter argument
    if args.words_per_chapter < 300:
        print("Error: Words per chapter must be at least 300.")
        exit(1)
    elif args.words_per_chapter > 3000:
        print("Error: Words per chapter cannot exceed 3000 for quality and performance reasons.")
        exit(1)

    return {
        "theme": args.theme,
        "style_preferences": args.style,
        "chapters": args.chapters,
        "words_per_chapter": args.words_per_chapter,
        "skip_cost_estimate": args.skip_cost_estimate,
        "auto_mode": args.auto_mode
    }

def main_cli():
    """Main CLI function using argparse."""
    setup_dummy_api_key()

    print("\n--- Novel Generation Setup ---")
    user_input_data = parse_arguments()
    print(f"Theme: {user_input_data['theme']}")
    print(f"Style: {user_input_data['style_preferences']}")
    print(f"Chapters: {user_input_data['chapters']}")
    print(f"Words per chapter: {user_input_data['words_per_chapter']}")

    # Token cost estimation
    if not user_input_data['skip_cost_estimate']:
        print("\n--- Token Cost Estimation ---")
        cost_estimator = NovelGenerationCostEstimator()
        cost_breakdown = cost_estimator.estimate_full_workflow_cost(user_input_data)

        print(f"Estimated total tokens: {cost_breakdown['total_tokens']:,}")
        print(f"  - Input tokens: {cost_breakdown['total_input_tokens']:,}")
        print(f"  - Output tokens: {cost_breakdown['total_output_tokens']:,}")
        print(f"Estimated cost: ${cost_breakdown['estimated_cost_usd']:.2f} USD")

        print("\nDetailed breakdown by operation:")
        for estimate in cost_breakdown['estimates']:
            print(f"  {estimate.operation_name}:")
            print(f"    Tokens: {estimate.total_tokens:,} (${estimate.estimated_cost_usd:.2f})")

        # Ask for user confirmation
        print(f"\nThis will generate a {user_input_data['chapters']}-chapter novel with approximately {user_input_data['words_per_chapter']} words per chapter.")
        print(f"Estimated token usage: {cost_breakdown['total_tokens']:,} tokens")
        print(f"Estimated cost: ${cost_breakdown['estimated_cost_usd']:.2f} USD")

        while True:
            user_choice = input("\nDo you want to proceed? (y/n): ").lower().strip()
            if user_choice in ['y', 'yes']:
                break
            elif user_choice in ['n', 'no']:
                print("Novel generation cancelled by user.")
                return
            else:
                print("Please enter 'y' for yes or 'n' for no.")

    print("\nInitializing WorkflowManager...")
    # Assuming default DB name is handled by WorkflowManager and DatabaseManager
    # Ensure any test DBs are cleaned up if you run this after tests, or use a unique DB for main.
    workflow_db_name = "main_novel_generation.db"
    workflow_chroma_dir = "./main_novel_chroma_db" # For LoreKeeper via WorkflowManager

    # Clean up previous main run DBs if they exist, for a fresh run each time
    import shutil
    if os.path.exists(workflow_db_name):
        print(f"INFO: Removing previous database: {workflow_db_name}")
        os.remove(workflow_db_name)
    if os.path.exists(workflow_chroma_dir):
        print(f"INFO: Removing previous Chroma database: {workflow_chroma_dir}")
        shutil.rmtree(workflow_chroma_dir)


    manager = WorkflowManager(db_name=workflow_db_name) # Pass db_name to constructor
    print(f"INFO: WorkflowManager will use DB: {workflow_db_name} and Chroma dir: {workflow_chroma_dir} (via LoreKeeperAgent)")


    print("\nStarting novel generation workflow...")
    try:
        final_state: NovelWorkflowState = manager.run_workflow(user_input_data)
        print("\n--- Novel Generation Workflow Complete ---")
    except Exception as e:
        print(f"\n--- Novel Generation Workflow Failed ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Display Output
    print("\n--- Generated Novel ---")
    if final_state.get('error_message'):
        print(f"Workflow failed: {final_state['error_message']}")
        print("\nWorkflow History:")
        for entry in final_state.get('history', []):
            print(f"  - {entry}")
    else:
        novel_id = final_state.get('novel_id') # Changed from narrative_id to novel_id

        # Access the db_manager instance from the WorkflowManager if it's made available
        # Or instantiate a new one for display purposes.
        # For this example, we'll instantiate a new one.
        display_db_manager = DatabaseManager(db_name=workflow_db_name)

        novel_record = display_db_manager.get_novel_by_id(novel_id) if novel_id else None

        print(f"Novel ID: {novel_id}")
        print(f"Theme: {final_state.get('user_input', {}).get('theme')}")
        print(f"Style: {final_state.get('user_input', {}).get('style_preferences')}")

        if novel_record:
            outline_data = display_db_manager.get_outline_by_id(novel_record['active_outline_id']) if novel_record['active_outline_id'] else None
            worldview_data = display_db_manager.get_worldview_by_id(novel_record['active_worldview_id']) if novel_record['active_worldview_id'] else None
            plot_data = display_db_manager.get_plot_by_id(novel_record['active_plot_id']) if novel_record['active_plot_id'] else None

            # Characters from DB will now be List[DetailedCharacterProfile]
            characters_details_from_db = display_db_manager.get_characters_for_novel(novel_id) if novel_id else []

            if outline_data: print(f"\nOutline: {outline_data['overview_text']}")
            if worldview_data: print(f"\nWorldview: {worldview_data['description_text']}")

            # Plot display: plot_data['plot_summary'] is JSON string of List[PlotChapterDetail]
            if plot_data and plot_data['plot_summary']:
                print("\nPlot Details (from DB JSON):")
                try:
                    detailed_plot_list = json.loads(plot_data['plot_summary'])
                    for i, ch_detail in enumerate(detailed_plot_list):
                        print(f"  Chapter {ch_detail.get('chapter_number', i+1)} Title: {ch_detail.get('title', 'N/A')}")
                        print(f"    Events: {str(ch_detail.get('key_events_and_plot_progression', 'N/A'))[:100]}...")
                except json.JSONDecodeError:
                    print(f"  Could not decode plot summary JSON. Raw: {plot_data['plot_summary'][:100]}...")
            elif plot_data:
                 print(f"\nPlot Summary (Raw): {plot_data['plot_summary']}")


            if characters_details_from_db:
                print("\nCharacters (from DB, deserialized):")
                for char_profile in characters_details_from_db:
                    print(f"  - Name: {char_profile.get('name', 'N/A')}")
                    print(f"    Role: {char_profile.get('role_in_story', 'N/A')}")
                    print(f"    Appearance: {char_profile.get('appearance_summary', 'N/A')}")
                    print(f"    Background Snippet: {char_profile.get('background_story', 'N/A')[:100]}...")
            else:
                print("\nCharacters: No characters were generated or found in DB.")
        else:
            print("\nNovel core data could not be fully retrieved from DB (novel_record not found).")
            # Display from state if available
            print(f"  Narrative Outline Text (from state): {final_state.get('narrative_outline_text')}")
            selected_wv_detail = final_state.get('selected_worldview_detail')
            if selected_wv_detail: print(f"  Selected Worldview Concept (from state): {selected_wv_detail.get('core_concept')}")

            characters_from_state = final_state.get('characters') # This is List[DetailedCharacterProfile]
            if characters_from_state:
                print("\nCharacters (from final workflow state):")
                for char_profile in characters_from_state:
                    print(f"  - Name: {char_profile.get('name', 'N/A')}")
                    print(f"    Role: {char_profile.get('role_in_story', 'N/A')}")
                    print(f"    Appearance: {char_profile.get('appearance_summary', 'N/A')}")


        outline_review_data = final_state.get('outline_review')
        if outline_review_data:
            print("\n--- Outline Review (from final state) ---")
            if isinstance(outline_review_data, dict): # Check if it's a dict before iterating
                for key, value in outline_review_data.items():
                    print(f"  {key.replace('_', ' ').capitalize()}: {value}")
            else:
                print(f"  Review data is not in the expected format: {outline_review_data}")
            print("------------------------------------")

        generated_chapters = final_state.get('generated_chapters', [])
        if generated_chapters:
            print("\n--- Chapters ---")
            for chapter in generated_chapters:
                print(f"\nChapter {chapter['chapter_number']}: {chapter['title']}")
                print(f"Summary: {chapter['summary']}")
                print(f"Content:\n{chapter['content']}")
        else:
            print("\nNo chapters were generated by the workflow.")
            print("This might be due to the workflow stopping before chapter generation (e.g., at LoreKeeper initialization if API key is dummy),")
            print("or if the chapter generation loop was configured for 0 chapters.")

        print("\nFull Workflow History:")
        for entry in final_state.get('history', []):
            print(f"  - {entry}")

        # Suggestion for user:
        print(f"\nINFO: All persistent data for this novel (ID: {novel_id}) is in '{workflow_db_name}'.")
        print(f"INFO: Vector embeddings (if generated) are in '{workflow_chroma_dir}'.")

if __name__ == "__main__":
    main_cli()
