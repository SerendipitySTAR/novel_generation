import sqlite3
from datetime import datetime, timezone # Corrected import for timezone
from typing import List, Optional, Any # Added Any for cursor.lastrowid
from src.core.models import Novel, Outline, WorldView, Plot, Character, Chapter, KnowledgeBaseEntry

class DatabaseManager:
    def __init__(self, db_name="novel_mvp.db"):
        self.db_name = db_name
        self._create_tables() # Changed from _initialize_db

    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraint enforcement
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _create_tables(self):
        """Creates all necessary tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Novel table (formerly narratives)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS novels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_theme TEXT NOT NULL,
                        style_preferences TEXT,
                        creation_date TEXT NOT NULL,
                        last_updated_date TEXT NOT NULL,
                        active_outline_id INTEGER,
                        active_worldview_id INTEGER,
                        active_plot_id INTEGER,
                        FOREIGN KEY (active_outline_id) REFERENCES outlines(id) ON DELETE SET NULL,
                        FOREIGN KEY (active_worldview_id) REFERENCES worldviews(id) ON DELETE SET NULL,
                        FOREIGN KEY (active_plot_id) REFERENCES plots(id) ON DELETE SET NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS outlines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        novel_id INTEGER NOT NULL,
                        overview_text TEXT NOT NULL,
                        creation_date TEXT NOT NULL,
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS worldviews (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        novel_id INTEGER NOT NULL,
                        description_text TEXT NOT NULL,
                        creation_date TEXT NOT NULL,
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS plots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        novel_id INTEGER NOT NULL,
                        plot_summary TEXT NOT NULL,
                        creation_date TEXT NOT NULL,
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS characters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        novel_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        role_in_story TEXT NOT NULL,
                        creation_date TEXT NOT NULL,
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chapters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        novel_id INTEGER NOT NULL,
                        chapter_number INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        creation_date TEXT NOT NULL,
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
                        UNIQUE(novel_id, chapter_number)
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS knowledge_base_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        novel_id INTEGER NOT NULL,
                        entry_type TEXT NOT NULL,
                        content_text TEXT NOT NULL,
                        embedding BLOB, -- Storing as BLOB for list of floats
                        creation_date TEXT NOT NULL,
                        related_entities TEXT, -- Storing as JSON string
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
            print(f"Database '{self.db_name}' initialized successfully. All tables are ready.")
        except sqlite3.Error as e:
            print(f"Error creating tables in '{self.db_name}': {e}")
            raise

    def _update_novel_last_updated(self, novel_id: int, conn: sqlite3.Connection):
        """Internal helper to update the last_updated_date of a novel."""
        current_timestamp = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute("UPDATE novels SET last_updated_date = ? WHERE id = ?", (current_timestamp, novel_id))

    # --- Novel Methods ---
    def add_novel(self, user_theme: str, style_preferences: str) -> int:
        """Adds a new novel to the database and returns its ID."""
        if not user_theme:
            raise ValueError("User theme cannot be empty.")

        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO novels (user_theme, style_preferences, creation_date, last_updated_date,
                                        active_outline_id, active_worldview_id, active_plot_id)
                    VALUES (?, ?, ?, ?, NULL, NULL, NULL)
                """, (user_theme, style_preferences, current_timestamp, current_timestamp))
                conn.commit()
                new_id: Optional[Any] = cursor.lastrowid
                if new_id is None:
                    raise sqlite3.Error("Failed to retrieve last inserted ID for novel.")
                print(f"Novel added with ID: {new_id}")
                return int(new_id)
        except sqlite3.Error as e:
            print(f"Error adding novel: {e}")
            raise

    def get_novel_by_id(self, novel_id: int) -> Optional[Novel]:
        """Retrieves a single novel by its ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM novels WHERE id = ?", (novel_id,))
                row = cursor.fetchone()
                return Novel(**dict(row)) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving novel by ID {novel_id}: {e}")
            return None

    def list_all_novels(self) -> List[Novel]:
        """Retrieves all novels from the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM novels ORDER BY last_updated_date DESC")
                rows = cursor.fetchall()
                return [Novel(**dict(row)) for row in rows]
        except sqlite3.Error as e:
            print(f"Error listing all novels: {e}")
            return []

    # --- Outline Methods ---
    def add_outline(self, novel_id: int, overview_text: str) -> int:
        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO outlines (novel_id, overview_text, creation_date) VALUES (?, ?, ?)",
                               (novel_id, overview_text, current_timestamp))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for outline.")
                return int(new_id)
        except sqlite3.Error as e:
            print(f"Error adding outline for novel {novel_id}: {e}")
            raise

    def get_outline_by_id(self, outline_id: int) -> Optional[Outline]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM outlines WHERE id = ?", (outline_id,))
                row = cursor.fetchone()
                return Outline(**dict(row)) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving outline by ID {outline_id}: {e}")
            return None

    def update_novel_active_outline(self, novel_id: int, outline_id: Optional[int]):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE novels SET active_outline_id = ? WHERE id = ?", (outline_id, novel_id))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                if cursor.rowcount == 0:
                     print(f"Warning: Novel with ID {novel_id} not found for updating active outline.")
        except sqlite3.Error as e:
            print(f"Error updating active outline for novel {novel_id}: {e}")
            raise

    # --- WorldView Methods ---
    def add_worldview(self, novel_id: int, description_text: str) -> int:
        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO worldviews (novel_id, description_text, creation_date) VALUES (?, ?, ?)",
                               (novel_id, description_text, current_timestamp))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for worldview.")
                return int(new_id)
        except sqlite3.Error as e:
            print(f"Error adding worldview for novel {novel_id}: {e}")
            raise

    def get_worldview_by_id(self, worldview_id: int) -> Optional[WorldView]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM worldviews WHERE id = ?", (worldview_id,))
                row = cursor.fetchone()
                return WorldView(**dict(row)) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving worldview by ID {worldview_id}: {e}")
            return None

    def update_novel_active_worldview(self, novel_id: int, worldview_id: Optional[int]):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE novels SET active_worldview_id = ? WHERE id = ?", (worldview_id, novel_id))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                if cursor.rowcount == 0:
                     print(f"Warning: Novel with ID {novel_id} not found for updating active worldview.")
        except sqlite3.Error as e:
            print(f"Error updating active worldview for novel {novel_id}: {e}")
            raise

    # --- Plot Methods ---
    def add_plot(self, novel_id: int, plot_summary: str) -> int:
        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO plots (novel_id, plot_summary, creation_date) VALUES (?, ?, ?)",
                               (novel_id, plot_summary, current_timestamp))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for plot.")
                return int(new_id)
        except sqlite3.Error as e:
            print(f"Error adding plot for novel {novel_id}: {e}")
            raise

    def get_plot_by_id(self, plot_id: int) -> Optional[Plot]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM plots WHERE id = ?", (plot_id,))
                row = cursor.fetchone()
                return Plot(**dict(row)) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving plot by ID {plot_id}: {e}")
            return None

    def update_novel_active_plot(self, novel_id: int, plot_id: Optional[int]):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE novels SET active_plot_id = ? WHERE id = ?", (plot_id, novel_id))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                if cursor.rowcount == 0:
                     print(f"Warning: Novel with ID {novel_id} not found for updating active plot.")
        except sqlite3.Error as e:
            print(f"Error updating active plot for novel {novel_id}: {e}")
            raise

    # --- Character Methods ---
    def add_character(self, novel_id: int, name: str, description: str, role_in_story: str) -> int:
        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO characters (novel_id, name, description, role_in_story, creation_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (novel_id, name, description, role_in_story, current_timestamp))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for character.")
                return int(new_id)
        except sqlite3.Error as e:
            print(f"Error adding character for novel {novel_id}: {e}")
            raise

    def get_character_by_id(self, character_id: int) -> Optional[Character]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
                row = cursor.fetchone()
                return Character(**dict(row)) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving character by ID {character_id}: {e}")
            return None

    def get_characters_for_novel(self, novel_id: int) -> List[Character]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM characters WHERE novel_id = ? ORDER BY name", (novel_id,))
                rows = cursor.fetchall()
                return [Character(**dict(row)) for row in rows]
        except sqlite3.Error as e:
            print(f"Error retrieving characters for novel {novel_id}: {e}")
            return []

    # --- Chapter Methods ---
    def add_chapter(self, novel_id: int, chapter_number: int, title: str, content: str, summary: str) -> int:
        current_timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chapters (novel_id, chapter_number, title, content, summary, creation_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (novel_id, chapter_number, title, content, summary, current_timestamp))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for chapter.")
                return int(new_id)
        except sqlite3.Error as e:
            print(f"Error adding chapter for novel {novel_id}: {e}")
            raise

    def get_chapter_by_id(self, chapter_id: int) -> Optional[Chapter]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
                row = cursor.fetchone()
                return Chapter(**dict(row)) if row else None
        except sqlite3.Error as e:
            print(f"Error retrieving chapter by ID {chapter_id}: {e}")
            return None

    def get_chapters_for_novel(self, novel_id: int) -> List[Chapter]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM chapters WHERE novel_id = ? ORDER BY chapter_number", (novel_id,))
                rows = cursor.fetchall()
                return [Chapter(**dict(row)) for row in rows]
        except sqlite3.Error as e:
            print(f"Error retrieving chapters for novel {novel_id}: {e}")
            return []

    # --- KnowledgeBaseEntry Methods ---
    def add_kb_entry(self, novel_id: int, entry_type: str, content_text: str,
                     embedding: Optional[List[float]] = None,
                     related_entities: Optional[List[str]] = None) -> int:
        current_timestamp = datetime.now(timezone.utc).isoformat()
        # Convert embedding and related_entities to storable formats
        embedding_blob = sqlite3.Binary(str(embedding).encode()) if embedding else None # Simple serialization
        related_entities_json = str(related_entities) if related_entities else None # Simple serialization as string

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO knowledge_base_entries (novel_id, entry_type, content_text, embedding, creation_date, related_entities)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (novel_id, entry_type, content_text, embedding_blob, current_timestamp, related_entities_json))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for KB entry.")
                return int(new_id)
        except sqlite3.Error as e:
            print(f"Error adding KB entry for novel {novel_id}: {e}")
            raise

    def get_kb_entry_by_id(self, entry_id: int) -> Optional[KnowledgeBaseEntry]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM knowledge_base_entries WHERE id = ?", (entry_id,))
                row_data = cursor.fetchone()
                if row_data:
                    row_dict = dict(row_data)
                    # Deserialize embedding and related_entities
                    if row_dict.get('embedding'):
                        try:
                            row_dict['embedding'] = eval(row_dict['embedding'].decode())
                        except: # simple eval might fail for more complex cases or if not stringified list
                            row_dict['embedding'] = None # Or handle error appropriately
                    if row_dict.get('related_entities'):
                        try:
                            row_dict['related_entities'] = eval(row_dict['related_entities'])
                        except:
                             row_dict['related_entities'] = None # Or handle error
                    return KnowledgeBaseEntry(**row_dict)
                return None
        except sqlite3.Error as e:
            print(f"Error retrieving KB entry by ID {entry_id}: {e}")
            return None

    def get_kb_entries_for_novel(self, novel_id: int, entry_type: Optional[str] = None) -> List[KnowledgeBaseEntry]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM knowledge_base_entries WHERE novel_id = ?"
                params: List[Any] = [novel_id]
                if entry_type:
                    sql += " AND entry_type = ?"
                    params.append(entry_type)
                sql += " ORDER BY creation_date DESC"

                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                entries = []
                for row_data in rows:
                    row_dict = dict(row_data)
                    if row_dict.get('embedding'):
                        try:
                            row_dict['embedding'] = eval(row_dict['embedding'].decode())
                        except:
                            row_dict['embedding'] = None
                    if row_dict.get('related_entities'):
                        try:
                            row_dict['related_entities'] = eval(row_dict['related_entities'])
                        except:
                            row_dict['related_entities'] = None
                    entries.append(KnowledgeBaseEntry(**row_dict))
                return entries
        except sqlite3.Error as e:
            print(f"Error retrieving KB entries for novel {novel_id}: {e}")
            return []

if __name__ == "__main__":
    print("--- Testing DatabaseManager (New Structure) ---")
    test_db_name = "test_novel_full_structure.db"
    import os
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    db_manager = DatabaseManager(db_name=test_db_name)
    print(f"DatabaseManager initialized with '{test_db_name}'.")

    # 1. Add a Novel
    novel_id1 = db_manager.add_novel("Sci-fi adventure on Mars", "Gritty, fast-paced")
    print(f"Added Novel ID: {novel_id1}")
    retrieved_novel = db_manager.get_novel_by_id(novel_id1)
    assert retrieved_novel is not None
    assert retrieved_novel['user_theme'] == "Sci-fi adventure on Mars"
    assert retrieved_novel['active_outline_id'] is None

    # 2. Add Outline, Worldview, Plot for Novel 1
    outline_id1 = db_manager.add_outline(novel_id1, "Chapter 1: Crash landing. Chapter 2: Finding shelter.")
    worldview_id1 = db_manager.add_worldview(novel_id1, "Mars is a harsh, unforgiving desert. Tech is failing.")
    plot_id1 = db_manager.add_plot(novel_id1, "A lone astronaut must survive on Mars after a catastrophic mission failure.")

    print(f"Added Outline ID: {outline_id1}, Worldview ID: {worldview_id1}, Plot ID: {plot_id1}")

    # 3. Set active components for Novel 1
    db_manager.update_novel_active_outline(novel_id1, outline_id1)
    db_manager.update_novel_active_worldview(novel_id1, worldview_id1)
    db_manager.update_novel_active_plot(novel_id1, plot_id1)

    updated_novel1 = db_manager.get_novel_by_id(novel_id1)
    assert updated_novel1 is not None
    assert updated_novel1['active_outline_id'] == outline_id1
    assert updated_novel1['active_worldview_id'] == worldview_id1
    assert updated_novel1['active_plot_id'] == plot_id1
    print(f"Novel 1 active components updated: {updated_novel1}")

    # 4. Retrieve components
    retrieved_outline = db_manager.get_outline_by_id(outline_id1)
    assert retrieved_outline is not None and retrieved_outline['overview_text'].startswith("Chapter 1")
    retrieved_worldview = db_manager.get_worldview_by_id(worldview_id1)
    assert retrieved_worldview is not None and retrieved_worldview['description_text'].startswith("Mars is a harsh")
    retrieved_plot = db_manager.get_plot_by_id(plot_id1)
    assert retrieved_plot is not None and retrieved_plot['plot_summary'].startswith("A lone astronaut")

    # 5. Add Characters for Novel 1
    char1_id = db_manager.add_character(novel_id1, "Jax Rylan", "Stoic astronaut", "Protagonist")
    char2_id = db_manager.add_character(novel_id1, "AI Unit 734", "Mission AI, possibly corrupted", "Supporting/Antagonist")
    characters = db_manager.get_characters_for_novel(novel_id1)
    assert len(characters) == 2
    assert characters[0]['name'] == "AI Unit 734" # Ordered by name
    assert characters[1]['name'] == "Jax Rylan"
    print(f"Added characters for Novel 1: {[c['name'] for c in characters]}")

    # 6. Add Chapters for Novel 1
    chap1_id = db_manager.add_chapter(novel_id1, 1, "Red Desolation", "The lander was a wreck...", "Jax crash lands.")
    chap2_id = db_manager.add_chapter(novel_id1, 2, "Whispers in the Static", "The radio crackled...", "Jax tries to contact Earth.")
    chapters = db_manager.get_chapters_for_novel(novel_id1)
    assert len(chapters) == 2
    assert chapters[0]['chapter_number'] == 1
    assert chapters[1]['title'] == "Whispers in the Static"
    print(f"Added chapters for Novel 1: {[c['title'] for c in chapters]}")

    retrieved_chapter = db_manager.get_chapter_by_id(chap1_id)
    assert retrieved_chapter is not None and retrieved_chapter['summary'] == "Jax crash lands."

    # 7. Add Knowledge Base Entries for Novel 1
    kb1_id = db_manager.add_kb_entry(novel_id1, "character_bio", "Jax Rylan: Born on lunar colony, ex-military.", related_entities=["Jax Rylan"])
    kb2_id = db_manager.add_kb_entry(novel_id1, "world_rule", "Red rust storms are lethal on Mars.", embedding=[0.1, 0.2, 0.3])
    kb_entries = db_manager.get_kb_entries_for_novel(novel_id1)
    assert len(kb_entries) == 2
    kb_char_entries = db_manager.get_kb_entries_for_novel(novel_id1, entry_type="character_bio")
    assert len(kb_char_entries) == 1
    assert kb_char_entries[0]['content_text'].startswith("Jax Rylan: Born")

    retrieved_kb_entry = db_manager.get_kb_entry_by_id(kb2_id)
    assert retrieved_kb_entry is not None
    assert retrieved_kb_entry['embedding'] == [0.1, 0.2, 0.3]
    assert retrieved_kb_entry['related_entities'] is None # Was not eval-able string

    # Test deserialization of related_entities
    kb3_id = db_manager.add_kb_entry(novel_id1, "plot_event", "Communication blackout with Earth.", related_entities="['Jax Rylan', 'Earth']" )
    retrieved_kb_entry_3 = db_manager.get_kb_entry_by_id(kb3_id)
    assert retrieved_kb_entry_3 is not None
    assert retrieved_kb_entry_3['related_entities'] == ['Jax Rylan', 'Earth']


    # 8. List all novels
    novel_id2 = db_manager.add_novel("Fantasy epic", "High fantasy, detailed world-building")
    all_novels = db_manager.list_all_novels()
    assert len(all_novels) == 2
    print(f"All novels: {[n['user_theme'] for n in all_novels]}")

    # Test foreign key ON DELETE SET NULL for active_ids (e.g. delete active outline)
    if updated_novel1 and updated_novel1['active_outline_id']:
        active_outline_id_to_delete = updated_novel1['active_outline_id']
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM outlines WHERE id = ?", (active_outline_id_to_delete,))
            conn.commit()

        novel_after_delete = db_manager.get_novel_by_id(novel_id1)
        assert novel_after_delete is not None
        assert novel_after_delete['active_outline_id'] is None
        print(f"Novel 1 active_outline_id is NULL after deleting the outline: {novel_after_delete['active_outline_id']}")

    # Test foreign key ON DELETE CASCADE (e.g. delete novel, ensure related items are gone)
    # Add a quick item to novel2 to test cascade
    test_char_id = db_manager.add_character(novel_id2, "Cascade Test Char", "desc", "role")
    with db_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM novels WHERE id = ?", (novel_id2,))
        conn.commit()

    assert db_manager.get_novel_by_id(novel_id2) is None
    assert db_manager.get_character_by_id(test_char_id) is None
    print(f"Novel ID {novel_id2} and its related character deleted due to CASCADE.")


    if os.path.exists(test_db_name):
        os.remove(test_db_name)
    print(f"Cleaned up '{test_db_name}'.")
    print("--- DatabaseManager (New Structure) Test Finished ---")
