from typing import TypedDict, List, Optional

class Novel(TypedDict):
    id: int
    user_theme: str
    style_preferences: str
    creation_date: str
    last_updated_date: str
    active_outline_id: Optional[int]
    active_worldview_id: Optional[int]
    active_plot_id: Optional[int]

class Outline(TypedDict):
    id: int
    novel_id: int
    overview_text: str
    creation_date: str

class WorldView(TypedDict):
    id: int
    novel_id: int
    description_text: str
    creation_date: str

class Plot(TypedDict):
    id: int
    novel_id: int
    plot_summary: str  # This will now store JSON string of List[PlotChapterDetail]
    creation_date: str

class Character(TypedDict):
    id: int
    novel_id: int
    name: str
    description: str
    role_in_story: str
    creation_date: str

class Chapter(TypedDict):
    id: int
    novel_id: int
    chapter_number: int
    title: str
    content: str
    summary: str
    creation_date: str

class KnowledgeBaseEntry(TypedDict):
    id: int
    novel_id: int
    entry_type: str  # e.g., 'character_bio', 'world_rule', 'plot_event'
    content_text: str
    embedding: Optional[List[float]]
    creation_date: str
    related_entities: Optional[List[str]]  # e.g. character names, location names

class PlotChapterDetail(TypedDict):
    chapter_number: int
    title: str
    estimated_words: Optional[int]
    core_scene_summary: Optional[str]
    characters_present: Optional[List[str]]
    key_events_and_plot_progression: Optional[str]
    goal_and_conflict: Optional[str]
    turning_point: Optional[str]
    tone_and_style_notes: Optional[str]
    suspense_or_hook: Optional[str]
    raw_llm_output_for_chapter: Optional[str]
