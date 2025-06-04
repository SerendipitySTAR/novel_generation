import sqlite3
import json # Added for JSON deserialization
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from src.core.models import (
    Novel, Outline, WorldView, Plot, Character, Chapter, KnowledgeBaseEntry,
    DetailedCharacterProfile, PlotChapterDetail # Added DetailedCharacterProfile and PlotChapterDetail
)

class DatabaseManager:
    def __init__(self, db_name="novel_mvp.db"):
        self.db_name = db_name
        self._create_tables()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _create_tables(self):
        # ... (create_tables method remains the same)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
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
                        plot_summary TEXT NOT NULL, -- Stores JSON string of List[PlotChapterDetail]
                        creation_date TEXT NOT NULL,
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS characters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        novel_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL, -- Stores JSON string of DetailedCharacterProfile
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
                        embedding BLOB,
                        creation_date TEXT NOT NULL,
                        related_entities TEXT,
                        FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
                    )
                """)
                conn.commit()
            print(f"Database '{self.db_name}' initialized successfully. All tables are ready.")
        except sqlite3.Error as e:
            print(f"Error creating tables in '{self.db_name}': {e}")
            raise


    def _update_novel_last_updated(self, novel_id: int, conn: sqlite3.Connection):
        current_timestamp = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute("UPDATE novels SET last_updated_date = ? WHERE id = ?", (current_timestamp, novel_id))

    # --- Novel Methods ---
    # ... (add_novel, get_novel_by_id, list_all_novels remain the same)
    def add_novel(self, user_theme: str, style_preferences: str) -> int:
        if not user_theme: raise ValueError("User theme cannot be empty.")
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO novels (user_theme, style_preferences, creation_date, last_updated_date) VALUES (?, ?, ?, ?)",
                            (user_theme, style_preferences, ts, ts))
                conn.commit()
                new_id = cur.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for novel.")
                return int(new_id)
        except sqlite3.Error as e: print(f"Error adding novel: {e}"); raise

    def get_novel_by_id(self, novel_id: int) -> Optional[Novel]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM novels WHERE id = ?", (novel_id,))
                row = cur.fetchone()
                return Novel(**dict(row)) if row else None
        except sqlite3.Error as e: print(f"Error retrieving novel ID {novel_id}: {e}"); return None

    def list_all_novels(self) -> List[Novel]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM novels ORDER BY last_updated_date DESC")
                return [Novel(**dict(row)) for row in cur.fetchall()]
        except sqlite3.Error as e: print(f"Error listing novels: {e}"); return []

    # --- Outline Methods ---
    # ... (add_outline, get_outline_by_id, update_novel_active_outline remain the same)
    def add_outline(self, novel_id: int, overview_text: str) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO outlines (novel_id, overview_text, creation_date) VALUES (?, ?, ?)",
                               (novel_id, overview_text, ts))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cur.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for outline.")
                return int(new_id)
        except sqlite3.Error as e: print(f"Error adding outline: {e}"); raise

    def get_outline_by_id(self, outline_id: int) -> Optional[Outline]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM outlines WHERE id = ?", (outline_id,))
                row = cur.fetchone()
                return Outline(**dict(row)) if row else None
        except sqlite3.Error as e: print(f"Error retrieving outline ID {outline_id}: {e}"); return None

    def update_novel_active_outline(self, novel_id: int, outline_id: Optional[int]):
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE novels SET active_outline_id = ? WHERE id = ?", (outline_id, novel_id))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
        except sqlite3.Error as e: print(f"Error updating active outline: {e}"); raise


    # --- WorldView Methods ---
    # ... (add_worldview, get_worldview_by_id, update_novel_active_worldview remain the same)
    def add_worldview(self, novel_id: int, description_text: str) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO worldviews (novel_id, description_text, creation_date) VALUES (?, ?, ?)",
                               (novel_id, description_text, ts))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cur.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for worldview.")
                return int(new_id)
        except sqlite3.Error as e: print(f"Error adding worldview: {e}"); raise

    def get_worldview_by_id(self, worldview_id: int) -> Optional[WorldView]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM worldviews WHERE id = ?", (worldview_id,))
                row = cur.fetchone()
                return WorldView(**dict(row)) if row else None
        except sqlite3.Error as e: print(f"Error retrieving worldview ID {worldview_id}: {e}"); return None

    def update_novel_active_worldview(self, novel_id: int, worldview_id: Optional[int]):
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE novels SET active_worldview_id = ? WHERE id = ?", (worldview_id, novel_id))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
        except sqlite3.Error as e: print(f"Error updating active worldview: {e}"); raise

    # --- Plot Methods ---
    # ... (add_plot, get_plot_by_id, update_novel_active_plot remain the same)
    # get_plot_by_id currently returns Plot with plot_summary as JSON string. Deserialization can be added if needed by caller.
    def add_plot(self, novel_id: int, plot_summary: str) -> int: # plot_summary is now JSON string
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO plots (novel_id, plot_summary, creation_date) VALUES (?, ?, ?)",
                               (novel_id, plot_summary, ts))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cur.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for plot.")
                return int(new_id)
        except sqlite3.Error as e: print(f"Error adding plot: {e}"); raise

    def get_plot_by_id(self, plot_id: int) -> Optional[Plot]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM plots WHERE id = ?", (plot_id,))
                row = cur.fetchone()
                return Plot(**dict(row)) if row else None # plot_summary will be JSON string
        except sqlite3.Error as e: print(f"Error retrieving plot ID {plot_id}: {e}"); return None

    def update_novel_active_plot(self, novel_id: int, plot_id: Optional[int]):
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE novels SET active_plot_id = ? WHERE id = ?", (plot_id, novel_id))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
        except sqlite3.Error as e: print(f"Error updating active plot: {e}"); raise


    # --- Character Methods ---
    def add_character(self, novel_id: int, name: str, description: str, role_in_story: str) -> int:
        # description is now expected to be a JSON string of DetailedCharacterProfile (excluding id, novel_id, creation_date)
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

    def delete_character(self, character_id: int) -> bool:
        """删除指定的角色"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM characters WHERE id = ?", (character_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error deleting character: {e}")
            return False

    def update_character(self, character_id: int, name: str = None, description: str = None, role_in_story: str = None) -> bool:
        """更新角色信息"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                updates = []
                params = []

                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                if role_in_story is not None:
                    updates.append("role_in_story = ?")
                    params.append(role_in_story)

                if not updates:
                    return False

                params.append(character_id)
                query = f"UPDATE characters SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error updating character: {e}")
            return False

    def clear_characters_for_novel(self, novel_id: int) -> bool:
        """清除指定小说的所有角色"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM characters WHERE novel_id = ?", (novel_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error clearing characters for novel {novel_id}: {e}")
            return False

    def get_character_by_id(self, character_id: int) -> Optional[DetailedCharacterProfile]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
                row = cursor.fetchone()
                if row:
                    detailed_profile_data: Dict[str, Any] = {}
                    if row['description']:
                        try:
                            detailed_profile_data = json.loads(row['description'])
                        except json.JSONDecodeError as e:
                            print(f"Error decoding character description JSON for id {character_id}: {e}. Description: {row['description']}")
                            # Fallback: use raw description if not valid JSON, or parts of it
                            detailed_profile_data['background_story'] = f"Could not parse full details. Raw description: {row['description']}"


                    # Construct DetailedCharacterProfile
                    # Fields from DB row take precedence for id, novel_id, name, role, creation_date
                    profile = DetailedCharacterProfile(
                        character_id=row['id'],
                        novel_id=row['novel_id'],
                        name=row['name'],
                        role_in_story=row['role_in_story'],
                        creation_date=row['creation_date'],
                        # Fields from JSON description
                        gender=detailed_profile_data.get('gender'),
                        age=detailed_profile_data.get('age'),
                        race_or_species=detailed_profile_data.get('race_or_species'),
                        appearance_summary=detailed_profile_data.get('appearance_summary'),
                        clothing_style=detailed_profile_data.get('clothing_style'),
                        background_story=detailed_profile_data.get('background_story'),
                        personality_traits=detailed_profile_data.get('personality_traits'),
                        values_and_beliefs=detailed_profile_data.get('values_and_beliefs'),
                        strengths=detailed_profile_data.get('strengths'),
                        weaknesses=detailed_profile_data.get('weaknesses'),
                        quirks_or_mannerisms=detailed_profile_data.get('quirks_or_mannerisms'),
                        catchphrase_or_verbal_style=detailed_profile_data.get('catchphrase_or_verbal_style'),
                        skills_and_abilities=detailed_profile_data.get('skills_and_abilities'),
                        special_powers=detailed_profile_data.get('special_powers'),
                        power_level_assessment=detailed_profile_data.get('power_level_assessment'),
                        motivations_deep_drive=detailed_profile_data.get('motivations_deep_drive'),
                        goal_short_term=detailed_profile_data.get('goal_short_term'),
                        goal_long_term=detailed_profile_data.get('goal_long_term'),
                        character_arc_potential=detailed_profile_data.get('character_arc_potential'),
                        relationships_initial_notes=detailed_profile_data.get('relationships_initial_notes'),
                        raw_llm_output_for_character=detailed_profile_data.get('raw_llm_output_for_character')
                    )
                    return profile
                return None
        except sqlite3.Error as e:
            print(f"Error retrieving character by ID {character_id}: {e}")
            return None

    def get_characters_for_novel(self, novel_id: int) -> List[DetailedCharacterProfile]:
        characters_list: List[DetailedCharacterProfile] = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM characters WHERE novel_id = ? ORDER BY name", (novel_id,))
                rows = cursor.fetchall()
                for row in rows:
                    detailed_profile_data: Dict[str, Any] = {}
                    if row['description']:
                        try:
                            detailed_profile_data = json.loads(row['description'])
                        except json.JSONDecodeError as e:
                            print(f"Error decoding character description JSON for id {row['id']}: {e}. Description: {row['description']}")
                            detailed_profile_data['background_story'] = f"Could not parse full details. Raw description: {row['description']}"

                    profile = DetailedCharacterProfile(
                        character_id=row['id'],
                        novel_id=row['novel_id'],
                        name=row['name'],
                        role_in_story=row['role_in_story'],
                        creation_date=row['creation_date'],
                        gender=detailed_profile_data.get('gender'),
                        age=detailed_profile_data.get('age'),
                        race_or_species=detailed_profile_data.get('race_or_species'),
                        appearance_summary=detailed_profile_data.get('appearance_summary'),
                        clothing_style=detailed_profile_data.get('clothing_style'),
                        background_story=detailed_profile_data.get('background_story'),
                        personality_traits=detailed_profile_data.get('personality_traits'),
                        values_and_beliefs=detailed_profile_data.get('values_and_beliefs'),
                        strengths=detailed_profile_data.get('strengths'),
                        weaknesses=detailed_profile_data.get('weaknesses'),
                        quirks_or_mannerisms=detailed_profile_data.get('quirks_or_mannerisms'),
                        catchphrase_or_verbal_style=detailed_profile_data.get('catchphrase_or_verbal_style'),
                        skills_and_abilities=detailed_profile_data.get('skills_and_abilities'),
                        special_powers=detailed_profile_data.get('special_powers'),
                        power_level_assessment=detailed_profile_data.get('power_level_assessment'),
                        motivations_deep_drive=detailed_profile_data.get('motivations_deep_drive'),
                        goal_short_term=detailed_profile_data.get('goal_short_term'),
                        goal_long_term=detailed_profile_data.get('goal_long_term'),
                        character_arc_potential=detailed_profile_data.get('character_arc_potential'),
                        relationships_initial_notes=detailed_profile_data.get('relationships_initial_notes'),
                        raw_llm_output_for_character=detailed_profile_data.get('raw_llm_output_for_character')
                    )
                    characters_list.append(profile)
            return characters_list
        except sqlite3.Error as e:
            print(f"Error retrieving characters for novel {novel_id}: {e}")
            return []

    # --- Chapter Methods ---
    # ... (add_chapter, get_chapter_by_id, get_chapters_for_novel remain the same)
    def add_chapter(self, novel_id: int, chapter_number: int, title: str, content: str, summary: str) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO chapters (novel_id, chapter_number, title, content, summary, creation_date) VALUES (?, ?, ?, ?, ?, ?)",
                               (novel_id, chapter_number, title, content, summary, ts))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cur.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for chapter.")
                return int(new_id)
        except sqlite3.Error as e: print(f"Error adding chapter: {e}"); raise

    def get_chapter_by_id(self, chapter_id: int) -> Optional[Chapter]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
                row = cur.fetchone()
                return Chapter(**dict(row)) if row else None
        except sqlite3.Error as e: print(f"Error retrieving chapter ID {chapter_id}: {e}"); return None

    def get_chapters_for_novel(self, novel_id: int) -> List[Chapter]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM chapters WHERE novel_id = ? ORDER BY chapter_number", (novel_id,))
                return [Chapter(**dict(row)) for row in cur.fetchall()]
        except sqlite3.Error as e: print(f"Error retrieving chapters for novel {novel_id}: {e}"); return []


    # --- KnowledgeBaseEntry Methods ---
    # ... (add_kb_entry, get_kb_entry_by_id, get_kb_entries_for_novel remain the same)
    def add_kb_entry(self, novel_id: int, entry_type: str, content_text: str,
                     embedding: Optional[List[float]] = None,
                     related_entities: Optional[List[str]] = None) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        emb_blob = sqlite3.Binary(str(embedding).encode()) if embedding else None
        rel_ent_json = str(related_entities) if related_entities else None
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO knowledge_base_entries (novel_id, entry_type, content_text, embedding, creation_date, related_entities) VALUES (?, ?, ?, ?, ?, ?)",
                               (novel_id, entry_type, content_text, emb_blob, ts, rel_ent_json))
                self._update_novel_last_updated(novel_id, conn)
                conn.commit()
                new_id = cur.lastrowid
                if new_id is None: raise sqlite3.Error("Failed to retrieve ID for KB entry.")
                return int(new_id)
        except sqlite3.Error as e: print(f"Error adding KB entry: {e}"); raise

    def get_kb_entry_by_id(self, entry_id: int) -> Optional[KnowledgeBaseEntry]:
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM knowledge_base_entries WHERE id = ?", (entry_id,))
                row = cur.fetchone()
                if not row: return None
                rd = dict(row)
                if rd.get('embedding'): rd['embedding'] = eval(rd['embedding'].decode()) if isinstance(rd['embedding'], bytes) else None
                if rd.get('related_entities'): rd['related_entities'] = eval(rd['related_entities']) if isinstance(rd['related_entities'], str) else None
                return KnowledgeBaseEntry(**rd)
        except Exception as e: print(f"Error retrieving KB entry ID {entry_id}: {e}"); return None

    def get_kb_entries_for_novel(self, novel_id: int, entry_type: Optional[str] = None) -> List[KnowledgeBaseEntry]:
        entries = []
        try:
            with self._get_connection() as conn:
                cur = conn.cursor()
                sql = "SELECT * FROM knowledge_base_entries WHERE novel_id = ?"
                params: List[Any] = [novel_id]
                if entry_type: sql += " AND entry_type = ?"; params.append(entry_type)
                sql += " ORDER BY creation_date DESC"
                cur.execute(sql, tuple(params))
                for row in cur.fetchall():
                    rd = dict(row)
                    if rd.get('embedding'): rd['embedding'] = eval(rd['embedding'].decode()) if isinstance(rd['embedding'], bytes) else None
                    if rd.get('related_entities'): rd['related_entities'] = eval(rd['related_entities']) if isinstance(rd['related_entities'], str) else None
                    entries.append(KnowledgeBaseEntry(**rd))
            return entries
        except Exception as e: print(f"Error retrieving KB entries for novel {novel_id}: {e}"); return []


if __name__ == "__main__":
    print("--- Testing DatabaseManager (with DetailedCharacterProfile handling) ---")
    test_db_name = "test_db_manager_detailed_char.db"
    import os
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    db_manager = DatabaseManager(db_name=test_db_name)

    # Test Novel
    novel_id = db_manager.add_novel("Test Novel for Characters", "Test Style")

    # Test Character with Detailed Profile
    char_name = "Jax The Mighty"
    char_role = "Protagonist"
    detailed_profile_content = DetailedCharacterProfile(
        character_id=None, novel_id=None, creation_date=None, # These will be set by DB or ignored in JSON
        name=char_name, # This will also be a direct DB column
        gender="Male",
        age="30s",
        race_or_species="Human",
        appearance_summary="Tall and rugged, with a scar over his left eye.",
        clothing_style="Worn leather armor and a heavy cloak.",
        background_story="A former soldier trying to escape his past.",
        personality_traits="Gruff, Loyal, Secretive", # Stored as string, but can be parsed if needed
        values_and_beliefs="Believes in second chances, but trusts few.",
        strengths=["Swordsmanship", "Survival skills"],
        weaknesses=["His past trauma", "Distrustful of authority"],
        quirks_or_mannerisms=["Taps his sword hilt when thinking"],
        catchphrase_or_verbal_style="Prefers silence but speaks bluntly.",
        skills_and_abilities=["Tracking (Expert)", "Lockpicking (Adept)"],
        special_powers=None, # Explicitly None
        power_level_assessment="Seasoned warrior",
        motivations_deep_drive="To find peace and redemption.",
        goal_short_term="Find a safe place to hide.",
        goal_long_term="Confront the warlord who destroyed his village.",
        character_arc_potential="From a loner to a leader.",
        relationships_initial_notes="Will likely clash with authority figures but protect the innocent.",
        role_in_story=char_role, # This will also be a direct DB column
        raw_llm_output_for_character="Raw LLM text for Jax..." # For debugging
    )

    # Create a dict from DetailedCharacterProfile, excluding fields managed by the DB table directly
    # (id, novel_id, name, role_in_story, creation_date) as these are columns in `characters` table.
    # The agent would prepare this JSON part.
    profile_json_data = {k: v for k, v in detailed_profile_content.items()
                         if k not in ['character_id', 'novel_id', 'name', 'role_in_story', 'creation_date']}
    description_json_str = json.dumps(profile_json_data, ensure_ascii=False, indent=2)

    char_id = db_manager.add_character(novel_id, char_name, description_json_str, char_role)
    print(f"Added character '{char_name}' with ID: {char_id}")

    # Test get_character_by_id
    retrieved_char_profile = db_manager.get_character_by_id(char_id)
    assert retrieved_char_profile is not None, f"Character ID {char_id} not found!"
    print(f"\nRetrieved Character (Detailed Profile) by ID {char_id}:")
    # for key, value in retrieved_char_profile.items():
    #     print(f"  {key}: {value}")
    assert retrieved_char_profile['character_id'] == char_id
    assert retrieved_char_profile['novel_id'] == novel_id
    assert retrieved_char_profile['name'] == char_name
    assert retrieved_char_profile['role_in_story'] == char_role
    assert retrieved_char_profile['gender'] == "Male"
    assert retrieved_char_profile['background_story'] == "A former soldier trying to escape his past."
    assert "Swordsmanship" in retrieved_char_profile['strengths'] if retrieved_char_profile['strengths'] else False
    assert retrieved_char_profile['special_powers'] is None # Check for correct handling of None
    print("  Detailed profile fields verified successfully via get_character_by_id.")


    # Test get_characters_for_novel
    db_manager.add_character(novel_id, "Silas the Sly", json.dumps({"name": "Silas the Sly", "age": "40s", "background_story": "A cunning thief."}, ensure_ascii=False, indent=2), "Antagonist")
    all_novel_chars = db_manager.get_characters_for_novel(novel_id)
    assert len(all_novel_chars) == 2, f"Expected 2 characters, got {len(all_novel_chars)}"
    print(f"\nRetrieved {len(all_novel_chars)} characters for Novel ID {novel_id}:")
    for char_prof in all_novel_chars:
        print(f"  - ID: {char_prof['character_id']}, Name: {char_prof['name']}, Role: {char_prof['role_in_story']}, Age: {char_prof.get('age', 'N/A')}")
        if char_prof['name'] == "Jax The Mighty":
             assert "Survival skills" in char_prof['strengths'] if char_prof['strengths'] else False
    print("  get_characters_for_novel seems to correctly deserialize.")

    # Test Plot JSON storage (conceptual, as PlotChapterDetail is complex)
    sample_plot_details = [
        PlotChapterDetail(chapter_number=1, title="The Beginning", estimated_words=1000, core_scene_summary="Intro", characters_present=["Jax"], key_events_and_plot_progression="Event A", goal_and_conflict="Goal A", turning_point="None", tone_and_style_notes="Fast", suspense_or_hook="Hook A", raw_llm_output_for_chapter="..."),
        PlotChapterDetail(chapter_number=2, title="The Middle", estimated_words=1500, core_scene_summary="Middle part", characters_present=["Jax", "Silas"], key_events_and_plot_progression="Event B", goal_and_conflict="Goal B", turning_point="Big one", tone_and_style_notes="Slow", suspense_or_hook="Hook B", raw_llm_output_for_chapter="...")
    ]
    plot_id = db_manager.add_plot(novel_id, json.dumps(sample_plot_details, ensure_ascii=False, indent=2))
    retrieved_plot_obj = db_manager.get_plot_by_id(plot_id)
    assert retrieved_plot_obj is not None
    print(f"\nRetrieved Plot ID {plot_id}. Summary (JSON string): {retrieved_plot_obj['plot_summary'][:100]}...")
    try:
        deserialized_plot_summary = json.loads(retrieved_plot_obj['plot_summary'])
        assert isinstance(deserialized_plot_summary, list)
        assert len(deserialized_plot_summary) == 2
        assert deserialized_plot_summary[0]['title'] == "The Beginning"
        print("  Plot JSON string successfully deserialized and verified.")
    except json.JSONDecodeError as e:
        print(f"  Failed to deserialize plot_summary JSON: {e}")


    if os.path.exists(test_db_name):
        os.remove(test_db_name)
    print(f"\nCleaned up '{test_db_name}'.")
    print("--- DatabaseManager (with DetailedCharacterProfile handling) Test Finished ---")
