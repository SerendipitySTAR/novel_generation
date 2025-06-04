import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List, Optional, Dict, Any # Added Optional, Dict, and Any
import chromadb

# 尝试使用新的 langchain-huggingface 包，如果失败则回退到旧版本
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    print("Using new langchain-huggingface package")
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    print("Using legacy langchain-community package")

class KnowledgeBaseManager:
    def __init__(self, collection_name_prefix: str = "novel_kb", db_directory: str = "./chroma_db"):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not found. Please set it in your .env file or environment.")

        # Support for local embedding models
        self.use_local_embeddings = os.getenv("USE_LOCAL_EMBEDDINGS", "true").lower() == "true"
        self.local_embedding_model_path = os.getenv("LOCAL_EMBEDDING_MODEL_PATH",
                                                   "/media/sc/AI/self-llm/embed_model/sentence-transformers/all-MiniLM-L6-v2")

        if self.use_local_embeddings:
            try:
                print(f"KnowledgeBaseManager: Attempting to use local embedding model at {self.local_embedding_model_path}")
                self.embeddings_model = HuggingFaceEmbeddings(
                    model_name=self.local_embedding_model_path,
                    model_kwargs={'device': 'cpu'}  # You can change to 'cuda' if you have GPU
                )
                print("KnowledgeBaseManager: Successfully initialized local embeddings")
            except Exception as e:
                print(f"KnowledgeBaseManager: Failed to initialize local embeddings: {e}")
                print("KnowledgeBaseManager: Falling back to OpenAI embeddings")
                self.use_local_embeddings = False
                self.embeddings_model = OpenAIEmbeddings(openai_api_key=self.api_key)
        else:
            print("KnowledgeBaseManager: Using OpenAI embeddings")
            self.embeddings_model = OpenAIEmbeddings(openai_api_key=self.api_key)

        self.db_directory = db_directory
        self.collection_name_prefix = collection_name_prefix

        # 缓存向量存储实例以避免重复创建和减少内存使用
        self._vector_store_cache = {}

        # 初始化 ChromaDB 客户端
        self.chroma_client = chromadb.PersistentClient(path=self.db_directory)

        # Ensure the Chroma DB directory exists
        if not os.path.exists(self.db_directory):
            os.makedirs(self.db_directory)
            print(f"Chroma DB directory created at: {self.db_directory}")

    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            self.cleanup_resources()
        except:
            pass  # 忽略析构时的错误

    def cleanup_resources(self):
        """清理资源，释放向量存储缓存"""
        if hasattr(self, '_vector_store_cache'):
            self._vector_store_cache.clear()
            print("KnowledgeBaseManager: Cleaned up vector store cache")

    def _get_collection_name(self, novel_id: int) -> str:
        return f"{self.collection_name_prefix}_{novel_id}"

    def _get_vector_store(self, novel_id: int) -> Chroma:
        # 检查缓存中是否已有该向量存储
        if novel_id in self._vector_store_cache:
            return self._vector_store_cache[novel_id]

        collection_name = self._get_collection_name(novel_id)
        try:
            vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings_model,
                persist_directory=self.db_directory
            )
            # 缓存向量存储实例
            self._vector_store_cache[novel_id] = vector_store
            return vector_store
        except Exception as e:
            print(f"Error creating vector store for novel_id {novel_id}: {e}")
            # 尝试清理并重新创建
            try:
                self._cleanup_corrupted_collection(novel_id)
                vector_store = Chroma(
                    collection_name=collection_name,
                    embedding_function=self.embeddings_model,
                    persist_directory=self.db_directory
                )
                print(f"Successfully recreated vector store for novel_id {novel_id}")
                # 缓存重新创建的向量存储实例
                self._vector_store_cache[novel_id] = vector_store
                return vector_store
            except Exception as e2:
                print(f"Failed to recreate vector store for novel_id {novel_id}: {e2}")
                raise ValueError(f"Cannot create vector store for novel_id {novel_id}: {e2}")

    def _cleanup_corrupted_collection(self, novel_id: int) -> None:
        """清理损坏的集合"""
        collection_name = self._get_collection_name(novel_id)

        # 从缓存中移除该向量存储
        if novel_id in self._vector_store_cache:
            del self._vector_store_cache[novel_id]
            print(f"Removed novel_id {novel_id} from vector store cache")

        print(f"⚠️  检测到知识库集合损坏: {collection_name}")
        print(f"📁 数据库目录: {self.db_directory}")
        print(f"🔧 建议的修复步骤:")
        print(f"   1. 停止当前程序")
        print(f"   2. 备份重要数据（如果需要）")
        print(f"   3. 运行修复脚本: python fix_chromadb_issues.py")
        print(f"   4. 或手动删除损坏的集合目录")
        print(f"💡 如果问题持续，可以删除整个ChromaDB目录: {self.db_directory}")
        print(f"   但这会丢失所有知识库数据，请谨慎操作！")

        # 不再自动删除数据，让用户决定
        raise RuntimeError(f"知识库集合 {collection_name} 损坏，需要手动修复。请参考上述提示进行修复。")

    def add_texts(self, novel_id: int, texts: List[str], metadatas: Optional[List[Dict[str, any]]] = None) -> None:
        if not texts:
            print("No texts provided to add.")
            return

        try:
            vector_store = self._get_vector_store(novel_id)
            vector_store.add_texts(texts=texts, metadatas=metadatas)
            vector_store.persist() # Ensure changes are saved to disk
            print(f"Added {len(texts)} texts to Chroma collection for novel_id {novel_id}. Persisted.")
        except Exception as e:
            print(f"Error adding texts to collection for novel_id {novel_id}: {e}")
            # 如果是collections.topic错误，尝试重新创建
            if "collections.topic" in str(e):
                print(f"Detected ChromaDB schema issue for novel_id {novel_id}. Attempting to fix...")
                try:
                    self._cleanup_corrupted_collection(novel_id)
                    vector_store = self._get_vector_store(novel_id)
                    vector_store.add_texts(texts=texts, metadatas=metadatas)
                    vector_store.persist()
                    print(f"Successfully fixed ChromaDB schema and added {len(texts)} texts for novel_id {novel_id}")
                except Exception as e2:
                    print(f"Failed to fix ChromaDB schema and add texts for novel_id {novel_id}: {e2}")
                    raise
            else:
                raise

    def retrieve_relevant_chunks(self, novel_id: int, query: str, k: int = 5) -> List[str]:
        if not query:
            print("Empty query provided.")
            return []

        try:
            vector_store = self._get_vector_store(novel_id)
        except Exception as e:
            print(f"Failed to get vector store for novel_id {novel_id}: {e}")
            return []

        try:
            # Check if collection exists / has documents before querying
            collection_data = vector_store.get()
            if not collection_data.get('ids'):
                print(f"Collection for novel_id {novel_id} is empty.")
                return []
        except Exception as e:
            print(f"Could not access collection for novel_id {novel_id}: {e}")
            # 如果是collections.topic错误，尝试重新创建
            if "collections.topic" in str(e):
                print(f"Detected ChromaDB schema issue for novel_id {novel_id}. Attempting to fix...")
                try:
                    self._cleanup_corrupted_collection(novel_id)
                    vector_store = self._get_vector_store(novel_id)
                    print(f"Successfully fixed ChromaDB schema for novel_id {novel_id}")
                except Exception as e2:
                    print(f"Failed to fix ChromaDB schema for novel_id {novel_id}: {e2}")
                    return []
            else:
                return []

        print(f"Retrieving {k} relevant chunks for novel_id {novel_id} with query: '{query[:50]}...'")
        try:
            docs = vector_store.similarity_search(query, k=k)
            retrieved_contents = [doc.page_content for doc in docs]
            print(f"Retrieved {len(retrieved_contents)} chunks.")
            return retrieved_contents
        except Exception as e:
            print(f"Error during similarity search for novel_id {novel_id}: {e}")
            # 如果是collections.topic错误，尝试重新创建
            if "collections.topic" in str(e):
                print(f"Detected ChromaDB schema issue during search for novel_id {novel_id}. Attempting to fix...")
                try:
                    self._cleanup_corrupted_collection(novel_id)
                    print(f"Fixed ChromaDB schema for novel_id {novel_id}. Collection is now empty.")
                    return []
                except Exception as e2:
                    print(f"Failed to fix ChromaDB schema for novel_id {novel_id}: {e2}")
            return []

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

    def clear_knowledge_base(self, novel_id: int) -> bool:
        """清除指定小说的知识库（别名为delete_collection）"""
        try:
            self.delete_collection(novel_id)
            return True
        except Exception as e:
            print(f"Error clearing knowledge base for novel_id {novel_id}: {e}")
            return False

    def list_collections(self) -> List[str]:
        """列出所有现有的集合"""
        try:
            # Chroma v0.6.0+ 的新API
            collections = self.chroma_client.list_collections()
            # 新版本直接返回名称列表
            if isinstance(collections, list) and len(collections) > 0:
                if isinstance(collections[0], str):
                    return collections
                else:
                    # 如果返回的是对象，尝试获取name属性
                    return [col.name if hasattr(col, 'name') else str(col) for col in collections]
            return collections if isinstance(collections, list) else []
        except Exception as e:
            print(f"Error listing collections: {e}")
            return []

    def get_collection_stats(self, novel_id: int) -> Dict[str, Any]:
        """获取指定小说知识库的统计信息"""
        try:
            vector_store = self._get_vector_store(novel_id)
            collection_data = vector_store.get()
            return {
                "novel_id": novel_id,
                "collection_name": self._get_collection_name(novel_id),
                "document_count": len(collection_data.get('ids', [])),
                "has_documents": len(collection_data.get('ids', [])) > 0
            }
        except Exception as e:
            print(f"Error getting collection stats for novel_id {novel_id}: {e}")
            return {
                "novel_id": novel_id,
                "collection_name": self._get_collection_name(novel_id),
                "document_count": 0,
                "has_documents": False,
                "error": str(e)
            }


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
