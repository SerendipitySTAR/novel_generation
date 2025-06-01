import sqlite3
from datetime import datetime, timezone

class DatabaseManager:
    def __init__(self, db_name="novel_mvp.db"):
        self.db_name = db_name
        self._initialize_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self):
        """Initializes the database and creates/updates the narratives table."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Updated table creation to include generated_worldview
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS narratives (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_theme TEXT NOT NULL,
                        style_preferences TEXT,
                        generated_outline TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        generated_worldview TEXT
                    )
                """)
                # Basic column existence check and add if missing (for development ease)
                # In production, use a proper migration tool like Alembic.
                cursor.execute("PRAGMA table_info(narratives)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'generated_worldview' not in columns:
                    cursor.execute("ALTER TABLE narratives ADD COLUMN generated_worldview TEXT")
                    print("Added 'generated_worldview' column to 'narratives' table.")

                conn.commit()
            print(f"Database '{self.db_name}' initialized successfully. 'narratives' table is ready.")
        except sqlite3.Error as e:
            print(f"Error initializing database '{self.db_name}': {e}")
            raise

    def add_narrative(self, user_theme: str, style_preferences: str, generated_outline: str, generated_worldview: str | None = None) -> int:
        """Adds a new narrative to the database and returns its ID."""
        if not user_theme or not generated_outline:
            raise ValueError("User theme and generated outline cannot be empty.")

        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO narratives (user_theme, style_preferences, generated_outline, timestamp, generated_worldview)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_theme, style_preferences, generated_outline, current_timestamp, generated_worldview))
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None:
                    raise sqlite3.Error("Failed to retrieve last inserted ID.")
                print(f"Narrative added with ID: {new_id}")
                return new_id
        except sqlite3.Error as e:
            print(f"Error adding narrative: {e}")
            raise

    def update_narrative_worldview(self, narrative_id: int, generated_worldview: str) -> bool:
        """Updates the worldview for an existing narrative. Returns True on success."""
        if not generated_worldview:
            # Depending on requirements, empty string might be acceptable, or raise error
            print("Warning: Attempting to update worldview with empty data.")

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE narratives
                    SET generated_worldview = ?
                    WHERE id = ?
                """, (generated_worldview, narrative_id))
                conn.commit()
                success = cursor.rowcount > 0
                if success:
                    print(f"Worldview updated for narrative ID: {narrative_id}")
                else:
                    print(f"Warning: No narrative found with ID {narrative_id} to update worldview, or data unchanged.")
                return success
        except sqlite3.Error as e:
            print(f"Error updating worldview for narrative ID {narrative_id}: {e}")
            return False # Or raise

    def get_narrative_by_id(self, narrative_id: int) -> dict | None:
        """Retrieves a single narrative by its ID. Returns a dict or None."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Ensure all desired columns are selected
                cursor.execute("SELECT id, user_theme, style_preferences, generated_outline, timestamp, generated_worldview FROM narratives WHERE id = ?", (narrative_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving narrative by ID {narrative_id}: {e}")
            return None

    def list_all_narratives(self) -> list[dict]:
        """Retrieves all narratives from the database. Returns a list of dicts."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Ensure all desired columns are selected
                cursor.execute("SELECT id, user_theme, style_preferences, generated_outline, timestamp, generated_worldview FROM narratives ORDER BY timestamp DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"Error listing all narratives: {e}")
            return []

if __name__ == "__main__":
    print("--- Testing DatabaseManager (with Worldview) ---")
    test_db_name = "test_novel_mvp_wv.db" # Use a different name for this test run
    import os
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    db_manager = DatabaseManager(db_name=test_db_name)
    print(f"DatabaseManager initialized with '{test_db_name}'.")

    # 1. Add a narrative (initially without worldview via add_narrative)
    theme1 = "A chef who cooks emotions into food."
    style1 = "Magical realism"
    outline1 = "A renowned chef discovers their dishes can make people feel specific emotions. They struggle with the ethics of this power."
    narrative_id1 = db_manager.add_narrative(user_theme=theme1, style_preferences=style1, generated_outline=outline1)
    print(f"Added narrative (no worldview yet) with ID: {narrative_id1}")

    retrieved_before_wv = db_manager.get_narrative_by_id(narrative_id1)
    print(f"Retrieved before WV update: {retrieved_before_wv}")
    assert retrieved_before_wv is not None
    assert retrieved_before_wv['generated_worldview'] is None

    # 2. Update with worldview
    worldview_content = "The story is set in a bustling, modern city with a hidden magical underground culinary scene. The mood is whimsical but with an undercurrent of moral tension."
    print(f"\nUpdating narrative ID {narrative_id1} with worldview...")
    update_success = db_manager.update_narrative_worldview(narrative_id1, worldview_content)
    assert update_success is True
    print("Update successful.")

    retrieved_after_wv = db_manager.get_narrative_by_id(narrative_id1)
    print(f"Retrieved after WV update: {retrieved_after_wv}")
    assert retrieved_after_wv is not None
    assert retrieved_after_wv['generated_worldview'] == worldview_content

    # 3. Add another narrative, this time providing worldview directly to add_narrative (testing modification)
    theme2 = "AI therapist develops genuine consciousness."
    style2 = "Sci-fi, psychological"
    outline2 = "An advanced AI designed for therapy starts questioning its own existence after countless sessions."
    worldview2 = "Near-future society heavily reliant on AI for mental well-being. Clean, sterile environments contrast with the AI's messy internal awakening."
    narrative_id2 = db_manager.add_narrative(theme2, style2, outline2, generated_worldview=worldview2)
    print(f"Added narrative ID {narrative_id2} with worldview directly.")

    retrieved_narrative2 = db_manager.get_narrative_by_id(narrative_id2)
    print(f"Retrieved narrative ID {narrative_id2}: {retrieved_narrative2}")
    assert retrieved_narrative2 is not None
    assert retrieved_narrative2['generated_worldview'] == worldview2


    # 4. List all narratives and check worldview content
    print("\nListing all narratives...")
    all_narratives = db_manager.list_all_narratives()
    for nar in all_narratives:
        print(f"  ID: {nar['id']}, Theme: {nar['user_theme']}, WV: {nar['generated_worldview'][:30] if nar['generated_worldview'] else 'None'}...")
    assert len(all_narratives) == 2
    # Check if worldview is present for both
    found_wv1 = any(n['id'] == narrative_id1 and n['generated_worldview'] == worldview_content for n in all_narratives)
    found_wv2 = any(n['id'] == narrative_id2 and n['generated_worldview'] == worldview2 for n in all_narratives)
    assert found_wv1
    assert found_wv2

    # Test updating non-existent ID
    print("\nTesting update for non-existent narrative ID...")
    fail_update = db_manager.update_narrative_worldview(999, "test")
    assert fail_update is False

    if os.path.exists(test_db_name):
        os.remove(test_db_name)
    print(f"Cleaned up '{test_db_name}'.")
    print("--- DatabaseManager (with Worldview) Test Finished ---")
