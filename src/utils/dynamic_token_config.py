#!/usr/bin/env python3
"""
Dynamic Token Configuration Module

Provides dynamic token calculation for different agents based on user configuration.
Replaces hardcoded max_tokens values with calculated ones based on actual requirements.
"""

import math
from typing import Dict, Any, Optional
from .token_calculator import TokenCalculator


class DynamicTokenConfig:
    """
    Calculates appropriate max_tokens values for different agents based on user configuration
    and content requirements.
    """
    
    def __init__(self):
        self.calculator = TokenCalculator()
        # Safety margins to ensure we don't run out of tokens
        self.SAFETY_MARGIN = 1.5  # 50% buffer (increased from 20%)
        self.MIN_TOKENS = 2000    # Minimum tokens for any operation (increased from 1000)
        self.MAX_TOKENS = 32768   # Maximum tokens (model limit)
    
    def _apply_safety_margin(self, estimated_tokens: int) -> int:
        """Apply safety margin and ensure within bounds."""
        tokens_with_margin = math.ceil(estimated_tokens * self.SAFETY_MARGIN)
        return max(self.MIN_TOKENS, min(self.MAX_TOKENS, tokens_with_margin))
    
    def get_narrative_pathfinder_tokens(self, theme: str, style: str) -> int:
        """Calculate max_tokens for narrative outline generation."""
        theme_words = len(theme.split())
        style_words = len(style.split())
        estimate = self.calculator.estimate_narrative_pathfinder_tokens(theme_words, style_words)
        return self._apply_safety_margin(estimate.output_tokens)
    
    def get_world_weaver_tokens(self, theme: str, outline: str) -> int:
        """Calculate max_tokens for worldview generation."""
        theme_words = len(theme.split())
        outline_words = len(outline.split())
        estimate = self.calculator.estimate_world_weaver_tokens(theme_words, outline_words)
        return self._apply_safety_margin(estimate.output_tokens)
    
    def get_plot_architect_tokens(self, outline: str, worldview: str, num_chapters: int) -> int:
        """Calculate max_tokens for plot structure generation."""
        outline_words = len(outline.split())
        worldview_words = len(worldview.split())
        estimate = self.calculator.estimate_plot_architect_tokens(outline_words, worldview_words, num_chapters)
        return self._apply_safety_margin(estimate.output_tokens)
    
    def get_character_sculptor_tokens(self, outline: str, worldview: str, plot: str, 
                                    num_characters: int = 3) -> int:
        """Calculate max_tokens for character generation."""
        outline_words = len(outline.split())
        worldview_words = len(worldview.split())
        plot_words = len(plot.split())
        estimate = self.calculator.estimate_character_sculptor_tokens(
            outline_words, worldview_words, plot_words, num_characters
        )
        return self._apply_safety_margin(estimate.output_tokens)
    
    def get_quality_guardian_tokens(self, outline: str) -> int:
        """Calculate max_tokens for outline review."""
        outline_words = len(outline.split())
        estimate = self.calculator.estimate_quality_guardian_tokens(outline_words)
        return self._apply_safety_margin(estimate.output_tokens)
    
    def get_context_synthesizer_tokens(self, context_data: str) -> int:
        """Calculate max_tokens for chapter brief generation."""
        context_words = len(context_data.split())
        # For single chapter brief
        estimate = self.calculator.estimate_context_synthesizer_tokens(context_words, 1)
        return self._apply_safety_margin(estimate.output_tokens)
    
    def get_chapter_chronicler_tokens(self, brief: str, words_per_chapter: int) -> int:
        """Calculate max_tokens for chapter content generation."""
        brief_words = len(brief.split())
        # For single chapter
        estimate = self.calculator.estimate_chapter_chronicler_tokens(brief_words, words_per_chapter, 1)
        return self._apply_safety_margin(estimate.output_tokens)
    
    def get_tokens_for_agent(self, agent_name: str, context: Dict[str, Any]) -> int:
        """
        Get appropriate max_tokens for any agent based on context.
        
        Args:
            agent_name: Name of the agent (e.g., 'narrative_pathfinder', 'chapter_chronicler')
            context: Dictionary containing relevant context data
        
        Returns:
            Calculated max_tokens value
        """
        try:
            if agent_name == "narrative_pathfinder":
                return self.get_narrative_pathfinder_tokens(
                    context.get("theme", ""),
                    context.get("style", "")
                )
            elif agent_name == "world_weaver":
                return self.get_world_weaver_tokens(
                    context.get("theme", ""),
                    context.get("outline", "")
                )
            elif agent_name == "plot_architect":
                return self.get_plot_architect_tokens(
                    context.get("outline", ""),
                    context.get("worldview", ""),
                    context.get("num_chapters", 3)
                )
            elif agent_name == "character_sculptor":
                return self.get_character_sculptor_tokens(
                    context.get("outline", ""),
                    context.get("worldview", ""),
                    context.get("plot", ""),
                    context.get("num_characters", 3)
                )
            elif agent_name == "quality_guardian":
                return self.get_quality_guardian_tokens(
                    context.get("outline", "")
                )
            elif agent_name == "context_synthesizer":
                return self.get_context_synthesizer_tokens(
                    context.get("context_data", "")
                )
            elif agent_name == "chapter_chronicler":
                return self.get_chapter_chronicler_tokens(
                    context.get("brief", ""),
                    context.get("words_per_chapter", 1000)
                )
            else:
                # Fallback for unknown agents
                print(f"Warning: Unknown agent '{agent_name}', using default token calculation")
                return self.MIN_TOKENS * 2
                
        except Exception as e:
            print(f"Error calculating tokens for agent '{agent_name}': {e}")
            return self.MIN_TOKENS * 2


# Global instance for easy access
dynamic_token_config = DynamicTokenConfig()


def get_dynamic_max_tokens(agent_name: str, context: Dict[str, Any]) -> int:
    """
    Convenience function to get dynamic max_tokens for an agent.
    
    Args:
        agent_name: Name of the agent
        context: Context data for token calculation
    
    Returns:
        Calculated max_tokens value
    """
    return dynamic_token_config.get_tokens_for_agent(agent_name, context)


def log_token_usage(agent_name: str, calculated_tokens: int, context: Dict[str, Any]):
    """
    Log token usage information for debugging and monitoring.
    
    Args:
        agent_name: Name of the agent
        calculated_tokens: Calculated max_tokens value
        context: Context data used for calculation
    """
    print(f"DynamicTokenConfig: {agent_name}")
    print(f"  Calculated max_tokens: {calculated_tokens:,}")
    
    # Log key context information
    if "words_per_chapter" in context:
        print(f"  Words per chapter: {context['words_per_chapter']}")
    if "num_chapters" in context:
        print(f"  Number of chapters: {context['num_chapters']}")
    
    # Estimate input size
    total_input_words = 0
    for key, value in context.items():
        if isinstance(value, str) and key in ["theme", "style", "outline", "worldview", "plot", "brief", "context_data"]:
            words = len(value.split())
            total_input_words += words
            print(f"  {key.capitalize()} words: {words}")
    
    if total_input_words > 0:
        estimated_input_tokens = math.ceil(total_input_words * 1.33)  # Average tokens per word
        print(f"  Estimated input tokens: {estimated_input_tokens:,}")
        print(f"  Total estimated tokens: {estimated_input_tokens + calculated_tokens:,}")
