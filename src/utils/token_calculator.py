#!/usr/bin/env python3
"""
Token Calculator Module

Provides dynamic token estimation and cost calculation for novel generation workflow.
Estimates token usage for different agents and operations based on user configuration.
"""

import math
from typing import Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class TokenEstimate:
    """Represents token usage estimate for a specific operation."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    operation_name: str
    
    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost in USD based on typical GPT-4 pricing."""
        # Using approximate GPT-4 pricing: $0.03/1K input tokens, $0.06/1K output tokens
        input_cost = (self.input_tokens / 1000) * 0.03
        output_cost = (self.output_tokens / 1000) * 0.06
        return input_cost + output_cost


class TokenCalculator:
    """
    Calculates dynamic token requirements for novel generation workflow.
    """
    
    # Base token estimates for different text types (tokens per word)
    TOKENS_PER_WORD = {
        "english_text": 1.33,  # Average for English text
        "structured_output": 1.5,  # JSON/structured formats use more tokens
        "prompt_overhead": 1.2,  # Prompts with instructions
    }
    
    # Base prompt sizes (in tokens)
    BASE_PROMPT_SIZES = {
        "narrative_pathfinder": 800,  # Outline generation prompt
        "world_weaver": 700,  # Worldview generation prompt
        "plot_architect": 900,  # Plot structure prompt
        "character_sculptor": 1000,  # Character generation prompt
        "quality_guardian": 600,  # Review prompt
        "context_synthesizer": 500,  # Chapter brief prompt
        "chapter_chronicler": 800,  # Chapter writing prompt
    }
    
    def __init__(self):
        pass
    
    def estimate_words_to_tokens(self, word_count: int, text_type: str = "english_text") -> int:
        """Convert word count to estimated token count."""
        multiplier = self.TOKENS_PER_WORD.get(text_type, 1.33)
        return math.ceil(word_count * multiplier)
    
    def estimate_narrative_pathfinder_tokens(self, theme_length: int, style_length: int) -> TokenEstimate:
        """Estimate tokens for narrative outline generation."""
        # Input: base prompt + theme + style
        input_tokens = (
            self.BASE_PROMPT_SIZES["narrative_pathfinder"] +
            self.estimate_words_to_tokens(theme_length, "prompt_overhead") +
            self.estimate_words_to_tokens(style_length, "prompt_overhead")
        )

        # Output: 3 outline options, ~300 words each (increased from 200)
        # Need more detailed outlines for better story development
        output_tokens = self.estimate_words_to_tokens(900, "structured_output")

        return TokenEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            operation_name="Narrative Outline Generation"
        )
    
    def estimate_world_weaver_tokens(self, theme_length: int, outline_length: int) -> TokenEstimate:
        """Estimate tokens for worldview generation."""
        input_tokens = (
            self.BASE_PROMPT_SIZES["world_weaver"] +
            self.estimate_words_to_tokens(theme_length, "prompt_overhead") +
            self.estimate_words_to_tokens(outline_length, "prompt_overhead")
        )
        
        # Output: 3 worldview options, ~150 words each
        output_tokens = self.estimate_words_to_tokens(450, "structured_output")
        
        return TokenEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            operation_name="Worldview Generation"
        )
    
    def estimate_plot_architect_tokens(self, outline_length: int, worldview_length: int,
                                     num_chapters: int) -> TokenEstimate:
        """Estimate tokens for plot structure generation."""
        input_tokens = (
            self.BASE_PROMPT_SIZES["plot_architect"] +
            self.estimate_words_to_tokens(outline_length, "prompt_overhead") +
            self.estimate_words_to_tokens(worldview_length, "prompt_overhead")
        )

        # Output: Detailed plot for each chapter, ~300 words per chapter (increased from 150)
        # Each chapter needs multiple detailed fields, so we need more tokens
        words_per_chapter_plot = 300
        output_tokens = self.estimate_words_to_tokens(
            words_per_chapter_plot * num_chapters, "structured_output"
        )

        return TokenEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            operation_name=f"Plot Architecture ({num_chapters} chapters)"
        )
    
    def estimate_character_sculptor_tokens(self, outline_length: int, worldview_length: int,
                                         plot_length: int, num_characters: int = 3) -> TokenEstimate:
        """Estimate tokens for character generation."""
        input_tokens = (
            self.BASE_PROMPT_SIZES["character_sculptor"] +
            self.estimate_words_to_tokens(outline_length, "prompt_overhead") +
            self.estimate_words_to_tokens(worldview_length, "prompt_overhead") +
            self.estimate_words_to_tokens(plot_length, "prompt_overhead")
        )

        # Output: Detailed character profiles, ~400 words per character (increased from 200)
        # Character profiles need extensive detail, so we need more tokens
        words_per_character = 400
        output_tokens = self.estimate_words_to_tokens(
            words_per_character * num_characters, "structured_output"
        )

        return TokenEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            operation_name=f"Character Generation ({num_characters} characters)"
        )
    
    def estimate_quality_guardian_tokens(self, outline_length: int) -> TokenEstimate:
        """Estimate tokens for outline review."""
        input_tokens = (
            self.BASE_PROMPT_SIZES["quality_guardian"] +
            self.estimate_words_to_tokens(outline_length, "prompt_overhead")
        )
        
        # Output: Review scores and justification, ~100 words
        output_tokens = self.estimate_words_to_tokens(100, "structured_output")
        
        return TokenEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            operation_name="Outline Quality Review"
        )
    
    def estimate_context_synthesizer_tokens(self, context_length: int, num_chapters: int) -> TokenEstimate:
        """Estimate tokens for chapter brief generation (per chapter)."""
        input_tokens = (
            self.BASE_PROMPT_SIZES["context_synthesizer"] +
            self.estimate_words_to_tokens(context_length, "prompt_overhead")
        )
        
        # Output: Chapter brief, ~150 words per chapter
        output_tokens = self.estimate_words_to_tokens(150, "structured_output")
        
        # Multiply by number of chapters
        total_input = input_tokens * num_chapters
        total_output = output_tokens * num_chapters
        
        return TokenEstimate(
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_input + total_output,
            operation_name=f"Chapter Brief Generation ({num_chapters} chapters)"
        )
    
    def estimate_chapter_chronicler_tokens(self, brief_length: int, words_per_chapter: int,
                                         num_chapters: int) -> TokenEstimate:
        """Estimate tokens for chapter content generation."""
        input_tokens = (
            self.BASE_PROMPT_SIZES["chapter_chronicler"] +
            self.estimate_words_to_tokens(brief_length, "prompt_overhead")
        )
        
        # Output: Chapter content + title + summary
        # Title: ~5 words, Summary: ~30 words, Content: user-specified words
        words_per_chapter_output = words_per_chapter + 35
        output_tokens = self.estimate_words_to_tokens(words_per_chapter_output, "english_text")
        
        # Multiply by number of chapters
        total_input = input_tokens * num_chapters
        total_output = output_tokens * num_chapters
        
        return TokenEstimate(
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_input + total_output,
            operation_name=f"Chapter Content Generation ({num_chapters} chapters, {words_per_chapter} words each)"
        )


class NovelGenerationCostEstimator:
    """
    Provides comprehensive cost estimation for the entire novel generation workflow.
    """
    
    def __init__(self):
        self.calculator = TokenCalculator()
    
    def estimate_full_workflow_cost(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate total token cost for the complete novel generation workflow.
        
        Args:
            user_config: Dictionary containing:
                - theme: str
                - style_preferences: str  
                - chapters: int
                - words_per_chapter: int
        
        Returns:
            Dictionary with detailed cost breakdown
        """
        theme = user_config.get("theme", "")
        style = user_config.get("style_preferences", "")
        num_chapters = user_config.get("chapters", 3)
        words_per_chapter = user_config.get("words_per_chapter", 1000)
        
        # Estimate text lengths (in words)
        theme_words = len(theme.split())
        style_words = len(style.split())
        
        # Progressive estimates (each step builds on previous)
        estimates = []
        
        # 1. Narrative Pathfinder
        narrative_est = self.calculator.estimate_narrative_pathfinder_tokens(theme_words, style_words)
        estimates.append(narrative_est)
        outline_words = 200  # Estimated selected outline length
        
        # 2. World Weaver
        world_est = self.calculator.estimate_world_weaver_tokens(theme_words, outline_words)
        estimates.append(world_est)
        worldview_words = 150  # Estimated selected worldview length
        
        # 3. Plot Architect
        plot_est = self.calculator.estimate_plot_architect_tokens(outline_words, worldview_words, num_chapters)
        estimates.append(plot_est)
        plot_words = 150 * num_chapters  # Total plot length
        
        # 4. Character Sculptor
        char_est = self.calculator.estimate_character_sculptor_tokens(
            outline_words, worldview_words, plot_words, 3
        )
        estimates.append(char_est)
        
        # 5. Quality Guardian
        quality_est = self.calculator.estimate_quality_guardian_tokens(outline_words)
        estimates.append(quality_est)
        
        # 6. Context Synthesizer
        context_length = outline_words + worldview_words + plot_words + (3 * 200)  # Include characters
        context_est = self.calculator.estimate_context_synthesizer_tokens(context_length, num_chapters)
        estimates.append(context_est)
        
        # 7. Chapter Chronicler
        brief_length = 150  # Estimated brief length per chapter
        chapter_est = self.calculator.estimate_chapter_chronicler_tokens(
            brief_length, words_per_chapter, num_chapters
        )
        estimates.append(chapter_est)
        
        # Calculate totals
        total_input_tokens = sum(est.input_tokens for est in estimates)
        total_output_tokens = sum(est.output_tokens for est in estimates)
        total_tokens = total_input_tokens + total_output_tokens
        total_cost = sum(est.estimated_cost_usd for est in estimates)
        
        return {
            "estimates": estimates,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": total_cost,
            "user_config": user_config
        }
