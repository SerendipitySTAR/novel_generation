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
    description_text: str # This will store the core_concept of the selected WorldviewDetail, or a simple string if not structured.
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
    # Description will now store a JSON string serialization of DetailedCharacterProfile
    # for characters generated with the enhanced CharacterSculptorAgent.
    # For older data or simpler characters, it might be plain text.
    description: str
    role_in_story: str # e.g., Protagonist, Antagonist, Mentor, Love Interest, Foil
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

class WorldviewDetail(TypedDict):
    world_name: Optional[str]
    core_concept: str
    key_elements: Optional[List[str]]
    atmosphere: Optional[str]
    raw_llm_output_for_worldview: Optional[str]

class DetailedCharacterProfile(TypedDict):
    character_id: Optional[int] # Populated after DB save
    novel_id: Optional[int] # Populated by agent
    creation_date: Optional[str] # Populated by agent/DB

    name: str
    gender: Optional[str]
    age: Optional[str]  # e.g., "appears 20s", "ancient", "young adult"
    race_or_species: Optional[str]
    appearance_summary: Optional[str] # General physical description
    clothing_style: Optional[str]
    background_story: Optional[str] # Key points of their history, upbringing, significant life events
    personality_traits: Optional[str] # Main traits, e.g., "Brave, Curious, Stubborn" or a short paragraph
    values_and_beliefs: Optional[str] # What they hold dear, their moral compass
    strengths: Optional[List[str]] # List of key strengths, e.g., ["Strategic thinker", "Loyal friend"]
    weaknesses: Optional[List[str]] # List of key weaknesses, e.g., ["Impulsive", "Afraid of heights"]
    quirks_or_mannerisms: Optional[List[str]] # e.g., ["Taps fingers when thinking", "Always wears a hat"]
    catchphrase_or_verbal_style: Optional[str] # e.g., "By the stars!", or "Speaks very formally"
    skills_and_abilities: Optional[List[str]] # e.g., ["Swordsmanship (Expert)", "Fluent in Ancient Elvish", "Basic potion making"]
    special_powers: Optional[List[str]] # e.g., ["Can control fire (novice)", "Telepathic suggestion"] - must align with worldview
    power_level_assessment: Optional[str] # e.g., "Novice mage", "Seasoned warrior", "Powerful but untrained"
    motivations_deep_drive: Optional[str] # Their core, underlying motivation
    goal_short_term: Optional[str] # What they want to achieve in the immediate future of the story
    goal_long_term: Optional[str] # Their ultimate ambition or desire
    character_arc_potential: Optional[str] # How they are expected to change or grow throughout the story
    relationships_initial_notes: Optional[str] # Text describing initial ideas for relationships with other potential characters, factions, or types
    role_in_story: Optional[str]
    raw_llm_output_for_character: Optional[str] # For debugging the LLM output for this specific character
