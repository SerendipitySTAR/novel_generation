import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings # Adjusted import for newer langchain
from langchain_community.vectorstores import Chroma # Adjusted import for newer langchain
# If using older LangChain, these might be:
# from langchain.embeddings.openai import OpenAIEmbeddings
# from langchain.vectorstores import Chroma

def run_rag_poc():
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not found.")
        print("Please ensure it's set in a .env file or as an environment variable.")
        return

    print("OPENAI_API_KEY found. Initializing OpenAIEmbeddings...")
    try:
        embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)
    except Exception as e:
        print(f"Error initializing OpenAIEmbeddings: {e}")
        return

    print("OpenAIEmbeddings initialized.")

    # 1. Sample Documents
    sample_documents = [
        "The quick brown fox jumps over the lazy dog.",
        "Paris is the capital of France.",
        "The Eiffel Tower is a famous landmark in Paris.",
        "Artificial intelligence is a rapidly growing field.",
        "LangChain is a framework for developing applications powered by language models."
    ]
    print(f"Loaded {len(sample_documents)} sample documents.")

    # 2. Vector Store Setup (ChromaDB in-memory for POC)
    # LangChain's Chroma wrapper can simplify document adding and embedding.
    # It will handle creating embeddings and adding them to Chroma.
    print("Setting up ChromaDB in-memory vector store...")
    try:
        # The from_texts method handles embedding and adding documents.
        # It requires a collection name. If it doesn't exist, it's created.
        vector_store = Chroma.from_texts(
            texts=sample_documents,
            embedding=embeddings_model,
            collection_name="rag_poc_collection" # Specify a collection name
        )
        print("ChromaDB vector store created and documents embedded.")
    except Exception as e:
        print(f"Error setting up ChromaDB or embedding documents: {e}")
        return

    # 3. Querying
    sample_query = "What is the capital of France?"
    print(f"Performing similarity search for query: '{sample_query}'")

    try:
        retrieved_docs = vector_store.similarity_search(sample_query, k=2) # Get top 2 relevant docs

        print("\nRetrieved Documents:")
        if retrieved_docs:
            for i, doc in enumerate(retrieved_docs):
                print(f"Doc {i+1}: {doc.page_content}")
                # print(f"Metadata: {doc.metadata}") # If you add metadata
        else:
            print("No documents found.")

    except Exception as e:
        print(f"Error during similarity search: {e}")
        return

    # Example of adding more documents (optional)
    try:
        print("\nAdding more documents to the existing collection...")
        more_docs = ["ChromaDB is a vector database.", "The sky is blue on a clear day."]
        vector_store.add_texts(texts=more_docs)
        print(f"Added {len(more_docs)} new documents.")

        # Test query again
        another_query = "Tell me about ChromaDB"
        print(f"Performing similarity search for query: '{another_query}'")
        retrieved_docs_updated = vector_store.similarity_search(another_query, k=2)

        print("\nRetrieved Documents (after update):")
        if retrieved_docs_updated:
            for i, doc in enumerate(retrieved_docs_updated):
                print(f"Doc {i+1}: {doc.page_content}")
        else:
            print("No documents found for the new query.")

    except Exception as e:
        print(f"Error adding more documents or querying: {e}")


if __name__ == "__main__":
    print("--- Running Basic RAG Pipeline Proof-of-Concept ---")
    # This requires OPENAI_API_KEY to be set.
    # Create a .env file in the root of your project with:
    # OPENAI_API_KEY="your_actual_openai_api_key"
    run_rag_poc()
    print("\n--- RAG POC Finished ---")
