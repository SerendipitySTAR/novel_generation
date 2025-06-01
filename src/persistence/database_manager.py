import sqlite3
from datetime import datetime, timezone

class DatabaseManager:
    def __init__(self, db_name="novel_mvp.db"):
        self.db_name = db_name
        self._initialize_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row # Access columns by name
        return conn

    def _initialize_db(self):
        """Initializes the database and creates the narratives table if it doesn't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS narratives (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_theme TEXT NOT NULL,
                        style_preferences TEXT,
                        generated_outline TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                conn.commit()
            print(f"Database '{self.db_name}' initialized successfully. 'narratives' table is ready.")
        except sqlite3.Error as e:
            print(f"Error initializing database '{self.db_name}': {e}")
            raise # Propagate the error

    def add_narrative(self, user_theme: str, style_preferences: str, generated_outline: str) -> int:
        """Adds a new narrative to the database and returns its ID."""
        if not user_theme or not generated_outline:
            raise ValueError("User theme and generated outline cannot be empty.")

        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO narratives (user_theme, style_preferences, generated_outline, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (user_theme, style_preferences, generated_outline, current_timestamp))
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None: # Should not happen with AUTOINCREMENT if insert was successful
                    raise sqlite3.Error("Failed to retrieve last inserted ID.")
                print(f"Narrative added with ID: {new_id}")
                return new_id
        except sqlite3.Error as e:
            print(f"Error adding narrative: {e}")
            raise

    def get_narrative_by_id(self, narrative_id: int) -> dict | None:
        """Retrieves a single narrative by its ID. Returns a dict or None."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM narratives WHERE id = ?", (narrative_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving narrative by ID {narrative_id}: {e}")
            return None # Or raise

    def list_all_narratives(self) -> list[dict]:
        """Retrieves all narratives from the database. Returns a list of dicts."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM narratives ORDER BY timestamp DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Error listing all narratives: {e}")
            return [] # Or raise

if __name__ == "__main__":
    print("--- Testing DatabaseManager ---")
    # Test in a temporary database
    test_db_name = "test_novel_mvp.db"
    try:
        # Clean up previous test db if it exists
        import os
        if os.path.exists(test_db_name):
            os.remove(test_db_name)
            print(f"Removed old '{test_db_name}'.")

        db_manager = DatabaseManager(db_name=test_db_name)
        print(f"DatabaseManager initialized with '{test_db_name}'.")

        # Test adding a narrative
        print("\nTesting add_narrative...")
        theme1 = "A city powered by dreams."
        style1 = "Fantasy, Surreal"
        outline1 = "In a city where dreams fuel every aspect of life, a young dream-weaver uncovers a plot to corrupt the dream source."
        narrative_id1 = db_manager.add_narrative(user_theme=theme1, style_preferences=style1, generated_outline=outline1)
        print(f"Added narrative with ID: {narrative_id1}")

        theme2 = "The last librarian on Earth."
        style2 = "Post-apocalyptic, introspective"
        outline2 = "After a global catastrophe, the sole surviving librarian protects the world's last collection of books."
        narrative_id2 = db_manager.add_narrative(user_theme=theme2, style_preferences=style2, generated_outline=outline2)
        print(f"Added narrative with ID: {narrative_id2}")

        # Test retrieving a narrative
        print("\nTesting get_narrative_by_id...")
        retrieved_narrative = db_manager.get_narrative_by_id(narrative_id1)
        if retrieved_narrative:
            print(f"Retrieved narrative ID {narrative_id1}: {retrieved_narrative['user_theme']}")
            assert retrieved_narrative["id"] == narrative_id1
            assert retrieved_narrative["user_theme"] == theme1
        else:
            print(f"Could not retrieve narrative ID {narrative_id1}")

        non_existent_narrative = db_manager.get_narrative_by_id(999)
        assert non_existent_narrative is None
        print(f"Attempt to retrieve non-existent narrative ID 999: {'Not found (Correct)' if non_existent_narrative is None else 'Found (Incorrect)'}")


        # Test listing all narratives
        print("\nTesting list_all_narratives...")
        all_narratives = db_manager.list_all_narratives()
        print(f"Found {len(all_narratives)} narratives:")
        for nar in all_narratives:
            print(f"  ID: {nar['id']}, Theme: {nar['user_theme']}, Timestamp: {nar['timestamp']}")
        assert len(all_narratives) == 2

        # Test empty values (should raise ValueError)
        print("\nTesting empty values for add_narrative...")
        try:
            db_manager.add_narrative("", "", "")
        except ValueError as e:
            print(f"Caught expected ValueError: {e}")


    except Exception as e:
        print(f"An error occurred during DatabaseManager testing: {e}")
    finally:
        # Clean up the test database
        if os.path.exists(test_db_name):
            os.remove(test_db_name)
            print(f"Cleaned up '{test_db_name}'.")

    print("--- DatabaseManager Test Finished ---")
