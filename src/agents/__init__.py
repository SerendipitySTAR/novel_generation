# src/agents/__init__.py
# This file makes the 'agents' directory a Python package.

# Import agent classes here to make them available when the package is imported,
# e.g., from src.agents import NarrativePathfinderAgent

from .narrative_pathfinder_agent import NarrativePathfinderAgent
from .world_weaver_agent import WorldWeaverAgent
from .plot_architect_agent import PlotArchitectAgent
from .character_sculptor_agent import CharacterSculptorAgent
from .chapter_chronicler_agent import ChapterChroniclerAgent
from .quality_guardian_agent import QualityGuardianAgent
from .content_integrity_agent import ContentIntegrityAgent
from .context_synthesizer_agent import ContextSynthesizerAgent
from .lore_keeper_agent import LoreKeeperAgent
from .conflict_detection_agent import ConflictDetectionAgent
from .conflict_resolution_agent import ConflictResolutionAgent # New agent

__all__ = [
    "NarrativePathfinderAgent",
    "WorldWeaverAgent",
    "PlotArchitectAgent",
    "CharacterSculptorAgent",
    "ChapterChroniclerAgent",
    "QualityGuardianAgent",
    "ContentIntegrityAgent",
    "ContextSynthesizerAgent",
    "LoreKeeperAgent",
    "ConflictDetectionAgent",
    "ConflictResolutionAgent", # New agent
]
