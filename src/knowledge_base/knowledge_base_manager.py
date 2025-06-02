import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List, Optional, Dict # Added Optional and Dict

class KnowledgeBaseManager:
    def __init__(self, collection_name_prefix: str = "novel_kb", db_directory: str = "./chroma_db"):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not found. Please set it in your .env file or environment.")

        self.embeddings_model = OpenAIEmbeddings(openai_api_key=self.api_key)
        self.db_directory = db_directory
        self.collection_name_prefix = collection_name_prefix

        # Ensure the Chroma DB directory exists
        if not os.path.exists(self.db_directory):
            os.makedirs(self.db_directory)
            print(f"Chroma DB directory created at: {self.db_directory}")

    def _get_collection_name(self, novel_id: int) -> str:
        return f"{self.collection_name_prefix}_{novel_id}"

    def _get_vector_store(self, novel_id: int) -> Chroma:
        collection_name = self._get_collection_name(novel_id)
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings_model,
            persist_directory=self.db_directory
        )
        return vector_store

    def add_texts(self, novel_id: int, texts: List[str], metadatas: Optional[List[Dict[str, any]]] = None) -> None:
        if not texts:
            print("No texts provided to add.")
            return

        vector_store = self._get_vector_store(novel_id)
        vector_store.add_texts(texts=texts, metadatas=metadatas)
        vector_store.persist() # Ensure changes are saved to disk
        print(f"Added {len(texts)} texts to Chroma collection for novel_id {novel_id}. Persisted.")

    def retrieve_relevant_chunks(self, novel_id: int, query: str, k: int = 5) -> List[str]:
        vector_store = self._get_vector_store(novel_id)
        if not query:
            print("Empty query provided.")
            return []

        try:
            # Check if collection exists / has documents before querying
            # This is a bit of a workaround as Chroma can raise errors on empty/new collections for some ops
            # A more robust check might involve listing collections or trying a count_documents if available
            _ = vector_store.get() # Tries to get collection details, can indicate if empty or not found
        except Exception as e: # Broad exception, specific Chroma errors could be caught
            print(f"Could not access collection for novel_id {novel_id} (it might be empty or new): {e}")
            # Attempt to query anyway, or return empty if certain it's an issue
            # For an empty collection, similarity_search might also error or return empty list
            # Depending on Chroma's behavior, this try-except might need adjustment
            # If the collection is truly empty and similarity_search is called, it might raise an error
            # or return an empty list. If it raises an error, this try-except might not be needed here.
            # If it returns empty list, then it's fine.

        print(f"Retrieving {k} relevant chunks for novel_id {novel_id} with query: '{query[:50]}...'")
        try:
            docs = vector_store.similarity_search(query, k=k)
        except Exception as e:
            # This can happen if the collection is empty. Chroma sometimes raises errors.
            print(f"Error during similarity search for novel_id {novel_id} (collection might be empty): {e}")
            return []

        retrieved_contents = [doc.page_content for doc in docs]
        print(f"Retrieved {len(retrieved_contents)} chunks.")
        return retrieved_contents

    def delete_collection(self, novel_id: int) -> None:
        """Deletes an entire collection for a given novel_id."""
        collection_name = self._get_collection_name(novel_id)
        try:
            vector_store = self._get_vector_store(novel_id) # To connect to the existing collection
            vector_store.delete_collection() # Langchain Chroma wrapper provides this
            print(f"Successfully deleted Chroma collection: {collection_name}")
        except Exception as e: # Chroma can raise errors if collection doesn't exist
            print(f"Error deleting collection {collection_name} (it might not exist): {e}")
            # Depending on Chroma's specific error (e.g. a 'Not Found' error),
            # you might choose to ignore this error or handle it differently.


if __name__ == "__main__":
    print("--- Testing KnowledgeBaseManager ---")
    # Ensure OPENAI_API_KEY is set in your environment or a .env file
    # For testing, create a .env file in the root of the project:
    # OPENAI_API_KEY="your_actual_openai_api_key_or_a_test_key_if_mocking_embeddings"

    # Check if a .env file exists and create a dummy one if not, for CI/CD or test environments
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for testing KnowledgeBaseManager...")
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEY=\"sk-dummykeyforlocaltestingonly\"\n") # Dummy key

    load_dotenv() # Load it for this test script
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not found after attempting to load .env. Embedding calls will fail.")
        print("Please ensure an OPENAI_API_KEY is available in your environment or .env file.")
        # Exiting if no key, as embeddings are crucial for this manager
        exit(1)
    else:
        print(f"OPENAI_API_KEY found (length: {len(os.getenv('OPENAI_API_KEY'))}).")


    test_novel_id = 9999  # Using a distinct ID for testing
    test_db_dir = "./test_chroma_db"

    # Clean up previous test directory if it exists
    import shutil
    if os.path.exists(test_db_dir):
        print(f"Removing existing test Chroma DB directory: {test_db_dir}")
        shutil.rmtree(test_db_dir)

    kb_manager = KnowledgeBaseManager(collection_name_prefix="test_novel_kb", db_directory=test_db_dir)
    print(f"KnowledgeBaseManager initialized with DB directory: {kb_manager.db_directory}")

    assert os.path.exists(test_db_dir), "Chroma DB directory was not created by KnowledgeBaseManager"

    # 1. Add texts
    sample_texts = [
        "The dragon Ardax has green scales and breathes fire.",
        "Sir Gideon is a knight known for his bravery and loyalty.",
        "The Crystal of Eldoria is hidden in the Shadowfen.",
        "Shadowfen is a swamp full of dangerous creatures and illusions.",
        "Ardax guards the Crystal of Eldoria."
    ]
    sample_metadatas = [
        {"source": "character_bio", "character_name": "Ardax"},
        {"source": "character_bio", "character_name": "Sir Gideon"},
        {"source": "lore_item", "item_name": "Crystal of Eldoria"},
        {"source": "location_info", "location_name": "Shadowfen"},
        {"source": "plot_point", "entities": ["Ardax", "Crystal of Eldoria"]}
    ]

    print(f"\nAdding {len(sample_texts)} texts to novel ID {test_novel_id}...")
    try:
        kb_manager.add_texts(test_novel_id, sample_texts, metadatas=sample_metadatas)
    except Exception as e:
        print(f"ERROR during add_texts: {e}")
        print("This might be due to API key issues or network problems if not using a dummy key.")
        # Clean up before exiting on error
        if os.path.exists(test_db_dir):
            shutil.rmtree(test_db_dir)
        raise

    # Verify files are created in the persist_directory
    # Chroma creates a sqlite3 file and potentially other files/folders (like .parquet files in newer versions)
    chroma_files_present = any(fname.endswith('.sqlite3') for fname in os.listdir(test_db_dir))
    print(f"Chroma files found in {test_db_dir}: {os.listdir(test_db_dir)}")
    assert chroma_files_present, "Chroma database files not found in the persist directory."

    # 2. Retrieve relevant chunks
    query1 = "Tell me about the dragon."
    print(f"\nRetrieving chunks for query: '{query1}'")
    try:
        relevant_chunks1 = kb_manager.retrieve_relevant_chunks(test_novel_id, query1, k=2)
        print("Relevant chunks for query 1:")
        for chunk in relevant_chunks1:
            print(f"  - {chunk}")
        assert len(relevant_chunks1) > 0, "No chunks retrieved for query 1"
        assert any("Ardax" in chunk for chunk in relevant_chunks1), "Expected Ardax info not found"
    except Exception as e:
        print(f"ERROR during retrieve_relevant_chunks for query 1: {e}")
        if os.path.exists(test_db_dir):
            shutil.rmtree(test_db_dir)
        raise


    query2 = "What is hidden in the swamp?"
    print(f"\nRetrieving chunks for query: '{query2}'")
    try:
        relevant_chunks2 = kb_manager.retrieve_relevant_chunks(test_novel_id, query2, k=3)
        print("Relevant chunks for query 2:")
        for chunk in relevant_chunks2:
            print(f"  - {chunk}")
        assert len(relevant_chunks2) > 0, "No chunks retrieved for query 2"
        assert any("Crystal of Eldoria" in chunk for chunk in relevant_chunks2), "Expected Crystal info not found"
        assert any("Shadowfen" in chunk for chunk in relevant_chunks2), "Expected Shadowfen info not found"
    except Exception as e:
        print(f"ERROR during retrieve_relevant_chunks for query 2: {e}")
        if os.path.exists(test_db_dir):
            shutil.rmtree(test_db_dir)
        raise

    # 3. Test deleting the collection
    print(f"\nDeleting collection for novel ID {test_novel_id}...")
    kb_manager.delete_collection(test_novel_id)

    # Try to retrieve after deletion (should ideally find nothing or error gracefully)
    print(f"\nAttempting to retrieve chunks after deletion for novel ID {test_novel_id} (should be empty or error)...")
    chunks_after_delete = kb_manager.retrieve_relevant_chunks(test_novel_id, query1, k=2)
    assert len(chunks_after_delete) == 0, \
        f"Chunks were retrieved after collection deletion, which is unexpected. Found: {chunks_after_delete}"
    print("Retrieval after deletion returned 0 chunks as expected.")


    # Clean up test directory
    print(f"\nCleaning up test Chroma DB directory: {test_db_dir}")
    if os.path.exists(test_db_dir):
        shutil.rmtree(test_db_dir)

    # Clean up dummy .env if it was created by this script
    if os.path.exists(".env") and "dummykeyforlocaltestingonly" in open(".env").read():
        print("Removing dummy .env file...")
        os.remove(".env")

    print("--- KnowledgeBaseManager Test Finished ---")
