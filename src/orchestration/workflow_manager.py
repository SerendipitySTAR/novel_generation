from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, List, Annotated, Dict, Optional
import operator
import os
import json
import gc
from dotenv import load_dotenv
from src.core.auto_decision_engine import AutoDecisionEngine
import logging

logger = logging.getLogger(__name__)

# 尝试导入 psutil，如果不可用则使用基本的内存监控
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("WARNING: psutil not available, memory monitoring will be limited")

# Agent Imports
from src.agents.narrative_pathfinder_agent import NarrativePathfinderAgent
from src.agents.world_weaver_agent import WorldWeaverAgent
from src.agents.plot_architect_agent import PlotArchitectAgent
from src.agents.character_sculptor_agent import CharacterSculptorAgent
from src.agents.lore_keeper_agent import LoreKeeperAgent
from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent
from src.agents.quality_guardian_agent import QualityGuardianAgent # Import added
from src.agents.content_integrity_agent import ContentIntegrityAgent
from src.agents.conflict_detection_agent import ConflictDetectionAgent
from src.agents.conflict_resolution_agent import ConflictResolutionAgent # New Agent
from src.llm_abstraction.llm_client import LLMClient # Ensure LLMClient is imported

# Persistence and Core Models
from src.persistence.database_manager import DatabaseManager
from src.core.models import PlotChapterDetail, Plot, Character, Chapter, Outline, WorldView, Novel, WorldviewDetail

# --- State Definition ---
class UserInput(TypedDict):
    theme: str
    style_preferences: Optional[str]
    chapters: Optional[int]  # 新增：用户指定的章节数
    words_per_chapter: Optional[int]
    auto_mode: Optional[bool]  # 新增：自动模式，跳过用户交互
    interaction_mode: Optional[str] # "cli" or "api"

class NovelWorkflowState(TypedDict):
    user_input: UserInput
    error_message: Optional[str]
    history: Annotated[List[str], operator.add]
    novel_id: Optional[int]
    novel_data: Optional[Novel]
    narrative_outline_text: Optional[str]
    all_generated_outlines: Optional[List[str]]
    outline_id: Optional[int]
    outline_data: Optional[Outline]
    outline_review: Optional[Dict[str, Any]] # New field for review
    all_generated_worldviews: Optional[List[WorldviewDetail]]
    selected_worldview_detail: Optional[WorldviewDetail]
    worldview_id: Optional[int]
    worldview_data: Optional[WorldView]
    plot_id: Optional[int]
    detailed_plot_data: Optional[List[PlotChapterDetail]]
    plot_data: Optional[Plot]
    all_generated_character_options: Optional[Dict[str, List[DetailedCharacterProfile]]] # New field for options
    selected_detailed_character_profiles: Optional[List[DetailedCharacterProfile]] # New field for chosen detailed profiles
    saved_characters_db_model: Optional[List[Character]] # Renamed from 'characters'
    lore_keeper_initialized: bool
    current_chapter_number: int
    total_chapters_to_generate: int
    generated_chapters: List[Chapter]
    active_character_ids_for_chapter: Optional[List[int]]
    current_chapter_plot_summary: Optional[str]
    current_plot_focus_for_chronicler: Optional[str] # Added missing field
    chapter_brief: Optional[str]
    db_name: Optional[str] # Add db_name field
    current_chapter_review: Optional[Dict[str, Any]]
    current_chapter_quality_passed: Optional[bool]
    current_chapter_conflicts: Optional[List[Dict[str, Any]]]
    auto_decision_engine: Optional[AutoDecisionEngine] # New field
    knowledge_graph_data: Optional[Dict[str, Any]]
    # Chapter Retry Mechanism Fields
    current_chapter_retry_count: int
    max_chapter_retries: int
    current_chapter_original_content: Optional[str]
    current_chapter_feedback_for_retry: Optional[str]
    # API Interaction / Human-in-the-loop state
    workflow_status: Optional[str] # e.g., "running", "paused_for_outline_selection"
    pending_decision_type: Optional[str]
    pending_decision_options: Optional[List[Dict[str, Any]]] # Stores DecisionOption like dicts
    # Plot Twist State Fields
    available_plot_twist_options: Optional[List[PlotChapterDetail]]
    selected_plot_twist_option: Optional[PlotChapterDetail]
    chapter_number_for_twist: Optional[int]
    # Plot Branching State Fields
    available_plot_branch_options: Optional[List[List[PlotChapterDetail]]]
    selected_plot_branch_path: Optional[List[PlotChapterDetail]]
    chapter_number_for_branching: Optional[int]
    # Manual Chapter Review State Fields
    chapter_pending_manual_review_id: Optional[int] = None
    chapter_content_for_manual_review: Optional[str] = None
    chapter_review_feedback_for_manual_review: Optional[Dict[str, Any]] = None
    pending_decision_prompt: Optional[str]
    user_made_decision_payload: Optional[Dict[str, Any]] # Stores submitted choice
    original_chapter_content_for_conflict_review: Optional[str] # Stores chapter text before potential conflict resolution by human
    # 循环安全参数
    loop_iteration_count: int
    max_loop_iterations: int
    execution_count: int  # 新增：执行计数器防止无限循环

# --- Utility Functions ---
def _get_memory_usage() -> str:
    """获取当前内存使用情况"""
    if PSUTIL_AVAILABLE:
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            return f"{memory_mb:.1f}MB"
        except Exception:
            pass
    return "N/A"

def _log_memory_usage(context: str = ""):
    """记录内存使用情况"""
    memory_usage = _get_memory_usage()
    print(f"DEBUG: Memory usage {context}: {memory_usage}")

    # 如果内存使用超过阈值，强制垃圾回收
    if PSUTIL_AVAILABLE:
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            if memory_mb > 1000:  # 超过1GB时强制垃圾回收
                print(f"WARNING: High memory usage ({memory_mb:.1f}MB), forcing garbage collection")
                collected = gc.collect()
                print(f"DEBUG: Garbage collected {collected} objects")

                # 如果内存使用超过4GB，发出严重警告
                if memory_mb > 4000:
                    print(f"CRITICAL: Very high memory usage ({memory_mb:.1f}MB), system may be unstable")
        except Exception:
            pass

def _aggressive_memory_cleanup():
    """激进的内存清理"""
    try:
        import gc
        # 强制垃圾回收
        collected = gc.collect()
        print(f"DEBUG: Aggressive cleanup collected {collected} objects")

        # 清理未引用的循环
        gc.set_debug(gc.DEBUG_UNCOLLECTABLE)
        collected_cycles = gc.collect()
        print(f"DEBUG: Cleaned up {collected_cycles} reference cycles")

        return True
    except Exception as e:
        print(f"WARNING: Aggressive memory cleanup failed: {e}")
        return False

# --- Node Functions ---
def _log_and_update_history(current_history: List[str], message: str, error: bool = False) -> List[str]:
    # 限制历史记录长度以防止内存泄漏
    MAX_HISTORY_LENGTH = 100  # 只保留最近100条记录

    updated_history = current_history + [message]
    if error: print(f"Error: {message}")
    else: print(message)

    # 如果历史记录过长，只保留最近的记录
    if len(updated_history) > MAX_HISTORY_LENGTH:
        # 保留前10条（初始化信息）和最后90条（最近的操作）
        updated_history = updated_history[:10] + ["... (历史记录已截断) ..."] + updated_history[-(MAX_HISTORY_LENGTH-11):]
        print(f"DEBUG: History truncated to {len(updated_history)} entries to prevent memory leak")

    return updated_history

def execute_narrative_pathfinder_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    # 更新执行计数器
    execution_count = state.get("execution_count", 0) + 1
    print(f"DEBUG: execute_narrative_pathfinder_agent - execution_count: {execution_count}")

    history = _log_and_update_history(state.get("history", []), "Executing Node: Narrative Pathfinder Agent")
    try:
        user_input = state["user_input"]
        num_outlines_to_generate = 2
        history = _log_and_update_history(history, f"Calling NarrativePathfinderAgent for {num_outlines_to_generate} outlines for theme: '{user_input['theme']}'")
        agent = NarrativePathfinderAgent()
        all_outlines = agent.generate_outline(
            user_theme=user_input['theme'], style_preferences=user_input.get("style_preferences", "general fiction"),
            num_outlines=num_outlines_to_generate
        )
        if all_outlines:
            history = _log_and_update_history(history, f"Successfully generated {len(all_outlines)} outlines.")
            # 确保返回完整的状态更新，而不是部分更新
            result = dict(state)  # 复制当前状态
            result.update({
                "all_generated_outlines": all_outlines,
                "history": history,
                "error_message": None,
                "execution_count": execution_count
            })
            print(f"DEBUG: execute_narrative_pathfinder_agent - returning success with {len(all_outlines)} outlines")
            return result
        else:
            msg = "Narrative Pathfinder Agent returned no outlines."
            result = dict(state)
            result.update({
                "error_message": msg,
                "history": _log_and_update_history(history, msg, True),
                "execution_count": execution_count
            })
            return result
    except Exception as e:
        msg = f"Error in Narrative Pathfinder Agent node: {e}"
        result = dict(state)
        result.update({
            "error_message": msg,
            "history": _log_and_update_history(history, msg, True),
            "execution_count": execution_count
        })
        return result

def present_outlines_for_selection_cli(state: NovelWorkflowState) -> dict:
    execution_count = state.get("execution_count", 0) + 1
    print(f"DEBUG: present_outlines_for_selection_cli - execution_count: {execution_count}")

    history = _log_and_update_history(state.get("history", []), "Node: Present Outlines for Selection (CLI)")
    print("\n=== Outline Selection ===")
    all_outlines = state.get("all_generated_outlines")
    if not all_outlines:
        error_msg = "No outlines available for selection."
        result = dict(state)
        result.update({
            "error_message": error_msg,
            "history": _log_and_update_history(history, error_msg, True),
            "execution_count": execution_count
        })
        return result

    # 显示所有大纲选项
    for i, outline_text in enumerate(all_outlines):
        print(f"\n--- Outline {i + 1} ---\n{outline_text}\n--------------------")

    selected_index = 0
    # choice_int = 0 # No longer needed here due to new logic structure

    user_input_settings = state.get("user_input", {})
    auto_mode = user_input_settings.get("auto_mode", False)
    interaction_mode = user_input_settings.get("interaction_mode", "cli")
    auto_engine = state.get("auto_decision_engine")

    # API Interaction Mode (Human makes decision via API)
    if interaction_mode == "api" and not auto_mode:
        payload = state.get("user_made_decision_payload", {})
        # Check if resuming from an API decision specific to outline selection
        # The selected_option_id is set by resume_workflow and is 1-based.
        if payload.get("source_decision_type") == "outline_selection" and payload.get("selected_option_id") is not None:
            history = state.get("history", [])
            selected_id_str = payload.get("selected_option_id")

            try:
                # Convert 1-based selected_option_id to 0-based index
                selected_index = int(selected_id_str) - 1
            except ValueError:
                error_msg = f"API Mode: Invalid 'selected_option_id' format: '{selected_id_str}' for outline_selection. Must be an integer."
                state["error_message"] = error_msg
                state["history"] = _log_and_update_history(history, error_msg, True)
                return state # Error state will be caught by _check_node_output

            all_outlines_from_state = state.get("all_generated_outlines")
            if not all_outlines_from_state or not isinstance(all_outlines_from_state, list):
                error_msg = "API Mode: 'all_generated_outlines' not found or not a list in state for outline selection resume."
                state["error_message"] = error_msg
                state["history"] = _log_and_update_history(history, error_msg, True)
                return state

            if not (0 <= selected_index < len(all_outlines_from_state)):
                error_msg = f"API Mode: Invalid selected_index {selected_index} (from ID {selected_id_str}) for outlines (length {len(all_outlines_from_state)})."
                state["error_message"] = error_msg
                state["history"] = _log_and_update_history(history, error_msg, True)
                return state

            state["narrative_outline_text"] = all_outlines_from_state[selected_index]
            state["history"] = _log_and_update_history(history, f"API Human-Mode: Outline {selected_index + 1} ('{state['narrative_outline_text'][:50]}...') selected via API.")
            state["workflow_status"] = "running" # Generic running status
            state["user_made_decision_payload"] = None # Clear consumed decision
            # Pending decision fields are cleared in resume_workflow, so no need here if logic holds
            state["error_message"] = None
            # execution_count is already incremented at the start of the function
            return state
        else:
            # Pausing for API decision: options should be 0-indexed for API consistency
            options_for_api = [{"id": str(i), "text_summary": str(o)[:150]+"...", "full_data": str(o)} for i, o in enumerate(all_outlines)]
            state["pending_decision_type"] = "outline_selection"
            state["pending_decision_options"] = options_for_api
            state["pending_decision_prompt"] = "Please select a narrative outline for the novel."
            state["workflow_status"] = "paused_for_outline_selection"
            history = _log_and_update_history(history, "API Mode: Pausing for outline selection.")
            state["history"] = history # Ensure history is updated in state
            state["execution_count"] = execution_count

            # Persist state to DB before returning
            try:
                db_manager = DatabaseManager(db_name=state.get("db_name", "novel_mvp.db"))
                options_json = json.dumps(options_for_api)

                prepared_state_for_json = WorkflowManager._prepare_state_for_json_static(dict(state))
                state_json = json.dumps(prepared_state_for_json)

                db_manager.update_novel_pause_state(
                    state["novel_id"], state["workflow_status"], state["pending_decision_type"],
                    options_json, state["pending_decision_prompt"], state_json
                )
                history = _log_and_update_history(history, "Successfully saved paused state to DB.")
                state["history"] = history
            except Exception as db_e:
                error_msg = f"API Mode: Failed to save paused state to DB: {db_e}"
                history = _log_and_update_history(history, error_msg, True)
                state["history"] = history
                state["error_message"] = error_msg # This will stop the workflow via _check_node_output
                # Do not return yet, let it fall through to _check_workflow_pause_status which might be an error state

            return state # This state will be caught by _check_workflow_pause_status

    # Auto Mode (CLI or API)
    if auto_mode and auto_engine:
        print("Auto mode enabled: Making automatic outline selection.")
        # Ensure all_outlines is not empty before calling decide
        if not all_outlines: # This check was already there, just ensuring context
            error_msg = "No outlines available for automatic selection."
            # The existing error handling for empty all_outlines will be hit before this,
            # but as a safeguard if structure changes:
            result = dict(state)
            result.update({
                "error_message": error_msg,
                "history": _log_and_update_history(history, error_msg, True),
                "execution_count": execution_count
            })
            return result
        else:
            selected_outline_text = auto_engine.decide(all_outlines, context={"decision_type": "outline_selection"})
            # Find index for logging, assuming decide returns the item itself
            try:
                selected_index = all_outlines.index(selected_outline_text)
                log_msg = f"Auto mode: Selected Outline {selected_index + 1} via AutoDecisionEngine."
            except ValueError:
                # Should not happen if engine.decide returns an element from all_outlines
                selected_index = 0 # Fallback, though problematic
                selected_outline_text = all_outlines[selected_index] # Ensure selected_outline_text is set
                log_msg = f"Auto mode: Selected an outline via AutoDecisionEngine (index unknown, defaulted to 1)."
    elif auto_mode and not auto_engine: # Auto mode but no engine (e.g. API auto mode without engine fully setup)
        print("Auto mode enabled, but AutoDecisionEngine not found in state. Defaulting to Outline 1.")
        log_msg = "Auto mode (engine missing): Defaulting to Outline 1."
        selected_index = 0 # Default behavior
        selected_outline_text = all_outlines[selected_index]
    else: # CLI Human interaction mode
        try:
            import sys
            if not sys.stdin.isatty():
                print("Non-interactive environment detected: Automatically selecting Outline 1.")
                log_msg = "Non-interactive environment: Selected Outline 1."
                selected_index = 0
            else:
                choice_str = input(f"Please select an outline by number (1-{len(all_outlines)}) or type '0' to default to Outline 1: ")
                choice_int = int(choice_str) # choice_int defined here now
                if 0 < choice_int <= len(all_outlines):
                    selected_index = choice_int - 1
                    log_msg = f"User selected Outline {selected_index + 1}."
                else:
                    selected_index = 0 # Default to first if input is invalid
                    log_msg = f"Invalid input or '0', defaulted to Outline 1."
        except (ValueError, EOFError, KeyboardInterrupt) as e:
            print(f"Input error ({e}), defaulting to Outline 1.")
            log_msg = f"Input error ({type(e).__name__}), defaulting to Outline 1."
            selected_index = 0
        except Exception as e: # Catch any other unexpected errors during input
            print(f"Unexpected error during input ({e}), defaulting to Outline 1.")
            log_msg = f"Unexpected error during input, defaulting to Outline 1."
            selected_index = 0
        selected_outline_text = all_outlines[selected_index]

    history = _log_and_update_history(history, log_msg)
    # selected_outline_text is now set either by auto_engine or user/default
    print(f"Proceeding with Outline {selected_index + 1}.")

    # 确保返回完整的状态更新
    result = dict(state)
    result.update({
        "narrative_outline_text": selected_outline_text,
        "history": history,
        "error_message": None,
        "execution_count": execution_count
    })
    print(f"DEBUG: present_outlines_for_selection_cli - returning success with selected outline")
    return result

def persist_novel_record_node(state: NovelWorkflowState) -> Dict[str, Any]:
    execution_count = state.get("execution_count", 0) + 1
    print(f"DEBUG: persist_novel_record_node - execution_count: {execution_count}")

    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Novel Record")
    try:
        user_input = state["user_input"]
        db_manager = DatabaseManager(db_name=state.get("db_name", "novel_mvp.db"))
        new_novel_id = db_manager.add_novel(user_theme=user_input["theme"], style_preferences=user_input.get("style_preferences", ""))
        novel_data = db_manager.get_novel_by_id(new_novel_id)
        history = _log_and_update_history(history, f"Novel record saved to DB with ID: {new_novel_id}.")

        # 确保返回完整的状态更新
        result = dict(state)
        result.update({
            "novel_id": new_novel_id,
            "novel_data": novel_data,
            "history": history,
            "error_message": None,
            "execution_count": execution_count
        })
        print(f"DEBUG: persist_novel_record_node - returning success with novel_id: {new_novel_id}")
        return result
    except Exception as e:
        msg = f"Error in Persist Novel Record node: {e}"
        result = dict(state)
        result.update({
            "error_message": msg,
            "history": _log_and_update_history(history, msg, True),
            "execution_count": execution_count
        })
        return result

def persist_initial_outline_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Initial Outline")
    try:
        novel_id = state["novel_id"]
        outline_text_to_persist = state["narrative_outline_text"]
        if novel_id is None or outline_text_to_persist is None:
            msg = "Novel ID or selected outline text ('narrative_outline_text') missing for outline persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        db_manager = DatabaseManager(db_name=state.get("db_name", "novel_mvp.db"))
        new_outline_id = db_manager.add_outline(novel_id=novel_id, overview_text=outline_text_to_persist)
        db_manager.update_novel_active_outline(novel_id, new_outline_id)
        outline_data = db_manager.get_outline_by_id(new_outline_id)
        history = _log_and_update_history(history, f"Initial (selected) outline saved with ID {new_outline_id} and linked to novel {novel_id}.")
        return {"outline_id": new_outline_id, "outline_data": outline_data, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Initial Outline node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_outline_quality_guardian(state: NovelWorkflowState) -> dict:
    history = _log_and_update_history(state.get("history", []), "Node: Execute Outline Quality Guardian")
    print("Executing Node: Outline Quality Guardian")
    selected_outline_text = state.get("narrative_outline_text")
    if not selected_outline_text:
        error_msg = "No selected outline available for review by Quality Guardian."
        history = _log_and_update_history(history, f"Error: {error_msg}")
        return {"history": history, "error_message": None, "outline_review": None}
    try:
        guardian_agent = QualityGuardianAgent()
        review = guardian_agent.review_outline(selected_outline_text)
        history = _log_and_update_history(history, "Outline review completed by Quality Guardian.")
        print("\n--- Outline Review by Quality Guardian ---")
        if review:
            for key, value in review.items(): print(f"  {key.replace('_', ' ').capitalize()}: {value}")
        else: print("  Quality Guardian Agent did not return a review.")
        print("----------------------------------------\n")
        return {"outline_review": review, "history": history, "error_message": None}
    except Exception as e:
        error_msg = f"Error during Quality Guardian outline review: {e}"
        history = _log_and_update_history(history, error_msg, True)
        print(f"Error in Outline Quality Guardian node: {e}")
        return {"history": history, "error_message": state.get("error_message"), "outline_review": None}

def execute_world_weaver_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: World Weaver Agent")
    try:
        outline_text_for_worldview = state["narrative_outline_text"]
        user_theme = state["user_input"]["theme"]  # Get user theme for consistency
        if not outline_text_for_worldview:
            msg = "Selected narrative outline text is required for World Weaver Agent."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        num_worldviews_to_generate = 2
        history = _log_and_update_history(history, f"Calling WorldWeaverAgent for {num_worldviews_to_generate} worldviews based on theme: '{user_theme}' and outline: '{outline_text_for_worldview[:50]}...'")
        agent = WorldWeaverAgent()
        # Note: WorldWeaverAgent currently only accepts narrative_outline and num_worldviews
        # The user theme is already incorporated into the selected narrative outline
        all_worldviews = agent.generate_worldview(
            narrative_outline=outline_text_for_worldview,
            num_worldviews=num_worldviews_to_generate
        )
        if all_worldviews:
            history = _log_and_update_history(history, f"Successfully generated {len(all_worldviews)} worldviews.")
            return {"all_generated_worldviews": all_worldviews, "history": history, "error_message": None}
        else:
            msg = "World Weaver Agent returned no worldviews."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in World Weaver Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def present_worldviews_for_selection_cli(state: NovelWorkflowState) -> dict:
    history = _log_and_update_history(state.get("history", []), "Node: Present Worldviews for Selection (CLI)")
    print("\n=== Worldview Selection ===")
    all_worldviews = state.get("all_generated_worldviews")
    if not all_worldviews:
        error_msg = "No worldviews available for selection."
        return {"error_message": error_msg, "history": _log_and_update_history(history, error_msg, True)}

    # 显示所有世界观选项
    for i, wv_detail in enumerate(all_worldviews):
        print(f"\n--- Worldview Option {i + 1} ---")
        print(f"  Name: {wv_detail.get('world_name', 'N/A')}")
        print(f"  Core Concept: {wv_detail.get('core_concept', 'N/A')}")
        print(f"  Key Elements: {', '.join(wv_detail.get('key_elements') or [])}")
        print(f"  Atmosphere: {wv_detail.get('atmosphere', 'N/A')}")
        print("--------------------")

    selected_index = 0
    # choice_int = 0 # No longer needed here

    user_input_settings = state.get("user_input", {})
    auto_mode = user_input_settings.get("auto_mode", False)
    interaction_mode = user_input_settings.get("interaction_mode", "cli")
    auto_engine = state.get("auto_decision_engine")

    # API Interaction Mode (Human makes decision via API)
    if interaction_mode == "api" and not auto_mode:
        payload = state.get("user_made_decision_payload", {})
        # Check if resuming from an API decision specific to worldview selection
        # The selected_option_id is set by resume_workflow and is 1-based.
        if payload.get("source_decision_type") == "worldview_selection" and payload.get("selected_option_id") is not None:
            history = state.get("history", []) # Get current history
            selected_id_str = payload.get("selected_option_id")

            try:
                # Convert 1-based selected_option_id to 0-based index
                selected_index = int(selected_id_str) - 1
            except ValueError:
                error_msg = f"API Mode: Invalid 'selected_option_id' format: '{selected_id_str}' for worldview_selection. Must be an integer."
                state["error_message"] = error_msg
                state["history"] = _log_and_update_history(history, error_msg, True)
                return state # Error state will be caught by _check_node_output

            all_worldviews_from_state = state.get("all_generated_worldviews") # Renamed to avoid conflict
            if not all_worldviews_from_state or not isinstance(all_worldviews_from_state, list):
                error_msg = "API Mode: 'all_generated_worldviews' not found or not a list in state for worldview selection resume."
                state["error_message"] = error_msg
                state["history"] = _log_and_update_history(history, error_msg, True)
                return state

            if not (0 <= selected_index < len(all_worldviews_from_state)):
                error_msg = f"API Mode: Invalid selected_index {selected_index} (from ID {selected_id_str}) for worldviews (length {len(all_worldviews_from_state)})."
                state["error_message"] = error_msg
                state["history"] = _log_and_update_history(history, error_msg, True)
                return state

            state["selected_worldview_detail"] = all_worldviews_from_state[selected_index]
            wv_name = state["selected_worldview_detail"].get('world_name', f'Option {selected_index + 1}')
            state["history"] = _log_and_update_history(history, f"API Human-Mode: Worldview '{wv_name}' selected via API.")
            state["workflow_status"] = "running" # Generic running status
            state["user_made_decision_payload"] = None # Clear consumed decision
            state["error_message"] = None
            return state
        else:
            # Pausing for API decision: options should be 0-indexed for API consistency
            options_for_api = [{"id": str(i), "text_summary": wv.get('world_name', f'Worldview {i+1}') + ": " + wv.get('core_concept', '')[:100]+"...", "full_data": wv} for i, wv in enumerate(all_worldviews)]
            state["pending_decision_type"] = "worldview_selection"
            state["pending_decision_options"] = options_for_api
            state["pending_decision_prompt"] = "Please select a worldview for the novel."
            state["workflow_status"] = "paused_for_worldview_selection"
            history = _log_and_update_history(history, "API Mode: Pausing for worldview selection.")
            state["history"] = history # Ensure history is updated in state

            # Persist state to DB
            try:
                db_manager = DatabaseManager(db_name=state.get("db_name", "novel_mvp.db"))
                options_json = json.dumps(options_for_api)

                prepared_state_for_json = WorkflowManager._prepare_state_for_json_static(dict(state))
                state_json = json.dumps(prepared_state_for_json)

                db_manager.update_novel_pause_state(
                    state["novel_id"], state["workflow_status"], state["pending_decision_type"],
                    options_json, state["pending_decision_prompt"], state_json
                )
                history = _log_and_update_history(history, "Successfully saved paused worldview selection state to DB.")
                state["history"] = history
            except Exception as db_e:
                error_msg = f"API Mode: Failed to save paused worldview state to DB: {db_e}"
                history = _log_and_update_history(history, error_msg, True)
                state["history"] = history
                state["error_message"] = error_msg

            return state # This state will be caught by _check_workflow_pause_status

    # Auto Mode (CLI or API)
    if auto_mode and auto_engine:
        print("Auto mode enabled: Making automatic worldview selection.")
        if not all_worldviews: # This check was already there
            error_msg = "No worldviews available for automatic selection."
            # Error handling for empty all_worldviews is already present and will be hit first.
            # This is a safeguard:
            return {"error_message": error_msg, "history": _log_and_update_history(history, error_msg, True)}
        else:
            selected_wv_detail = auto_engine.decide(all_worldviews, context={"decision_type": "worldview_selection"})
            try:
                selected_index = all_worldviews.index(selected_wv_detail)
                log_msg = f"Auto mode: Selected Worldview {selected_index + 1} ('{selected_wv_detail.get('world_name', 'N/A')}') via AutoDecisionEngine."
            except ValueError:
                selected_index = 0 # Fallback
                selected_wv_detail = all_worldviews[selected_index] # Ensure selected_wv_detail is set
                log_msg = f"Auto mode: Selected a worldview via AutoDecisionEngine (index unknown, defaulted to 1)."
    elif auto_mode and not auto_engine: # Auto mode but no engine
        print("Auto mode enabled, but AutoDecisionEngine not found in state. Defaulting to Worldview 1.")
        log_msg = "Auto mode (engine missing): Defaulting to Worldview 1."
        selected_index = 0
        selected_wv_detail = all_worldviews[selected_index]
    else: # CLI Human interaction mode
        try:
            import sys
            if not sys.stdin.isatty():
                print("Non-interactive environment detected: Automatically selecting Worldview 1.")
                log_msg = "Non-interactive environment: Selected Worldview 1."
                selected_index = 0
            else:
                choice_str = input(f"Please select a worldview by number (1-{len(all_worldviews)}) or type '0' to default to Option 1: ")
                choice_int = int(choice_str) # choice_int defined here
                if 0 < choice_int <= len(all_worldviews):
                    selected_index = choice_int - 1
                    log_msg = f"User selected Worldview {selected_index + 1}."
                else:
                    selected_index = 0
                    log_msg = f"Invalid input or '0', defaulted to Worldview 1."
        except (ValueError, EOFError, KeyboardInterrupt) as e:
            print(f"Input error ({e}), defaulting to Worldview 1.")
            log_msg = f"Input error ({type(e).__name__}), defaulting to Worldview 1."
            selected_index = 0
        except Exception as e: # Catch any other unexpected errors during input
            print(f"Unexpected error during input ({e}), defaulting to Worldview 1.")
            log_msg = f"Unexpected error during input, defaulting to Worldview 1."
            selected_index = 0
        selected_wv_detail = all_worldviews[selected_index]

    history = _log_and_update_history(history, log_msg)
    # selected_wv_detail is now set
    print(f"Proceeding with Worldview {selected_index + 1} ('{selected_wv_detail.get('world_name', 'N/A')}')")
    return {"selected_worldview_detail": selected_wv_detail, "history": history, "error_message": None}

def persist_worldview_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Worldview")
    try:
        novel_id = state["novel_id"]
        selected_wv_detail = state.get("selected_worldview_detail")
        if novel_id is None or selected_wv_detail is None:
            msg = "Novel ID or selected worldview detail missing for worldview persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        description_to_save = selected_wv_detail.get('core_concept', 'Worldview description not available.')
        if not description_to_save and selected_wv_detail.get('raw_llm_output_for_worldview'):
            description_to_save = "Raw: " + selected_wv_detail['raw_llm_output_for_worldview']
        db_manager = DatabaseManager(db_name=state.get("db_name", "novel_mvp.db"))
        new_worldview_id = db_manager.add_worldview(novel_id=novel_id, description_text=description_to_save)
        db_manager.update_novel_active_worldview(novel_id, new_worldview_id)
        worldview_data_from_db = db_manager.get_worldview_by_id(new_worldview_id)
        history = _log_and_update_history(history, f"Selected worldview (concept: '{description_to_save[:50]}...') saved with ID {new_worldview_id} and linked to novel {novel_id}.")
        return {"worldview_id": new_worldview_id, "worldview_data": worldview_data_from_db, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Worldview node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_plot_architect_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Plot Architect Agent")
    try:
        outline_text_for_plot = state["narrative_outline_text"]
        selected_worldview = state.get("selected_worldview_detail")
        if not outline_text_for_plot or not selected_worldview:
            msg = "Selected outline text or selected worldview detail is required for Plot Architect Agent."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        worldview_text_for_plot = selected_worldview.get('core_concept', '')
        if not worldview_text_for_plot and selected_worldview.get('raw_llm_output_for_worldview'):
            worldview_text_for_plot = selected_worldview['raw_llm_output_for_worldview']
        # 优先使用用户输入的章节数
        user_input = state.get("user_input", {})
        num_chapters_for_plot = user_input.get("chapters", 0) if user_input else 0

        # 如果用户输入中没有章节数，尝试从state中获取（向后兼容）
        if num_chapters_for_plot == 0:
            num_chapters_for_plot = state.get("total_chapters_to_generate", 3)

        history = _log_and_update_history(history, f"Calling PlotArchitectAgent for {num_chapters_for_plot} detailed chapter structures.")
        agent = PlotArchitectAgent()
        detailed_plot_data_list = agent.generate_plot_points(
            narrative_outline=outline_text_for_plot, worldview_data=worldview_text_for_plot, num_chapters=num_chapters_for_plot
        )
        if detailed_plot_data_list:
            history = _log_and_update_history(history, f"PlotArchitectAgent generated {len(detailed_plot_data_list)} detailed chapter plots.")
            return {"detailed_plot_data": detailed_plot_data_list, "history": history, "error_message": None}
        else:
            msg = "Plot Architect Agent returned no detailed chapter plots."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Plot Architect Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def persist_plot_node(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Persist Plot")
    try:
        novel_id = state["novel_id"]
        detailed_plot = state.get("detailed_plot_data")
        if novel_id is None or not detailed_plot:
            msg = "Novel ID or detailed plot data missing for plot persistence."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        db_manager = DatabaseManager(db_name=state.get("db_name", "novel_mvp.db"))
        plot_summary_json = json.dumps(detailed_plot, ensure_ascii=False, indent=2)
        new_plot_id = db_manager.add_plot(novel_id=novel_id, plot_summary=plot_summary_json)
        db_manager.update_novel_active_plot(novel_id, new_plot_id)
        plot_data_from_db = db_manager.get_plot_by_id(new_plot_id)
        history = _log_and_update_history(history, f"Detailed plot (as JSON) saved with ID {new_plot_id} and linked to novel {novel_id}.")
        return {"plot_id": new_plot_id, "plot_data": plot_data_from_db, "history": history, "error_message": None}
    except Exception as e:
        msg = f"Error in Persist Plot node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_character_sculptor_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Character Sculptor Agent")
    try:
        novel_id = state["novel_id"]
        outline = state["outline_data"]
        selected_worldview = state.get("selected_worldview_detail")
        detailed_plot = state.get("detailed_plot_data")
        if not all([novel_id, outline, selected_worldview, detailed_plot]):
            msg = "Novel ID, outline data, selected worldview detail, or detailed plot data missing for Character Sculptor."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        worldview_text_for_chars = selected_worldview.get('core_concept', "General worldview.")
        plot_summary_for_chars = "; ".join(
            [f"Ch{d.get('chapter_number')}: {d.get('key_events_and_plot_progression', d.get('core_scene_summary', ''))}" for d in detailed_plot]
        )
        if not plot_summary_for_chars: plot_summary_for_chars = "Overall plot not yet detailed."
        # For MVP, let's define concepts here or pass them in user_input.
        character_concepts = ["the main protagonist", "a compelling antagonist"] # Example concepts
        history = _log_and_update_history(history, f"Generating characters for concepts: {character_concepts}")
        agent = CharacterSculptorAgent(db_name=state.get("db_name", "novel_mvp.db"))
        # CharacterSculptorAgent.generate_character_profile_options returns Dict[str, List[DetailedCharacterProfile]]
        # This node should now store these options. Selection will be a new node.
        # For now, let's assume this node's purpose is to generate options.
        # The actual saving will happen after a selection step.
        # This change means 'character_sculptor' node might need a subsequent 'select_characters' node.
        # For this sub-task, we just update the state fields.
        # The agent.generate_character_profile_options does not take novel_id.
        character_profile_options = agent.generate_character_profile_options(
            narrative_outline=outline['overview_text'],
            worldview_data_core_concept=worldview_text_for_chars,
            plot_summary_str=plot_summary_for_chars,
            character_concepts=character_concepts
            # num_options_per_concept can be passed if not default
        )
        if character_profile_options:
            history = _log_and_update_history(history, f"Generated {sum(len(opts) for opts in character_profile_options.values())} character profile options for {len(character_concepts)} concepts.")
            # Store all generated options in the new state field
            return {"all_generated_character_options": character_profile_options, "history": history, "error_message": None}
        else:
            msg = "Character Sculptor Agent failed to generate character options."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Character Sculptor Agent node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_lore_keeper_initialize(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Lore Keeper Initialize")
    try:
        novel_id = state["novel_id"]
        outline = state["outline_data"]
        worldview_db_object = state["worldview_data"]
        plot_db_object = state.get("plot_data")
        if not plot_db_object and state.get("plot_id"):
            db_manager = DatabaseManager(db_name=state.get("db_name", "novel_mvp.db"))
            plot_db_object = db_manager.get_plot_by_id(state["plot_id"])

        # LoreKeeperAgent's initialize_knowledge_base expects List[Character] (the DB model).
        # It should now use `selected_detailed_character_profiles` if available,
        # or `saved_characters_db_model` if detailed profiles are not the primary source for KB init.
        # For now, let's assume KB initialization might happen *after* characters are selected and saved.
        # If character selection is a separate step, this node might need to be re-ordered or
        # use `selected_detailed_character_profiles`.
    # LoreKeeperAgent's initialize_knowledge_base expects List[Character] (the DB model).
    # It should now use `selected_detailed_character_profiles` if available,
    # or `saved_characters_db_model` if detailed profiles are not the primary source for KB init.
    # For this sub-task, we'll use `selected_detailed_character_profiles`.
    # Note: `initialize_knowledge_base` in LoreKeeperAgent might need adjustment
    # if it strictly expects List[Character] and not List[DetailedCharacterProfile].
    # For now, we pass List[DetailedCharacterProfile], assuming it can handle it or will be adapted.
    character_details_for_kb = state.get("selected_detailed_character_profiles")


    # Allow KB initialization even if characters are not yet selected/available.
    if character_details_for_kb is None:
        history = _log_and_update_history(history, "Selected character profiles not yet available for Lore Keeper initialization. Initializing KB with other data.")
        character_details_for_kb = [] # Pass empty list if not available

    if not all([novel_id, outline, worldview_db_object, plot_db_object]):
        msg = "Missing critical data (novel_id, outline, worldview, or plot) for Lore Keeper initialization."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        try:
            lore_keeper = LoreKeeperAgent(db_name=state.get("db_name", "novel_mvp.db"))
            # TODO: Adapt LoreKeeperAgent to handle List[DetailedCharacterProfile] if its initialize_knowledge_base expects List[Character]
            # For now, assuming it can work with the richer structure or a transformation happens inside.
            # If initialize_knowledge_base strictly needs List[Character], we'd convert here:
            # temp_characters_for_kb = [Character(id=dp['character_id'], novel_id=dp['novel_id'], name=dp['name'], description="See detailed profile.", role_in_story=dp['role_in_story'], creation_date=dp['creation_date']) for dp in character_details_for_kb]
            # lore_keeper.initialize_knowledge_base(novel_id, outline, worldview_db_object, plot_db_object, temp_characters_for_kb)

            # Assuming LoreKeeperAgent.initialize_knowledge_base is adapted to use DetailedCharacterProfile
            # or extracts necessary info from it. This might require changes in LoreKeeperAgent.
            # For now, we'll pass the detailed profiles.
            lore_keeper.initialize_knowledge_base(novel_id, outline, worldview_db_object, plot_db_object, character_details_for_kb) # type: ignore

            history = _log_and_update_history(history, "Lore Keeper knowledge base initialized.")
            # 缓存 LoreKeeperAgent 实例以避免重复创建
            return {"lore_keeper_initialized": True, "lore_keeper_instance": lore_keeper, "history": history, "error_message": None}
        except Exception as lore_error:
            # 检查是否是ChromaDB相关错误
            error_str = str(lore_error)
            if "collections.topic" in error_str or "no such column" in error_str:
                warning_msg = f"Warning: Lore Keeper initialization failed (ChromaDB schema issue: {lore_error}), continuing without knowledge base."
                print(f"WARNING: ChromaDB schema issue detected. You may need to run 'python fix_chromadb_issues.py'")
            else:
                warning_msg = f"Warning: Lore Keeper initialization failed ({lore_error}), continuing without knowledge base."

            print(f"WARNING: {warning_msg}")
            history = _log_and_update_history(history, warning_msg)
            return {"lore_keeper_initialized": False, "history": history, "error_message": None}  # 不设置error_message，允许继续
    except Exception as e:
        msg = f"Error in Lore Keeper Initialize node: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True), "lore_keeper_initialized": False}

def prepare_for_chapter_loop(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Prepare for Chapter Loop")
    detailed_plot = state.get("detailed_plot_data")
    if not detailed_plot:
        msg = "Detailed plot data not found, cannot determine total chapters for loop."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

    # 优先使用用户输入的章节数，而不是detailed_plot的长度
    user_input = state.get("user_input", {})
    user_requested_chapters = user_input.get("chapters", 0) if user_input else 0

    # 如果用户输入中没有章节数，尝试从state中获取（向后兼容）
    if user_requested_chapters == 0:
        user_requested_chapters = state.get("total_chapters_to_generate", 0)

    plot_chapters_count = len(detailed_plot)

    if plot_chapters_count == 0:
        # If plot data is empty, this is an error condition - don't default to 3
        msg = "Detailed plot data list is empty. Cannot proceed with chapter generation."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

    # 验证用户输入与plot数据的一致性
    if user_requested_chapters > 0:
        # 使用用户输入的章节数
        total_chapters = user_requested_chapters
        if plot_chapters_count != user_requested_chapters:
            warning_msg = f"Warning: User requested {user_requested_chapters} chapters, but plot contains {plot_chapters_count} chapters. Using user input ({user_requested_chapters})."
            print(f"WARNING: {warning_msg}")
            history = _log_and_update_history(history, warning_msg)

            # 如果plot章节数少于用户要求，这可能是个问题
            if plot_chapters_count < user_requested_chapters:
                msg = f"Error: Plot only contains {plot_chapters_count} chapters, but user requested {user_requested_chapters}. Cannot generate more chapters than plot provides."
                return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    else:
        # 如果用户输入缺失，使用plot数据的长度
        total_chapters = plot_chapters_count
        warning_msg = f"Warning: No user chapter count found, using plot data length ({plot_chapters_count})."
        print(f"WARNING: {warning_msg}")
        history = _log_and_update_history(history, warning_msg)

    history = _log_and_update_history(history, f"Preparing for chapter loop. Total chapters to generate: {total_chapters}")
    print(f"DEBUG: prepare_for_chapter_loop - User requested: {user_requested_chapters}, Plot contains: {plot_chapters_count}, Final decision: {total_chapters}")

    return {
        "current_chapter_number": 1,
        "generated_chapters": [],
        "total_chapters_to_generate": total_chapters,
        "history": history,
        "error_message": None
    }

def execute_context_synthesizer_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state['current_chapter_number']
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Context Synthesizer for Chapter {current_chapter_num}")
    try:
        novel_id = state["novel_id"]
        detailed_plot = state.get("detailed_plot_data")
        # Use selected_detailed_character_profiles for context
        character_profiles = state.get("selected_detailed_character_profiles", [])

        if not all([novel_id is not None, detailed_plot]): # Characters can be empty list
            msg = "Missing data for Context Synthesizer (novel_id, detailed_plot_data)."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
        if not (0 < current_chapter_num <= len(detailed_plot)):
            msg = f"Invalid current_chapter_number {current_chapter_num} for {len(detailed_plot)} detailed plot entries."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        current_chapter_detail: PlotChapterDetail = detailed_plot[current_chapter_num - 1]
        brief_plot_summary = current_chapter_detail.get('key_events_and_plot_progression') or \
                             current_chapter_detail.get('core_scene_summary') or \
                             f"Plot for Chapter {current_chapter_num} needs to be developed based on title: {current_chapter_detail.get('title', 'N/A')}."

        # Pass IDs of characters present in the current chapter's plot details, if available
        # Otherwise, default to first few characters from the main list.
        active_char_names_from_plot = current_chapter_detail.get("characters_present", [])
        active_char_ids: List[int] = []
        if active_char_names_from_plot:
            for char_prof in character_profiles:
                if char_prof.get("name") in active_char_names_from_plot:
                    if char_prof.get("character_id") is not None:
                         active_char_ids.append(char_prof["character_id"]) # type: ignore
        else: # Fallback if not specified in plot
            active_char_ids = [cp.get('character_id') for cp in character_profiles[:2] if cp.get('character_id') is not None] # type: ignore

        try:
            context_agent = ContextSynthesizerAgent(db_name=state.get("db_name", "novel_mvp.db"))
            chapter_brief_text = context_agent.generate_chapter_brief(
                novel_id, current_chapter_num, brief_plot_summary, active_char_ids
            )

            # Check for retry and append feedback if necessary
            # current_chapter_retry_count will be > 0 if _should_retry_chapter decided to retry and incremented it.
            # The value of current_chapter_retry_count is the number of the *current* attempt (e.g., 1 for the first retry)
            if state.get("current_chapter_retry_count", 0) > 0:
                feedback_for_retry = state.get("current_chapter_feedback_for_retry")
                if feedback_for_retry:
                    retry_message = (
                        f"\n\n--- IMPORTANT: THIS IS A RETRY ATTEMPT (Attempt {state['current_chapter_retry_count']} of {state['max_chapter_retries']}) ---\n"
                        f"Feedback from the previous attempt's quality review:\n"
                        f"{feedback_for_retry}\n"
                        f"Please carefully review this feedback and address all points in this new version of the chapter.\n"
                        f"--- END OF RETRY FEEDBACK ---\n"
                    )
                    chapter_brief_text += retry_message
                    history = _log_and_update_history(history, f"Appended retry feedback to chapter brief for Chapter {current_chapter_num}.")
                    print(f"INFO: Appended retry feedback to brief for Chapter {current_chapter_num}, This is Retry Attempt: {state['current_chapter_retry_count']}")

            history = _log_and_update_history(history, f"Chapter brief generated for Chapter {current_chapter_num}.")
            # Storing the specific plot focus for the chronicler separately as requested by subtask.
            return {
                "chapter_brief": chapter_brief_text,
                "current_plot_focus_for_chronicler": brief_plot_summary, # Changed key name
                "history": history, "error_message": None
            }
        except Exception as context_error:
            # 检查是否是ChromaDB相关错误
            error_str = str(context_error)
            if "collections.topic" in error_str or "no such column" in error_str:
                warning_msg = f"Warning: Context Synthesizer failed due to ChromaDB schema issue, generating basic brief without RAG context."
                print(f"WARNING: ChromaDB schema issue detected in Context Synthesizer. You may need to run 'python fix_chromadb_issues.py'")
                history = _log_and_update_history(history, warning_msg)

                # 生成基本的章节简介，不使用RAG上下文
                basic_brief = f"""**Chapter {current_chapter_num} Brief (Basic Mode - No RAG Context)**

**Specific Plot Focus for THIS Chapter ({current_chapter_num}):**
{brief_plot_summary}

**Note:** This brief was generated without RAG context due to knowledge base issues.
The chapter will be generated based on the plot summary and character information only.
"""
                return {
                    "chapter_brief": basic_brief,
                    "current_plot_focus_for_chronicler": brief_plot_summary,
                    "history": history, "error_message": None
                }
            else:
                # 其他错误，重新抛出
                raise context_error

    except Exception as e:
        msg = f"Error in Context Synthesizer node for Chapter {current_chapter_num}: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_chapter_chronicler_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state['current_chapter_number']
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Chapter Chronicler for Chapter {current_chapter_num}")
    try:
        novel_id = state["novel_id"]
        chapter_brief_text = state["chapter_brief"] # Renamed for clarity from 'chapter_brief'
        plot_focus_for_chapter = state["current_plot_focus_for_chronicler"] # Using new key
        style_prefs = state["user_input"].get("style_preferences", "general fiction")

        if not all([novel_id is not None, chapter_brief_text, plot_focus_for_chapter]):
            msg = "Missing data for Chapter Chronicler (novel_id, chapter_brief, or plot_focus_for_chapter)."
            history_log = _log_and_update_history(history, msg, True) # Ensure history is updated
            return {"error_message": msg, "history": history_log}

        # Print the full brief for RAG context visibility
        if chapter_brief_text:
            print(f"--- Chapter {current_chapter_num} - Brief for ChroniclerAgent ---")
            print(chapter_brief_text) # This will include the RAG context section
            print(f"--- End of Brief for Chapter {current_chapter_num} ---")
        else:
            # This case should ideally be caught by the check above, but as a safeguard:
            error_msg = f"Chapter {current_chapter_num} brief is missing."
            history_log = _log_and_update_history(history, error_msg, True)
            print(f"Error: {error_msg}")
            return {
                "history": history_log,
                "error_message": state.get("error_message") or error_msg
            }

        # Get words per chapter from user input
        words_per_chapter = state["user_input"].get("words_per_chapter", 1000)

        chronicler_agent = ChapterChroniclerAgent(db_name=state.get("db_name", "novel_mvp.db"))
        new_chapter = chronicler_agent.generate_and_save_chapter(
            novel_id, current_chapter_num, chapter_brief_text, plot_focus_for_chapter, style_prefs, words_per_chapter
        )
        if new_chapter:
            updated_generated_chapters = state.get("generated_chapters", []) + [new_chapter]
            history = _log_and_update_history(history, f"Chapter {current_chapter_num} generated and saved.")
            return {"generated_chapters": updated_generated_chapters, "history": history, "error_message": None}
        else:
            msg = f"Chapter Chronicler failed to generate Chapter {current_chapter_num}."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}
    except Exception as e:
        msg = f"Error in Chapter Chronicler node for Chapter {current_chapter_num}: {e}"
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

def execute_lore_keeper_update_kb(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state['current_chapter_number']
    print(f"DEBUG: execute_lore_keeper_update_kb - Starting for Chapter {current_chapter_num}")
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Lore Keeper Update KB for Chapter {current_chapter_num}")

    # 检查知识库是否已初始化
    if not state.get("lore_keeper_initialized", False):
        warning_msg = f"Lore Keeper not initialized, skipping KB update for Chapter {current_chapter_num}."
        print(f"WARNING: {warning_msg}")
        history = _log_and_update_history(history, warning_msg)
        print(f"DEBUG: execute_lore_keeper_update_kb - Completed (skipped) for Chapter {current_chapter_num}")
        return {"history": history, "error_message": None}  # 继续工作流程

    try:
        novel_id = state["novel_id"]
        generated_chapters = state.get("generated_chapters", [])
        if novel_id is None or not generated_chapters:
            msg = "Novel ID or generated chapters missing for Lore Keeper KB update."
            return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

        last_chapter = generated_chapters[-1]

        try:
            # 优先使用缓存的 LoreKeeperAgent 实例
            lore_keeper = state.get("lore_keeper_instance")
            if lore_keeper is None:
                # 如果缓存中没有实例，创建新的（但这不应该发生）
                print("WARNING: No cached LoreKeeperAgent instance found, creating new one")
                lore_keeper = LoreKeeperAgent(db_name=state.get("db_name", "novel_mvp.db"))

            lore_keeper.update_knowledge_base_with_chapter(novel_id, last_chapter)
            history = _log_and_update_history(history, f"Lore Keeper KB updated with Chapter {last_chapter['chapter_number']}.")
            print(f"DEBUG: execute_lore_keeper_update_kb - Successfully completed for Chapter {current_chapter_num}")

            # 强制清理向量存储缓存以释放内存
            if hasattr(lore_keeper, 'kb_manager') and hasattr(lore_keeper.kb_manager, 'cleanup_resources'):
                try:
                    lore_keeper.kb_manager.cleanup_resources()
                    print(f"DEBUG: execute_lore_keeper_update_kb - Cleaned up KB manager resources")
                except Exception as cleanup_error:
                    print(f"WARNING: Failed to cleanup KB manager resources: {cleanup_error}")

            # 清理向量存储缓存
            if hasattr(lore_keeper, 'kb_manager') and hasattr(lore_keeper.kb_manager, '_vector_store_cache'):
                try:
                    lore_keeper.kb_manager._vector_store_cache.clear()
                    print(f"DEBUG: execute_lore_keeper_update_kb - Cleared vector store cache")
                except Exception as cache_error:
                    print(f"WARNING: Failed to clear vector store cache: {cache_error}")

            # 强制垃圾回收
            import gc
            collected = gc.collect()
            print(f"DEBUG: execute_lore_keeper_update_kb - Garbage collected {collected} objects")
            _log_memory_usage("after lore_keeper_update_kb cleanup")

            print(f"DEBUG: execute_lore_keeper_update_kb - About to return result")
            # Clear retry-specific fields after successful KB update (or attempted update)
            # This is the primary place these fields are cleared after a chapter's processing is complete.
            updates_for_return = {
                "history": history,
                "error_message": None,
                "current_chapter_original_content": None,
                "current_chapter_feedback_for_retry": None
            }
            print(f"DEBUG: execute_lore_keeper_update_kb - Returning: {list(updates_for_return.keys())}")
            return updates_for_return
        except Exception as kb_error:
            # 如果知识库更新失败，记录警告但继续工作流程
            warning_msg = f"Warning: Failed to update knowledge base for Chapter {current_chapter_num} ({kb_error}), continuing workflow."
            print(f"WARNING: {warning_msg}")
            history = _log_and_update_history(history, warning_msg)
            # Still clear retry-specific fields even if KB update fails, as we are moving on from this chapter attempt.
            return {
                "history": history,
                "error_message": None, # 不设置error_message，允许继续
                "current_chapter_original_content": None,
                "current_chapter_feedback_for_retry": None
            }

    except Exception as e:
        msg = f"Error in Lore Keeper Update KB node for Chapter {current_chapter_num}: {e}"
        # Also clear retry fields in case of other errors in this node before returning,
        # as the chapter processing for this attempt is concluding.
        # Ensure the full state is returned, not just a partial dict.
        current_state_dict = dict(state)
        current_state_dict.update({
            "error_message": msg,
            "history": _log_and_update_history(history, msg, True),
            "current_chapter_original_content": None,
            "current_chapter_feedback_for_retry": None
        })
        return current_state_dict

def increment_chapter_number(state: NovelWorkflowState) -> Dict[str, Any]:
    # 记录内存使用情况
    _log_memory_usage("before increment_chapter_number")

    current_num = state.get("current_chapter_number", 0)
    total_chapters = state.get("total_chapters_to_generate", 0)
    generated_chapters = state.get("generated_chapters", [])

    # 增加循环计数器以防止无限循环
    current_iterations = state.get("loop_iteration_count", 0)
    new_iterations = current_iterations + 1

    print(f"DEBUG: increment_chapter_number - current: {current_num}")
    print(f"DEBUG: increment_chapter_number - iterations: {current_iterations} -> {new_iterations}")
    print(f"DEBUG: increment_chapter_number - progress: {len(generated_chapters)}/{total_chapters} chapters")

    # 关键修复：在递增章节号之前检查是否已经完成所有章节
    if len(generated_chapters) >= total_chapters:
        print(f"DEBUG: increment_chapter_number - All chapters completed ({len(generated_chapters)}/{total_chapters}), NOT incrementing chapter number")
        history = _log_and_update_history(state.get("history", []), f"All {total_chapters} chapters completed. Ready to end loop (iteration {new_iterations})")

        # 不递增章节号，但更新迭代计数器
        result = {
            "current_chapter_number": current_num,  # 保持当前章节号不变
            "loop_iteration_count": new_iterations,
            "history": history,
            "error_message": None
        }
        print(f"DEBUG: increment_chapter_number - Returning without incrementing: current_chapter_number={current_num}")
        _log_memory_usage("after increment_chapter_number")
        return result

    # 如果还需要生成更多章节，则递增章节号
    new_num = current_num + 1
    print(f"DEBUG: increment_chapter_number - More chapters needed, incrementing: {current_num} -> {new_num}")

    history = _log_and_update_history(state.get("history", []), f"Incrementing chapter number from {current_num} to {new_num} (iteration {new_iterations})")

    print(f"DEBUG: increment_chapter_number - About to return state update")
    print(f"DEBUG: increment_chapter_number - new_chapter_number: {new_num}")
    print(f"DEBUG: increment_chapter_number - new_iterations: {new_iterations}")
    print(f"DEBUG: increment_chapter_number - history length: {len(history)}")

    # 确保返回完整的状态更新，包括所有必要的字段
    result = {
        "current_chapter_number": new_num,
        "loop_iteration_count": new_iterations,
        "current_chapter_retry_count": 0, # Reset for the new chapter
        "current_chapter_original_content": None, # Reset for the new chapter
        "current_chapter_feedback_for_retry": None, # Reset for the new chapter
        "history": history,
        "error_message": None
    }
    print(f"DEBUG: increment_chapter_number - Reset retry count and related fields for the new chapter {new_num}.")
    print(f"DEBUG: increment_chapter_number - Returning result with keys: {list(result.keys())}")
    _log_memory_usage("after increment_chapter_number")
    return result

def generate_kb_visualization_data(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Executing Node: Generate KB Visualization Data")
    print("Executing Node: Generate KB Visualization Data")

    novel_id = state.get("novel_id")
    if novel_id is None:
        msg = "Novel ID not found, cannot generate KB visualization data."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

    try:
        # LoreKeeperAgent might have been initialized and cached in the state earlier
        # For simplicity, we'll assume it can be instantiated here if needed,
        # or that this node runs where 'lore_keeper_instance' is available.
        # If 'lore_keeper_instance' is reliably in state from 'lore_keeper_initialize':
        # lore_keeper = state.get("lore_keeper_instance")
        # if not lore_keeper:
        #    lore_keeper = LoreKeeperAgent(db_name=state.get("db_name", "novel_mvp.db"))
        # else:
        #    print("Using cached LoreKeeperAgent instance for KB viz data.")

        # For this subtask, let's instantiate it directly.
        # Ensure db_name is correctly passed if not using a cached instance.
        db_name = state.get("db_name", "novel_mvp.db")
        lore_keeper = LoreKeeperAgent(db_name=db_name) # Requires LLMClient for full init

        graph_data = lore_keeper.get_knowledge_graph_data(novel_id)
        history = _log_and_update_history(history, f"Successfully generated knowledge graph data. Nodes: {len(graph_data.get('nodes',[]))}, Edges: {len(graph_data.get('edges',[]))}")

        result = dict(state)
        result.update({
            "knowledge_graph_data": graph_data,
            "history": history,
            "error_message": None
        })
        return result

    except Exception as e:
        msg = f"Error in Generate KB Visualization Data node: {e}"
        print(f"ERROR: {msg}")
        result = dict(state)
        result.update({
            "error_message": None, # Let workflow continue
            "history": _log_and_update_history(history, msg, True),
            "knowledge_graph_data": {"nodes": [], "edges": [], "error": msg}
        })
        return result

def execute_conflict_detection(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state.get('current_chapter_number', 'Unknown')
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Conflict Detection for Chapter {current_chapter_num}")
    print(f"Executing Node: Conflict Detection for Chapter {current_chapter_num}")

    generated_chapters = state.get("generated_chapters", [])
    if not generated_chapters:
        msg = "No generated chapters found for conflict detection."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

    last_chapter = generated_chapters[-1]
    chapter_content = last_chapter.get("content")
    chapter_title = last_chapter.get("title", f"Chapter {last_chapter.get('chapter_number', current_chapter_num)}")

    if not chapter_content:
        msg = f"Content for chapter '{chapter_title}' (Num: {current_chapter_num}) is missing for conflict detection."
        return {
            "history": _log_and_update_history(history, msg, True),
            "current_chapter_conflicts": [{"error": msg, "description": msg}],
            "error_message": None # Allow workflow to continue
        }

    try:
        # Initialize LLMClient if not already available in a shared way
        # For now, ConflictDetectionAgent can initialize its own if none is passed.
        # A shared LLMClient instance passed via state would be more efficient.
        llm_client_instance = LLMClient() # Or get from state if available

        # LoreKeeperAgent instance might be needed. For now, agent handles it being None.
        # lore_keeper_instance = state.get("lore_keeper_instance") # This would be if LKA runs before and is cached. CDA will init its own if needed.

        db_name_for_agent = state.get("db_name", "novel_mvp.db")
        agent = ConflictDetectionAgent(llm_client=llm_client_instance, db_name=db_name_for_agent)
        history = _log_and_update_history(history, f"ConflictDetectionAgent instantiated for chapter '{chapter_title}' using db: {db_name_for_agent}.")

        novel_id = state.get("novel_id")
        if novel_id is None:
            msg = f"Novel ID is missing in state, cannot perform conflict detection for chapter '{chapter_title}'."
            history = _log_and_update_history(history, msg, True)
            # Return a valid state structure even on error
            result = dict(state)
            result.update({
                "error_message": msg, # Set error message
                "history": history,
                "current_chapter_conflicts": [{"error": msg, "description": msg}]
            })
            return result

        # Prepare context for conflict detection (simplified for now)
        # previous_chapters_summary = [...] # This would need to be built up
        novel_ctx = {
            "theme": state.get("user_input", {}).get("theme"),
            "style_preferences": state.get("user_input", {}).get("style_preferences"), # Corrected key
            "worldview_description": state.get("selected_worldview_detail", {}).get("core_concept")
                                     if state.get("selected_worldview_detail") else
                                     state.get("worldview_data", {}).get("description"),
        }

        chapter_num_for_agent = last_chapter.get('chapter_number')
        if chapter_num_for_agent is None: # Should not happen if chapter is valid
            msg = f"Chapter number missing for last generated chapter. Cannot run conflict detection."
            history = _log_and_update_history(history, msg, True)
            result = dict(state)
            result.update({"error_message": msg, "history": history, "current_chapter_conflicts": [{"error": msg, "description": msg}]})
            return result

        conflicts = agent.detect_conflicts(
            novel_id=novel_id,
            current_chapter_text=chapter_content,
            current_chapter_number=chapter_num_for_agent,
            novel_context=novel_ctx
        )
        history = _log_and_update_history(history, f"Conflict detection completed for chapter '{chapter_title}'. Found {len(conflicts)} conflicts.")

        print(f"--- Conflict Detection Report: Chapter '{chapter_title}' ---")
        if conflicts:
            for idx, conflict in enumerate(conflicts):
                print(f"  Conflict {idx+1}: [{conflict.get('severity')}] {conflict.get('type')} - {conflict.get('description')}")
        else:
            print("  No conflicts detected.")
        print("----------------------------------------------------")

        auto_mode = state.get("user_input", {}).get("auto_mode", False)
        if conflicts: # Check if the list is not empty
            num_conflicts = len(conflicts)
            if auto_mode:
                log_message = f"INFO: Auto-Mode: {num_conflicts} conflicts detected. Placeholder for auto-resolution attempt. Workflow continues with original text."
                print(log_message)
                history = _log_and_update_history(history, log_message)
            else: # Human-mode
                log_message = f"INFO: Human-Mode: {num_conflicts} conflicts detected. Placeholder: User would be prompted for review and resolution options. Workflow continues."
                print(log_message)
                history = _log_and_update_history(history, log_message)
        else: # No conflicts
            history = _log_and_update_history(history, "No conflicts detected in chapter.") # Added for clarity

        result = dict(state)
        result.update({
            "current_chapter_conflicts": conflicts,
            "history": history,
            "error_message": None
        })
        return result

    except Exception as e:
        msg = f"Error in Conflict Detection node for chapter '{chapter_title}': {e}"
        print(f"ERROR: {msg}")
        result = dict(state)
        result.update({
            "error_message": None,
            "history": _log_and_update_history(history, msg, True),
            "current_chapter_conflicts": [{"error": msg, "description": msg}]
        })
        return result

def execute_content_integrity_review(state: NovelWorkflowState) -> Dict[str, Any]:
    current_chapter_num = state.get('current_chapter_number', 'Unknown')
    history = _log_and_update_history(state.get("history", []), f"Executing Node: Content Integrity Review for Chapter {current_chapter_num}")
    print(f"Executing Node: Content Integrity Review for Chapter {current_chapter_num}")

    generated_chapters = state.get("generated_chapters", [])
    if not generated_chapters:
        msg = "No generated chapters found for content integrity review."
        return {"error_message": msg, "history": _log_and_update_history(history, msg, True)}

    last_chapter = generated_chapters[-1]
    chapter_content = last_chapter.get("content")
    # Corrected: Use chapter_title after definition
    chapter_title = last_chapter.get("title", f"Chapter {last_chapter.get('chapter_number', current_chapter_num)}")

    if not chapter_content:
        # Corrected: Use chapter_title in the message
        msg = f"Content for chapter '{chapter_title}' (Num: {current_chapter_num}) is missing for review."
        return {
            "history": _log_and_update_history(history, msg, True),
            "current_chapter_review": {"error": msg, "overall_score": 0.0},
            "current_chapter_quality_passed": False,
            "error_message": None # Allow workflow to continue, but mark as failed quality
        }

    try:
        agent = ContentIntegrityAgent() # LLMClient initialized by agent
        history = _log_and_update_history(history, f"ContentIntegrityAgent instantiated for chapter '{chapter_title}'.")

        review_results = agent.review_content(chapter_content, content_type=f"Chapter {current_chapter_num}: {chapter_title}")
        history = _log_and_update_history(history, f"Content review completed for chapter '{chapter_title}'.")

        print(f"--- Content Integrity Review: Chapter '{chapter_title}' ---")
        if review_results.get("error"):
            print(f"  Error during review: {review_results['error']}")
        print(f"  Overall Score: {review_results.get('overall_score')}")
        print(f"  Justification: {review_results.get('justification')}")
        print(f"  Individual Scores: {review_results.get('scores')}")
        print("----------------------------------------------------")

        auto_mode = state.get("user_input", {}).get("auto_mode", False)
        quality_threshold = 8.5 if auto_mode else 7.0

        overall_score = review_results.get("overall_score", 0.0)
        passed_quality_check = overall_score >= quality_threshold
            # Initialize these to None; they will be set if quality check fails
            current_chapter_original_content_to_set = None
            current_chapter_feedback_for_retry_to_set = None

        if passed_quality_check:
            history = _log_and_update_history(history, f"Chapter '{chapter_title}' PASSED quality check (Score: {overall_score} >= Threshold: {quality_threshold}).")
            print(f"INFO: Chapter '{chapter_title}' PASSED quality check (Score: {overall_score} >= Threshold: {quality_threshold}).")
        else:
            history = _log_and_update_history(history, f"Chapter '{chapter_title}' FAILED quality check (Score: {overall_score} < Threshold: {quality_threshold}).")
            print(f"WARNING: Chapter '{chapter_title}' FAILED quality check (Score: {overall_score} < Threshold: {quality_threshold}).")
            # Store original content and feedback for retry
            current_chapter_original_content_to_set = chapter_content
            feedback_summary = f"Review Justification: {review_results.get('justification', 'N/A')}. " \
                               f"Overall Score: {overall_score}. " \
                               f"Detailed Scores: {review_results.get('scores', {})}"
            current_chapter_feedback_for_retry_to_set = feedback_summary
            history = _log_and_update_history(history, f"Stored original content and feedback for potential retry of chapter '{chapter_title}'.")

        # Update state
        result = dict(state)
        result.update({
            "current_chapter_review": review_results,
            "current_chapter_quality_passed": passed_quality_check,
            "current_chapter_original_content": current_chapter_original_content_to_set,
            "current_chapter_feedback_for_retry": current_chapter_feedback_for_retry_to_set,
            "history": history,
            "error_message": None
        })
        return result

    except Exception as e:
        # Corrected: Use chapter_title in the message
        msg = f"Error in Content Integrity Review node for chapter '{chapter_title}': {e}"
        print(f"ERROR: {msg}")
        # Still try to return a valid state structure
        result = dict(state)
        result.update({
            "error_message": None, # Let workflow continue but log issue
            "history": _log_and_update_history(history, msg, True),
            "current_chapter_review": {"error": msg, "overall_score": 0.0},
            "current_chapter_quality_passed": False
        })
        return result

def cleanup_resources(state: NovelWorkflowState) -> Dict[str, Any]:
    """清理工作流程资源"""
    print("DEBUG: cleanup_resources - Starting cleanup process")
    history = _log_and_update_history(state.get("history", []), "Executing Node: Cleanup Resources")

    try:
        # 打印最终状态信息
        total_chapters = state.get("total_chapters_to_generate", 0)
        generated_chapters = state.get("generated_chapters", [])
        print(f"DEBUG: cleanup_resources - Final status: {len(generated_chapters)}/{total_chapters} chapters generated")

        # 清理 LoreKeeperAgent 实例
        lore_keeper = state.get("lore_keeper_instance")
        if lore_keeper and hasattr(lore_keeper, 'kb_manager'):
            if hasattr(lore_keeper.kb_manager, 'cleanup_resources'):
                lore_keeper.kb_manager.cleanup_resources()
                print("DEBUG: cleanup_resources - Cleaned up LoreKeeperAgent resources")

        # 清理其他可能的资源
        # 可以在这里添加更多清理逻辑

        print("DEBUG: cleanup_resources - Cleanup completed successfully")
        history = _log_and_update_history(history, "Resources cleaned up successfully")
        return {"history": history, "error_message": None}

    except Exception as e:
        warning_msg = f"Warning: Failed to cleanup resources ({e}), but workflow completed"
        print(f"WARNING: {warning_msg}")
        history = _log_and_update_history(history, warning_msg)
        return {"history": history, "error_message": None}  # 不设置error_message，允许正常结束

def _check_node_output(state: NovelWorkflowState) -> str:
    # 添加执行计数器防止无限循环
    execution_count = state.get("execution_count", 0)
    max_executions = 100  # 设置最大执行次数

    print(f"DEBUG: _check_node_output called (execution #{execution_count})")
    _log_memory_usage("in _check_node_output")

    # 检查状态完整性
    if not isinstance(state, dict):
        print(f"ERROR: _check_node_output - Invalid state type: {type(state)}")
        return "stop_on_error"

    print(f"DEBUG: _check_node_output - State keys: {list(state.keys())}")

    if execution_count > max_executions:
        print(f"SAFETY: Maximum executions ({max_executions}) reached. Forcing workflow end.")
        return "stop_on_error"

    # 检查是否有错误消息
    error_message = state.get("error_message")
    if error_message:
        print(f"DEBUG: _check_node_output - Found error_message: {error_message}")
        return "stop_on_error"

    # 确保状态更新正确传递
    print(f"DEBUG: _check_node_output - No errors found, continuing workflow")
    return "continue"

def _should_continue_chapter_loop(state: NovelWorkflowState) -> str:
    print("DEBUG: _should_continue_chapter_loop - Function called")
    _log_memory_usage("in _should_continue_chapter_loop")

    try:
        # 添加状态完整性检查
        if not isinstance(state, dict):
            print(f"ERROR: _should_continue_chapter_loop - Invalid state type: {type(state)}")
            return "end_loop_on_error"

        print(f"DEBUG: _should_continue_chapter_loop - State keys: {list(state.keys())}")

        if state.get("error_message"):
            print(f"Error detected before loop condition. Routing to END. Error: {state.get('error_message')}")
            return "end_loop_on_error"

        current_chapter = state.get("current_chapter_number", 1)
        total_chapters = state.get("total_chapters_to_generate", 0)
        generated_chapters = state.get("generated_chapters", [])

        print(f"DEBUG: _should_continue_chapter_loop - Received state values:")
        print(f"DEBUG: _should_continue_chapter_loop - current_chapter: {current_chapter}")
        print(f"DEBUG: _should_continue_chapter_loop - total_chapters: {total_chapters}")
        print(f"DEBUG: _should_continue_chapter_loop - generated_chapters count: {len(generated_chapters) if generated_chapters else 0}")

        # 验证关键值的有效性
        if total_chapters <= 0:
            print(f"ERROR: _should_continue_chapter_loop - Invalid total_chapters: {total_chapters}")
            return "end_loop_on_error"

        if not isinstance(generated_chapters, list):
            print(f"ERROR: _should_continue_chapter_loop - Invalid generated_chapters type: {type(generated_chapters)}")
            return "end_loop_on_error"

        # 安全检查：防止无限循环
        max_iterations = state.get("max_loop_iterations", total_chapters * 2)  # 允许一些重试
        current_iterations = state.get("loop_iteration_count", 0)

        print(f"DEBUG: _should_continue_chapter_loop - current_chapter: {current_chapter}, total_chapters: {total_chapters}, generated_chapters: {len(generated_chapters)}, iterations: {current_iterations}/{max_iterations}")

        # 检查是否超过最大迭代次数
        if current_iterations >= max_iterations:
            print(f"SAFETY: Maximum loop iterations ({max_iterations}) reached. Forcing loop end to prevent infinite loop.")
            return "end_loop_on_safety"

        # 检查是否有异常的状态
        if current_chapter > total_chapters + 5:  # 允许一些容错
            print(f"SAFETY: Current chapter number ({current_chapter}) is abnormally high. Forcing loop end.")
            return "end_loop_on_safety"

        # 修复后的逻辑：基于已生成章节数量判断是否继续循环
        # 如果已生成的章节数量少于目标数量，继续循环
        if len(generated_chapters) < total_chapters:
            print(f"Chapter loop: Generated {len(generated_chapters)}/{total_chapters} chapters. Need to generate chapter {current_chapter}. Continuing loop.")

            # 在继续循环前进行内存清理
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    if memory_mb > 2000:  # 超过2GB时进行激进清理
                        print(f"DEBUG: High memory usage before continuing loop ({memory_mb:.1f}MB), performing cleanup")
                        _aggressive_memory_cleanup()
                except Exception:
                    pass

            return "continue_loop"
        else:
            # 已生成的章节数量达到或超过目标数量，结束循环
            print(f"Chapter loop: Generated {len(generated_chapters)}/{total_chapters} chapters. All chapters complete. Ending loop.")
            print(f"DEBUG: _should_continue_chapter_loop - Final decision: END LOOP")
            return "end_loop"

    except Exception as e:
        print(f"CRITICAL ERROR in _should_continue_chapter_loop: {e}")
        import traceback
        traceback.print_exc()
        return "end_loop_on_error"

def _check_workflow_pause_status(state: NovelWorkflowState) -> str:
    """
    Checks if the workflow is paused for an API decision.
    If paused, ends the current graph invocation. The workflow will be resumed
    via a separate call to `WorkflowManager.resume_workflow` once the API receives the decision.
    """
    workflow_status = state.get("workflow_status", "running")
    if workflow_status and workflow_status.startswith("paused_for_"):
        print(f"DEBUG: Workflow PAUSED. Status: {workflow_status}. Ending current graph execution.")
        # History update for this should be in the node that sets the pause status.
        return "WORKFLOW_PAUSED" # This will lead to END in the graph for this invocation.

    # Default to a generic continue if no specific routing is needed beyond this check
    # If different nodes need different "continue" paths after this check,
    # this function might need to return more specific values based on state.
    # For now, a single "continue_workflow" assumes the node's _check_node_output
    # will handle further conditional logic if needed, or it's a direct path.
    print(f"DEBUG: Workflow status is '{workflow_status}'. Continuing graph execution.")
    return "continue_workflow"

def execute_plot_twist_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = state.get("history", [])
    novel_id = state.get("novel_id")
    detailed_plot_data = state.get("detailed_plot_data") # This is List[PlotChapterDetail]
    current_chapter_number_in_loop = state.get("current_chapter_number", 1) # Chapter currently being processed or just finished
    total_chapters_to_generate = state.get("total_chapters_to_generate", 0)
    db_name = state.get("db_name", "novel_mvp.db")

    history = _log_and_update_history(history, "Node: Execute Plot Twist Agent")

    if not all([novel_id, detailed_plot_data]):
        history = _log_and_update_history(history, "Skipping plot twist generation: Missing novel_id or detailed_plot_data.")
        return {"history": history, "available_plot_twist_options": None, "chapter_number_for_twist": None}

    # Placeholder Decision Logic: Generate twists for the chapter *after* the current one,
    # if current is chapter 2 and total chapters >= 3.
    # This means if we just finished generating chapter 2, we consider twists for chapter 3.
    # The 'current_chapter_number' in the main loop refers to the chapter *about to be generated*.
    # So, if current_chapter_number_in_loop is, for example, 2 (meaning we are about to work on chapter 2),
    # a twist might be for chapter 2 itself or chapter 3.
    # Let's define "target_chapter_for_twist" as the chapter number we want to generate twists for.
    # If we are about to generate Chapter 2, and total are >=3, let's generate twists for Chapter 3.

    trigger_twist_generation = False
    target_chapter_for_twist = None

    # Example logic: If we are about to generate chapter 2, and total chapters are 3 or more,
    # consider generating a twist for chapter 3.
    # `current_chapter_number_in_loop` is the chapter number that `context_synthesizer` will prepare for next.
    if total_chapters_to_generate >= 3 and current_chapter_number_in_loop == 2:
        target_chapter_for_twist = 3 # We want to generate a twist for Chapter 3
        if target_chapter_for_twist <= total_chapters_to_generate:
             trigger_twist_generation = True
        else:
            history = _log_and_update_history(history, f"Plot Twist: Target chapter {target_chapter_for_twist} exceeds total chapters {total_chapters_to_generate}. Skipping.")

    # More generic: Generate twist for the *next* chapter if current is, say, the midpoint.
    # Example: if current_chapter_number_in_loop == total_chapters_to_generate // 2 + 1 and total_chapters_to_generate > 1:
    #    target_chapter_for_twist = current_chapter_number_in_loop # Twist for the current chapter being planned
    #    trigger_twist_generation = True


    if trigger_twist_generation and target_chapter_for_twist is not None:
        history = _log_and_update_history(history, f"Condition met: Generating plot twist options for Chapter {target_chapter_for_twist}.")
        try:
            from src.agents.plot_twist_agent import PlotTwistAgent # Local import
            plot_twist_agent = PlotTwistAgent(db_name=db_name) # LLMClient will be default

            # Pass the existing detailed_plot_data (which is List[PlotChapterDetail])
            twist_options = plot_twist_agent.generate_twist_options(
                novel_id=novel_id,
                current_plot_details=detailed_plot_data, # Already List[Dict] or List[PlotChapterDetail]
                target_chapter_number=target_chapter_for_twist,
                num_options=2
            )

            if twist_options:
                history = _log_and_update_history(history, f"Successfully generated {len(twist_options)} twist options for Chapter {target_chapter_for_twist}.")
                return {
                    "history": history,
                    "available_plot_twist_options": twist_options,
                    "chapter_number_for_twist": target_chapter_for_twist,
                    "error_message": None
                }
            else:
                history = _log_and_update_history(history, f"PlotTwistAgent generated no options for Chapter {target_chapter_for_twist}.", True)
                return {"history": history, "available_plot_twist_options": None, "chapter_number_for_twist": None, "error_message": "Plot twist agent returned no options."}

        except ImportError:
            error_msg = "PlotTwistAgent could not be imported. Skipping twist generation."
            history = _log_and_update_history(history, error_msg, True)
            return {"history": history, "error_message": error_msg, "available_plot_twist_options": None, "chapter_number_for_twist": None}
        except Exception as e:
            error_msg = f"Error during plot twist generation: {e}"
            history = _log_and_update_history(history, error_msg, True)
            return {"history": history, "error_message": error_msg, "available_plot_twist_options": None, "chapter_number_for_twist": None}
    else:
        history = _log_and_update_history(history, "Condition for plot twist generation not met. Skipping.")
        return {"history": history, "available_plot_twist_options": None, "chapter_number_for_twist": None}


def prepare_conflict_review_for_api(state: NovelWorkflowState) -> Dict[str, Any]:
    history = state.get("history", [])
    novel_id = state.get("novel_id")
    current_chapter_num = state.get("current_chapter_number")
    generated_chapters = state.get("generated_chapters", [])
    conflicts = state.get("current_chapter_conflicts", [])
    db_name = state.get("db_name", "novel_mvp.db")
    user_input = state.get("user_input", {}) # For novel_context

    history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Preparing conflicts for API review.")

    history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Preparing conflicts for API review.")

    decision_payload_processed_by_resume = state.get("user_made_decision_payload", {}).get("action_taken_in_resume")

    if decision_payload_processed_by_resume:
        history = _log_and_update_history(history, f"Chapter {current_chapter_num}: An action '{decision_payload_processed_by_resume}' was processed by resume_workflow.")
        # Check if all conflicts are resolved or ignored
        # pending_decision_options in the state should have been updated by resume_workflow if an action was taken on one.
        # Or, current_chapter_conflicts might have been cleared if a global action like rewrite_all was done.

        # Re-evaluate remaining conflicts from state["pending_decision_options"] (which should reflect latest conflict statuses)
        # If a specific conflict was handled (e.g. applied_suggestion, ignored_by_user),
        # its status in pending_decision_options would be updated by resume_workflow before re-invoke.

        # The critical part is if resume_workflow decided to clear all pending items (e.g. on proceed_with_remaining)
        # or if it modified the list of pending_decision_options to only contain unresolved ones.
        # For now, assume resume_workflow sets user_made_decision_payload if global action,
        # and updates pending_decision_options for individual actions.

        unresolved_conflicts_in_options = []
        if state.get("pending_decision_options"):
            for c in state.get("pending_decision_options", []):
                if not c.get("full_data", {}).get("resolution_status"): # Check resolution_status in the full_data
                    unresolved_conflicts_in_options.append(c)

        if not unresolved_conflicts_in_options or \
           decision_payload_processed_by_resume in ["rewrite_all_auto_remaining", "proceed_with_remaining"]:
            history = _log_and_update_history(history, f"Chapter {current_chapter_num}: All conflicts processed or global action taken. Proceeding.")
            state["user_made_decision_payload"] = None
            state["workflow_status"] = "running_after_conflict_review_all_resolved_or_ignored"
            state["pending_decision_type"] = None
            state["pending_decision_options"] = None
            state["pending_decision_prompt"] = None
            state["original_chapter_content_for_conflict_review"] = None
            state["current_chapter_conflicts"] = [] # Clear if all resolved/ignored/proceeded
            state["history"] = history
            return state # To _check_workflow_pause_status -> "continue_workflow"
        else:
            # Still unresolved conflicts, re-pause with the remaining ones
            state["pending_decision_options"] = unresolved_conflicts_in_options
            # workflow_status will be set to paused_for_conflict_review again below
            history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Re-pausing for {len(unresolved_conflicts_in_options)} remaining conflicts.")
            # Fall through to the pausing logic

    # If not resuming from a processed decision, or if re-pausing:
    if not novel_id:
        error_msg = f"Chapter {current_chapter_num}: Novel ID missing, cannot prepare conflicts for API review."
        history = _log_and_update_history(history, error_msg, True)
        state["history"] = history
        state["error_message"] = error_msg
        return state

    if not conflicts:
        history = _log_and_update_history(history, f"Chapter {current_chapter_num}: No conflicts found to prepare for API review. Proceeding.")
        state["history"] = history
        state["workflow_status"] = "running_no_conflicts_to_review" # Should proceed in graph
        return state # Should be caught by _check_workflow_pause_status as not paused

    if not generated_chapters:
        error_msg = f"Chapter {current_chapter_num}: No generated chapters available for conflict review."
        history = _log_and_update_history(history, error_msg, True)
        state["history"] = history
        state["error_message"] = error_msg
        return state

    original_chapter_text = generated_chapters[-1].get("content")
    if not original_chapter_text:
        error_msg = f"Chapter {current_chapter_num}: Original chapter text missing for conflict review."
        history = _log_and_update_history(history, error_msg, True)
        state["history"] = history
        state["error_message"] = error_msg
        return state

    state["original_chapter_content_for_conflict_review"] = original_chapter_text

    try:
        llm_client = LLMClient()
        resolver_agent = ConflictResolutionAgent(llm_client=llm_client, db_name=db_name)

        # The ConflictResolutionAgent's suggest_revisions_for_human_review method
        # is expected to format conflicts, perhaps adding suggestions or placeholders.
        # For this subtask, it just adds a placeholder.
        formatted_conflicts_for_api = resolver_agent.suggest_revisions_for_human_review(
            novel_id, original_chapter_text, conflicts, novel_context=user_input
        )

        # Ensure options have unique IDs if the API expects them for selection
        # The `conflict_id` from ConflictDetectionAgent can be used.
        api_options = []
        for i, conflict_detail in enumerate(formatted_conflicts_for_api):
            api_options.append({
                "id": conflict_detail.get("conflict_id", str(i+1)), # Use existing conflict_id
                "text_summary": f"Conflict Type: {conflict_detail.get('type', 'N/A')}, Severity: {conflict_detail.get('severity', 'N/A')}",
                "full_data": conflict_detail # The entire conflict dictionary
            })

        state["pending_decision_type"] = "conflict_review"
        state["pending_decision_options"] = api_options
        state["pending_decision_prompt"] = (
            f"Conflicts ({len(api_options)}) detected in Chapter {current_chapter_num}. "
            "Please review. You can choose to 'proceed_as_is' or 'attempt_generic_rewrite_all_conflicts'."
        )
        state["workflow_status"] = f"paused_for_conflict_review_ch_{current_chapter_num}"
        history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Pausing for API conflict review. {len(api_options)} conflicts presented.")

        db_manager = DatabaseManager(db_name=db_name)
        options_json = json.dumps(api_options)

        prepared_state_for_json = WorkflowManager._prepare_state_for_json_static(dict(state))
        full_state_json = json.dumps(prepared_state_for_json)

        db_manager.update_novel_pause_state(
            novel_id, state["workflow_status"], state["pending_decision_type"],
            options_json, state["pending_decision_prompt"], full_state_json
        )
        history = _log_and_update_history(history, "Successfully saved conflict review pause state to DB.")

    except Exception as e:
        error_msg = f"Chapter {current_chapter_num}: Error preparing conflicts for API review: {e}"
        history = _log_and_update_history(history, error_msg, True)
        state["error_message"] = error_msg

    state["history"] = history
    return state

def _should_generate_twist(state: NovelWorkflowState) -> str:
    """
    Determines if plot twist generation should be attempted.
    """
    history = state.get("history", [])
    current_chapter_number = state.get("current_chapter_number", 1)
    total_chapters = state.get("total_chapters_to_generate", 0)
    # Example Logic: Trigger for Chapter 3 if total chapters >= 3
    # And we are about to generate chapter 2 (so current_chapter_number is 2, meaning next will be 3)
    # This is a placeholder; more sophisticated logic will be based on Plan Step 3.
    # The execute_plot_twist_agent itself has similar logic to determine target_chapter_for_twist.
    # This conditional node simply gates whether execute_plot_twist_agent runs.
    # If execute_plot_twist_agent runs, it will then check its own conditions for *which* chapter to target.

    # Let's use the same logic as in execute_plot_twist_agent for consistency:
    # If current_chapter_number is 2 (meaning we are about to work on chapter 2, and a twist could be for chapter 3)
    # and total_chapters >=3
    if total_chapters >= 3 and current_chapter_number == 2: # Condition to attempt twist generation for *next* chapter
        history = _log_and_update_history(history, "Decision: Conditions met to attempt plot twist generation.")
        state["history"] = history
        return "generate_twist"
    else:
        history = _log_and_update_history(history, "Decision: Conditions not met for plot twist generation. Skipping.")
        state["history"] = history
        return "skip_twist"

def _should_generate_branch(state: NovelWorkflowState) -> str: # Added from Subtask 4.2
    """
    Determines if plot branch generation should be attempted based on placeholder logic.
    """
    history = state.get("history", [])
    current_chapter_number = state.get("current_chapter_number", 1)
    total_chapters = state.get("total_chapters_to_generate", 0)
    # Placeholder Logic: e.g., if current_chapter_number is 3 (about to start chapter 4)
    # and total_chapters_to_generate >= 7
    if total_chapters >= 7 and current_chapter_number == 3: # Note: current_chapter_number is the one *about* to be generated
        history = _log_and_update_history(history, "Decision: Conditions met to attempt plot branch generation.")
        state["history"] = history
        return "generate_branch"
    else:
        history = _log_and_update_history(history, "Decision: Conditions not met for plot branch generation. Skipping.")
        state["history"] = history
        return "skip_branch"

def present_plot_twist_options_for_selection(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Node: Present Plot Twist Options for Selection")
    print("\n=== Plot Twist Options Selection ===")

    available_options = state.get("available_plot_twist_options")
    user_input = state.get("user_input", {})
    auto_engine = state.get("auto_decision_engine")
    db_name = state.get("db_name", "novel_mvp.db")
    novel_id = state.get("novel_id")
    chapter_num_for_twist = state.get("chapter_number_for_twist")

    if not novel_id:
        error_msg = "Novel ID not found in state for plot twist selection."
        return {"error_message": error_msg, "history": _log_and_update_history(history, error_msg, True)}

    if not available_options:
        history = _log_and_update_history(history, "No plot twist options available to select from. Skipping selection.")
        state["history"] = history
        state["selected_plot_twist_option"] = None # Ensure it's None
        return state # Proceed in workflow, apply_selected_plot_twist will also skip.

    interaction_mode = user_input.get("interaction_mode", "cli")
    auto_mode = user_input.get("auto_mode", False)

    # Handle Resuming from API
    if interaction_mode == "api" and not auto_mode and state.get("user_made_decision_payload"):
        payload = state.get("user_made_decision_payload", {})
        if payload.get("source_decision_type") == "plot_twist_selection":
            history = _log_and_update_history(history, "API Mode: Resuming plot twist selection from payload.")
            selected_option_id_from_api = payload.get("selected_option_id") # API sends the chosen option's ID

            if selected_option_id_from_api is None:
                error_msg = "API Mode: 'selected_option_id' missing in payload for plot_twist_selection."
                state["error_message"] = error_msg
                state["history"] = _log_and_update_history(history, error_msg, True)
                return state

            chosen_option = None
            for idx, option_detail in enumerate(available_options):
                # The ID for DecisionOption was 'twist_opt_idx'
                if f"twist_opt_{idx}" == selected_option_id_from_api:
                    chosen_option = option_detail
                    break

            if chosen_option:
                state["selected_plot_twist_option"] = chosen_option
                history = _log_and_update_history(history, f"API Mode: Selected plot twist option '{chosen_option.get('title')}' for Chapter {chapter_num_for_twist}.")
            else:
                error_msg = f"API Mode: Could not find plot twist option with ID '{selected_option_id_from_api}'."
                state["error_message"] = error_msg
                history = _log_and_update_history(history, error_msg, True)
                # Fallback: select no twist or first option? For now, error out.
                return state

            state["user_made_decision_payload"] = None
            state["workflow_status"] = "running_after_plot_twist_selection"
            state["history"] = history
            state["error_message"] = None
            return state

    # Handle Pausing for API
    if interaction_mode == "api" and not auto_mode:
        history = _log_and_update_history(history, "API Mode: Pausing for plot twist selection.")
        options_for_api_decision_node: List[Dict[str, Any]] = []
        for idx, option_detail in enumerate(available_options):
            options_for_api_decision_node.append({
                "id": f"twist_opt_{idx}", # Unique ID for this specific option
                "text_summary": option_detail.get('title', f"Twist Option {idx+1}") + " - " + option_detail.get('core_scene_summary','Summary N/A')[:100]+"...",
                "full_data": option_detail # The full PlotChapterDetail dict
            })

        state["pending_decision_type"] = "plot_twist_selection"
        state["pending_decision_options"] = options_for_api_decision_node
        state["pending_decision_prompt"] = f"Please select a plot twist option for Chapter {chapter_num_for_twist} (or choose to ignore twists)."
        state["workflow_status"] = f"paused_for_plot_twist_selection_ch_{chapter_num_for_twist}"

        try:
            db_manager = DatabaseManager(db_name=db_name)
            options_json_for_db = json.dumps(options_for_api_decision_node)
            prepared_state_for_json = WorkflowManager._prepare_state_for_json_static(dict(state))
            state_json = json.dumps(prepared_state_for_json)
            db_manager.update_novel_pause_state(
                novel_id, state["workflow_status"], state["pending_decision_type"],
                options_json_for_db, state["pending_decision_prompt"], state_json
            )
            history = _log_and_update_history(history, "Successfully saved paused plot twist selection state to DB.")
        except Exception as db_e:
            error_msg = f"API Mode: Failed to save paused plot twist selection state to DB: {db_e}"
            history = _log_and_update_history(history, error_msg, True)
            state["error_message"] = error_msg

        state["history"] = history
        return state

    # CLI / Auto Mode
    chosen_twist_option: Optional[PlotChapterDetail] = None
    if auto_mode and auto_engine:
        history = _log_and_update_history(history, f"Auto mode: Selecting plot twist for Chapter {chapter_num_for_twist}.")
        # Auto-engine could also select an implicit "no twist" option if desired.
        # For now, it picks one of the available twists.
        # To allow "no twist", add a dummy "None" option to available_options before calling decide.
        options_with_no_twist = list(available_options) + [None] # Allow auto-engine to select "no twist"

        chosen_twist_option = auto_engine.decide(
            options_with_no_twist,
            context={"decision_type": "plot_twist_selection", "chapter_number": chapter_num_for_twist}
        )
        if chosen_twist_option:
            log_msg = f"Auto mode: Selected twist '{chosen_twist_option.get('title')}' for Chapter {chapter_num_for_twist}."
        else:
            log_msg = f"Auto mode: Opted to NOT apply a plot twist for Chapter {chapter_num_for_twist}."
    elif auto_mode and not auto_engine: # CLI auto mode without engine
        history = _log_and_update_history(history, f"Auto mode (no engine): Defaulting to first twist option for Chapter {chapter_num_for_twist}.")
        chosen_twist_option = available_options[0] if available_options else None
        log_msg = f"Auto mode (no engine): Defaulted to '{chosen_twist_option.get('title') if chosen_twist_option else 'no twist'}' for Chapter {chapter_num_for_twist}."
    else: # CLI Human Interaction
        print(f"Available plot twist options for Chapter {chapter_num_for_twist}:")
        for i, option in enumerate(available_options):
            print(f"  Option {i + 1}: {option.get('title', 'Untitled Twist')}")
            print(f"    Summary: {option.get('core_scene_summary', 'N/A')}")

        try:
            import sys
            if not sys.stdin.isatty(): # Non-interactive
                chosen_idx = 0 # Default to first option
                log_msg = f"Non-interactive: Defaulted to twist option 1 for Chapter {chapter_num_for_twist}."
            else:
                choice_str = input(f"Select twist option for Chapter {chapter_num_for_twist} (1-{len(available_options)}), or 0 to apply NO twist: ")
                choice_int = int(choice_str)
                if 0 < choice_int <= len(available_options):
                    chosen_idx = choice_int - 1
                    log_msg = f"User selected twist option {chosen_idx + 1} for Chapter {chapter_num_for_twist}."
                else: # User chose 0 or invalid, so no twist
                    chosen_idx = -1 # Indicates no twist
                    log_msg = f"User opted for NO plot twist for Chapter {chapter_num_for_twist}."
        except (ValueError, EOFError, KeyboardInterrupt) as e:
            chosen_idx = -1 # Default to no twist on error
            log_msg = f"Input error ({type(e).__name__}) for twist selection, defaulting to NO twist for Chapter {chapter_num_for_twist}."

        chosen_twist_option = available_options[chosen_idx] if chosen_idx != -1 else None

    history = _log_and_update_history(history, log_msg)
    state["selected_plot_twist_option"] = chosen_twist_option
    state["history"] = history
    state["error_message"] = None
    return state

def apply_selected_plot_twist(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Node: Apply Selected Plot Twist")

    selected_twist: Optional[PlotChapterDetail] = state.get("selected_plot_twist_option")
    twist_chapter_num: Optional[int] = state.get("chapter_number_for_twist")
    detailed_plot_data: Optional[List[PlotChapterDetail]] = state.get("detailed_plot_data")
    plot_id: Optional[int] = state.get("plot_id")
    db_name: Optional[str] = state.get("db_name")

    if not selected_twist or not twist_chapter_num or not detailed_plot_data or not plot_id or not db_name:
        history = _log_and_update_history(history, "Skipping application of plot twist: missing selected twist, chapter number, plot data, plot ID, or DB name.")
        # Clear twist-related fields even if skipping application to prevent carry-over
        state["available_plot_twist_options"] = None
        state["selected_plot_twist_option"] = None
        state["chapter_number_for_twist"] = None
        state["history"] = history
        return state

    try:
        current_plot_list = list(detailed_plot_data) # Make a mutable copy
        twist_chapter_idx = twist_chapter_num - 1

        if not (0 <= twist_chapter_idx < len(current_plot_list)):
            error_msg = f"Invalid chapter index {twist_chapter_idx} for applying twist. Plot length: {len(current_plot_list)}."
            history = _log_and_update_history(history, error_msg, True)
            state["error_message"] = error_msg
            return state # Error state

        history = _log_and_update_history(history, f"Applying selected twist '{selected_twist.get('title')}' to Chapter {twist_chapter_num}.")

        # Replace the original chapter details with the twist, and truncate any subsequent chapters.
        updated_plot_list = current_plot_list[:twist_chapter_idx] + [selected_twist]

        history = _log_and_update_history(history, f"Plot updated up to Chapter {twist_chapter_num}. Subsequent chapters removed due to twist.")

        state["detailed_plot_data"] = updated_plot_list

        # Persist the updated plot to the database
        db_manager = DatabaseManager(db_name=db_name)
        updated_plot_json = json.dumps(updated_plot_list, ensure_ascii=False, indent=2)
        if db_manager.update_plot_summary(plot_id, updated_plot_json):
            history = _log_and_update_history(history, f"Successfully updated plot in DB (ID: {plot_id}) with applied twist.")
        else:
            history = _log_and_update_history(history, f"Warning: Failed to update plot in DB (ID: {plot_id}) after applying twist.", True)
            # Not necessarily a fatal error for workflow, but good to log.

    except Exception as e:
        error_msg = f"Error applying plot twist: {e}"
        history = _log_and_update_history(history, error_msg, True)
        state["error_message"] = error_msg

    # Clear twist-related state fields after application (or attempted application)
    state["available_plot_twist_options"] = None
    state["selected_plot_twist_option"] = None
    state["chapter_number_for_twist"] = None
    state["history"] = history
    return state

def execute_outline_enhancement_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Node: Execute Outline Enhancement Agent")
    narrative_outline = state.get("narrative_outline_text", "")
    outline_review = state.get("outline_review") # Contains overall_score and justification

    if not narrative_outline:
        error_msg = "No narrative outline available to enhance."
        history = _log_and_update_history(history, error_msg, True)
        return {**state, "history": history, "error_message": error_msg}

    print(f"Outline Enhancement Agent: Received outline. Review score: {outline_review.get('overall_score') if outline_review else 'N/A'}")
    # Placeholder logic: Append a note to the outline
    enhanced_outline = narrative_outline + "\n\n[Note: This outline has been processed by the enhancement placeholder.]"

    # Simulate calling an LLM to enhance based on review (conceptual)
    # For now, we just log what could be done.
    if outline_review and outline_review.get('overall_score', 0) < 7.5 : # Assuming 7.5 is the threshold
        history = _log_and_update_history(history, f"Outline score was {outline_review.get('overall_score')}. Justification: {outline_review.get('justification', 'N/A')}. Placeholder enhancement applied.")
    else:
        history = _log_and_update_history(history, "Outline score was sufficient or no review. Placeholder enhancement applied.")

    # Update state
    updated_state = dict(state)
    updated_state["narrative_outline_text"] = enhanced_outline
    updated_state["history"] = _log_and_update_history(history, "Outline enhancement placeholder complete.")
    updated_state["error_message"] = None # Clear any previous error if this node runs successfully
    # Potentially, update outline_data and persist changes if this were a real enhancement
    # For now, only narrative_outline_text in state is updated.
    # If the enhanced outline needs to be re-saved to DB and active_outline_id updated, that would go here.
    # For this subtask, modifying state['narrative_outline_text'] is sufficient.
    return updated_state

def _decide_outline_processing_path(state: NovelWorkflowState) -> str:
    history = state.get("history", [])
    outline_review = state.get("outline_review")
    auto_decision_engine = state.get("auto_decision_engine")

    if outline_review is None or auto_decision_engine is None:
        history = _log_and_update_history(history, "Warning: Outline review or auto-decision engine not available. Defaulting to 'proceed_to_world_weaver'.", True)
        state["history"] = history
        return "proceed_to_world_weaver"

    overall_score = float(outline_review.get("overall_score", 0.0)) # Ensure float for comparison

    # Options for AutoDecisionEngine represent the names of the next nodes or paths
    options = ["enhance_outline", "proceed_to_world_weaver"] # Note: order matters for AutoDecisionEngine if true path is first

    # Context for score-based decision: If score >= 7.5, proceed. Else, enhance.
    # So, if score >= 7.5 is TRUE, we take options[0] -> "proceed_to_world_weaver"
    # If score >= 7.5 is FALSE, we take options[1] -> "enhance_outline"
    # The AutoDecisionEngine returns options[0] for TRUE, options[1] for FALSE.
    # So, if op is ">=", options should be ["proceed_to_world_weaver", "enhance_outline"]
    context = {
        "decision_type": "score_threshold_branch",
        "score": overall_score,
        "threshold": 7.5,
        "operator": ">="
    }

    # The AutoDecisionEngine will return options[0] ("enhance_outline") if score >= 7.5 is TRUE
    # and options[1] ("proceed_to_world_weaver") if score >= 7.5 is FALSE.
    # This is the opposite of what we want. Let's adjust the options order or the logic.
    # If score >= 7.5, we want to "proceed_to_world_weaver".
    # If score < 7.5, we want to "enhance_outline".

    # Let's define paths clearly:
    path_if_score_meets_threshold = "proceed_to_world_weaver"
    path_if_score_below_threshold = "enhance_outline"

    # AutoDecisionEngine returns options[0] if op(score, threshold) is True, else options[1]
    # If operator is ">=", and score >= threshold is True, it returns options[0].
    # So, options[0] must be path_if_score_meets_threshold.
    decision_options = [path_if_score_meets_threshold, path_if_score_below_threshold]

    choice = auto_decision_engine.decide(decision_options, context)

    history = _log_and_update_history(history, f"Outline Review Score: {overall_score}. Threshold: >=7.5. Auto-decision: '{choice}'.")
    state["history"] = history
    return choice

def execute_conflict_resolution_auto(state: NovelWorkflowState) -> Dict[str, Any]:
    history = state.get("history", [])
    novel_id = state.get("novel_id")
    current_chapter_num = state.get("current_chapter_number")
    generated_chapters = list(state.get("generated_chapters", [])) # Ensure it's a mutable list
    conflicts_for_resolution = state.get("current_chapter_conflicts", [])
    db_name = state.get("db_name", "novel_mvp.db")
    # Using user_input as a proxy for novel_context, can be refined
    novel_context_for_agent = state.get("user_input")

    history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Entering auto conflict resolution node.")

    if not novel_id:
        error_msg = f"Chapter {current_chapter_num}: Novel ID missing, cannot perform auto conflict resolution."
        history = _log_and_update_history(history, error_msg, True)
        state["history"] = history
        state["error_message"] = error_msg
        return state

    if not generated_chapters:
        history = _log_and_update_history(history, f"Chapter {current_chapter_num}: No chapters generated, skipping auto conflict resolution.", True)
        state["history"] = history
        # This shouldn't typically happen if graph logic is correct
        return state

    if not conflicts_for_resolution:
        history = _log_and_update_history(history, f"Chapter {current_chapter_num}: No conflicts to resolve, skipping auto conflict resolution.")
        state["history"] = history
        return state

    last_chapter_obj = generated_chapters[-1]
    original_chapter_text = last_chapter_obj.get("content")

    if not original_chapter_text:
        error_msg = f"Chapter {current_chapter_num}: Original chapter text is missing, cannot perform auto conflict resolution."
        history = _log_and_update_history(history, error_msg, True)
        state["history"] = history
        state["error_message"] = error_msg
        return state

    try:
        llm_client = LLMClient()
        resolver_agent = ConflictResolutionAgent(llm_client=llm_client, db_name=db_name)

        history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Attempting auto-resolution for {len(conflicts_for_resolution)} conflicts.")
        revised_text = resolver_agent.attempt_auto_resolve(
            novel_id, original_chapter_text, conflicts_for_resolution, novel_context=novel_context_for_agent
        )

        if revised_text is not None and revised_text != original_chapter_text:
            # Create a new dictionary for the updated chapter to ensure state update
            updated_chapter = dict(last_chapter_obj)
            updated_chapter["content"] = revised_text
            updated_chapter["summary"] = "Summary needs regeneration after auto-resolution."

            generated_chapters[-1] = updated_chapter # Replace the last chapter with the updated one

            state["generated_chapters"] = generated_chapters
            history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Auto-conflict resolution attempted and text was modified.")
            # Clear conflicts as they've been "resolved" or attempted
            state["current_chapter_conflicts"] = []
        else:
            history = _log_and_update_history(history, f"Chapter {current_chapter_num}: Auto-conflict resolution attempted, but no changes made to chapter text.")
            # Conflicts remain as they were not changed by auto-resolve

    except Exception as e:
        error_msg = f"Chapter {current_chapter_num}: Error during auto conflict resolution: {e}"
        history = _log_and_update_history(history, error_msg, True)
        state["error_message"] = error_msg
        # Do not clear conflicts if resolution failed

    state["history"] = history
    return state

def execute_plot_branching_agent(state: NovelWorkflowState) -> Dict[str, Any]:
    history = state.get("history", [])
    novel_id = state.get("novel_id")
    detailed_plot_data = state.get("detailed_plot_data")
    current_chapter_num_in_loop = state.get("current_chapter_number", 1) # Chapter about to be processed
    total_chapters_to_generate = state.get("total_chapters_to_generate", 0)
    db_name = state.get("db_name", "novel_mvp.db")

    history = _log_and_update_history(history, "Node: Execute Plot Branching Agent")

    if not all([novel_id, detailed_plot_data]):
        history = _log_and_update_history(history, "Skipping plot branch generation: Missing novel_id or detailed_plot_data.")
        return {**state, "history": history, "available_plot_branch_options": None, "chapter_number_for_branching": None}

    trigger_branch_generation = False
    branch_point_chapter_num_for_agent = None
    num_chapters_per_branch = 3 # Default, can be made configurable

    # Placeholder Decision Logic: e.g., if current_chapter_number is 4 (meaning we are about to start chapter 4)
    # and total_chapters_to_generate >= 7, then generate branches starting from chapter 4.
    # current_chapter_number_in_loop is the chapter *about to be generated*.
    if total_chapters_to_generate >= 7 and current_chapter_num_in_loop == 4:
        branch_point_chapter_num_for_agent = current_chapter_num_in_loop
        # Check if generating 3 chapters from this point exceeds total_chapters.
        # If so, this branching logic might need adjustment or it implies the novel extends.
        # For now, assume branches can temporarily extend beyond original total_chapters_to_generate,
        # and selecting a branch might redefine total_chapters.
        if branch_point_chapter_num_for_agent + num_chapters_per_branch -1 <= total_chapters_to_generate + num_chapters_per_branch: # Allow extension
            trigger_branch_generation = True
        else:
             history = _log_and_update_history(history, f"Plot Branching: Target branch end {branch_point_chapter_num_for_agent + num_chapters_per_branch -1} too far. Skipping.")


    if trigger_branch_generation and branch_point_chapter_num_for_agent is not None:
        history = _log_and_update_history(history, f"Condition met: Generating plot branch options from Chapter {branch_point_chapter_num_for_agent}.")
        try:
            from src.agents.plot_branching_agent import PlotBranchingAgent # Local import
            branching_agent = PlotBranchingAgent(db_name=db_name)

            # current_plot_details should be up to the chapter *before* the branch point.
            plot_context_for_branching = [
                chap for chap in detailed_plot_data
                if chap.get('chapter_number', 0) < branch_point_chapter_num_for_agent
            ]

            branch_options = branching_agent.generate_branching_plot_options(
                novel_id=novel_id,
                current_plot_details=plot_context_for_branching,
                branch_point_chapter_number=branch_point_chapter_num_for_agent,
                num_options=2,
                num_chapters_per_branch=num_chapters_per_branch
            )

            if branch_options:
                history = _log_and_update_history(history, f"Successfully generated {len(branch_options)} plot branch options from Chapter {branch_point_chapter_num_for_agent}.")
                return {
                    **state, "history": history,
                    "available_plot_branch_options": branch_options,
                    "chapter_number_for_branching": branch_point_chapter_num_for_agent,
                    "error_message": None
                }
            else:
                history = _log_and_update_history(history, f"PlotBranchingAgent generated no options from Chapter {branch_point_chapter_num_for_agent}.", True)
                return {**state, "history": history, "available_plot_branch_options": None, "chapter_number_for_branching": None, "error_message": "Plot branching agent returned no options."}

        except ImportError:
            error_msg = "PlotBranchingAgent could not be imported. Skipping branch generation."
            history = _log_and_update_history(history, error_msg, True)
            return {**state, "history": history, "error_message": error_msg, "available_plot_branch_options": None, "chapter_number_for_branching": None}
        except Exception as e:
            error_msg = f"Error during plot branch generation: {e}"
            history = _log_and_update_history(history, error_msg, True)
            return {**state, "history": history, "error_message": error_msg, "available_plot_branch_options": None, "chapter_number_for_branching": None}
    else:
        history = _log_and_update_history(history, "Condition for plot branch generation not met or invalid parameters. Skipping.")
        return {**state, "history": history, "available_plot_branch_options": None, "chapter_number_for_branching": None}

def _decide_after_conflict_detection(state: NovelWorkflowState) -> str:
    history = state.get("history", [])
    conflicts = state.get("current_chapter_conflicts", [])
    user_input = state.get("user_input", {})
    auto_mode = user_input.get("auto_mode", False)
    interaction_mode = user_input.get("interaction_mode", "cli")

    if conflicts:
        history = _log_and_update_history(history, f"Decision: {len(conflicts)} conflicts found.")
        if auto_mode:
            history = _log_and_update_history(history, "Auto-Mode: Routing to auto-conflict resolution.")
            state["history"] = history
            return "resolve_conflicts_auto"
        elif interaction_mode == "api": # Human mode, API interaction
            history = _log_and_update_history(history, "Human-Mode (API): Routing for API-based conflict review preparation.")
            state["history"] = history
            return "human_api_conflict_pending" # This will go to prepare_conflict_review_for_api node
        else: # Human mode, CLI interaction
            history = _log_and_update_history(history, "Human-Mode (CLI): Conflicts detected. Currently, CLI mode proceeds without specific resolution step for conflicts. Manual review would be needed based on logs.")
            state["history"] = history
            return "proceed_to_increment" # CLI human mode currently doesn't pause for this
    else:
        history = _log_and_update_history(history, "Decision: No conflicts found. Proceeding to increment chapter.")
        state["history"] = history
        return "proceed_to_increment" # CLI human mode currently doesn't pause for this


# --- New Conditional Logic Function: _should_retry_chapter ---
def _should_retry_chapter(state: NovelWorkflowState) -> str:
    """
    Determines if the current chapter should be retried based on quality and retry limits.
    This function is called after content_integrity_review.
    """
    history = _log_and_update_history(state.get("history", []), "Conditional Node: Should Retry Chapter?")
    print("DEBUG: _should_retry_chapter - Function called")

    auto_mode = state.get("user_input", {}).get("auto_mode", False)
    # Default quality_passed to True to avoid retries if the field is somehow missing
    quality_passed = state.get("current_chapter_quality_passed", True)
    current_retry_count_for_this_chapter = state.get("current_chapter_retry_count", 0)
    max_retries = state.get("max_chapter_retries", 1)

    print(f"DEBUG: _should_retry_chapter - Auto Mode: {auto_mode}, Quality Passed: {quality_passed}, Retries This Chapter: {current_retry_count_for_this_chapter}/{max_retries}")

    if auto_mode and not quality_passed:
        if current_retry_count_for_this_chapter < max_retries:
            state["current_chapter_retry_count"] = current_retry_count_for_this_chapter + 1
            history = _log_and_update_history(history, f"Chapter failed quality. Auto-retry attempt {state['current_chapter_retry_count']}/{max_retries}.")
            state["history"] = history
            return "retry_chapter"
        else: # Max retries reached in auto_mode and still failed
            history = _log_and_update_history(history, f"Chapter failed quality after {max_retries} auto-retries. Initiating manual review.")
            state["history"] = history
            return "initiate_manual_review"

    # If not (auto_mode and not quality_passed) OR if quality_passed:
    # This means:
    # 1. Quality passed (in any mode)
    # 2. Not auto_mode and quality failed (human decides next, no auto-retry or manual review trigger here)
    # 3. Not auto_mode and quality passed (covered by 1)

    # Reset retry count for the next chapter's first attempt.
    state["current_chapter_retry_count"] = 0
    history = _log_and_update_history(history, "Proceeding to KB update (quality passed, or not auto_mode, or retries not applicable).")
    state["history"] = history
    return "proceed_to_kb_update"

def prepare_for_manual_chapter_review(state: NovelWorkflowState) -> Dict[str, Any]:
    history = _log_and_update_history(state.get("history", []), "Node: Prepare for Manual Chapter Review")

    generated_chapters = state.get("generated_chapters", [])
    if not generated_chapters:
        error_msg = "Cannot prepare for manual review: No chapters generated."
        history = _log_and_update_history(history, error_msg, True)
        return {**state, "history": history, "error_message": error_msg}

    failed_chapter = generated_chapters[-1]
    chapter_id_to_review = failed_chapter.get('id')

    if chapter_id_to_review is None: # Should ideally not happen if chapter was saved
        error_msg = "Cannot prepare for manual review: Failed chapter has no ID."
        history = _log_and_update_history(history, error_msg, True)
        return {**state, "history": history, "error_message": error_msg}

    state["chapter_pending_manual_review_id"] = chapter_id_to_review
    state["chapter_content_for_manual_review"] = failed_chapter.get("content")
    state["chapter_review_feedback_for_manual_review"] = state.get("current_chapter_review") # The review that triggered this
    state["workflow_status"] = "paused_for_manual_chapter_review"
    state["pending_decision_type"] = "manual_chapter_review"
    state["pending_decision_prompt"] = f"Chapter {failed_chapter.get('chapter_number')} ('{failed_chapter.get('title')}') requires manual review after {state.get('max_chapter_retries', 'N/A')} failed auto-retry attempts."

    # Options for the API to present to the user
    # These are action IDs, not specific content choices.
    state["pending_decision_options"] = [
        {"id": "submit_edit", "text_summary": "Submit with edits (content in request body of different endpoint)", "full_data": {"action_description": "User will provide new content for the chapter."}},
        {"id": "use_as_is", "text_summary": "Use current version as is (no edits needed)", "full_data": {"action_description": "The last generated version of the chapter will be accepted despite quality score."}}
    ]

    history = _log_and_update_history(history, f"Workflow paused for manual review of Chapter ID: {chapter_id_to_review}.")

    db_manager = DatabaseManager(db_name=state.get("db_name"))
    options_json = json.dumps(state["pending_decision_options"])
    prepared_state_for_json = WorkflowManager._prepare_state_for_json_static(dict(state))
    state_json_for_db = json.dumps(prepared_state_for_json)

    db_manager.update_novel_pause_state(
        state["novel_id"],
        state["workflow_status"],
        state["pending_decision_type"],
        options_json,
        state["pending_decision_prompt"],
        state_json_for_db
    )
    history = _log_and_update_history(history, "Manual review pause state saved to DB.")
    state["history"] = history
    return state # This will be caught by _check_workflow_pause_status and lead to END

def _route_after_prepare_manual_review(state: NovelWorkflowState) -> str:
    history = state.get("history", [])

    if state.get("user_made_decision_payload", {}).get("source_decision_type") == "manual_chapter_review":
        payload = state["user_made_decision_payload"]
        action = payload.get("action")
        edited_content_provided = payload.get("edited_content_provided", False) # From API endpoint
        chapter_id_processed = state.get("chapter_pending_manual_review_id")
        db_name = state.get("db_name")

        history = _log_and_update_history(history, f"Resuming after manual chapter review. Action: {action}.")

        if action == "submit_edit" and edited_content_provided:
            # Content update already happened in the API endpoint via db_manager.update_chapter_content
            # Need to refresh the chapter content in the state's generated_chapters list
            if chapter_id_processed is not None and db_name:
                db_manager = DatabaseManager(db_name)
                updated_chapter_from_db = db_manager.get_chapter_by_id(chapter_id_processed)
                if updated_chapter_from_db:
                    found_idx = -1
                    for i, chap in enumerate(state.get("generated_chapters", [])):
                        if chap.get("id") == chapter_id_processed:
                            found_idx = i
                            break
                    if found_idx != -1:
                        state["generated_chapters"][found_idx]["content"] = updated_chapter_from_db["content"]
                        # Also update its 'creation_date' to reflect the edit time, if desired
                        state["generated_chapters"][found_idx]["creation_date"] = updated_chapter_from_db["creation_date"]
                        history = _log_and_update_history(history, f"Chapter ID {chapter_id_processed} content in workflow state updated from DB after manual edit.")
                    else:
                         history = _log_and_update_history(history, f"Warning: Chapter ID {chapter_id_processed} not found in state.generated_chapters to update content.", True)
                else:
                    history = _log_and_update_history(history, f"Warning: Could not fetch updated chapter {chapter_id_processed} from DB after manual edit.", True)

            state["current_chapter_quality_passed"] = None # Force re-review
            state["current_chapter_review"] = None
            next_node = "content_integrity_review" # Send back for re-review
            history = _log_and_update_history(history, "Manual edit submitted. Routing for re-review.")

        elif action == "use_as_is":
            history = _log_and_update_history(history, "Chapter accepted 'as is' per manual review. Routing to KB update.")
            # Chapter quality is still considered "failed" from the last auto-review, but we are overriding that.
            # The workflow will proceed as if it passed, but the score remains low.
            # No need to change current_chapter_quality_passed here, as _should_retry_chapter won't run again for this.
            next_node = "lore_keeper_update_kb"
        else:
            history = _log_and_update_history(history, f"Unknown action '{action}' from manual review. Defaulting to KB update.", True)
            next_node = "lore_keeper_update_kb" # Fallback

        # Clear manual review specific fields
        state["chapter_pending_manual_review_id"] = None
        state["chapter_content_for_manual_review"] = None
        state["chapter_review_feedback_for_manual_review"] = None
        state["user_made_decision_payload"] = None
        state["workflow_status"] = f"running_after_manual_review_{action}" # Update status
        state["history"] = history
        return next_node
    else:
        # This is the initial call to prepare_for_manual_chapter_review, setting up the pause.
        # The actual pause is handled by _check_workflow_pause_status after this node.
        # So, if we are not resuming, it means we are pausing.
        state["history"] = history # history already updated by the main part of prepare_for_manual_chapter_review
        return "PAUSE_FOR_USER" # Special signal for graph to END this invocation.


class WorkflowManager:
    def __init__(self, db_name="novel_mvp.db", mode="human"): # mode is now less relevant here, user_input drives it.
        self.db_name = db_name
        self.mode = mode
        self.auto_decision_engine = AutoDecisionEngine() if self.mode == "auto" else None

        print(f"WorkflowManager initialized (DB: {self.db_name}, Mode: {self.mode}).") # Added mode to log
        self.initial_history = [f"WorkflowManager initialized (DB: {self.db_name}, Mode: {self.mode}) and graph compiled."]
        self.workflow = StateGraph(NovelWorkflowState)
        self._build_graph()
        self.app = self.workflow.compile()

    def resume_workflow(self, novel_id: int, decision_type_from_api: str, decision_payload_from_api: Dict) -> Dict:
        """
        Resumes the workflow from a paused state after a human decision made via API.
        Loads the state from DB, applies decision, and re-invokes the workflow.
        """
        print(f"WorkflowManager: Attempting to resume workflow for novel_id {novel_id} with decision type {decision_type_from_api}")
        db_manager = DatabaseManager(self.db_name)

        loaded_data = db_manager.load_workflow_snapshot_and_decision_info(novel_id)
        if not loaded_data or not loaded_data.get("full_workflow_state_json"):
            # This case should ideally be handled by the API layer before calling resume_workflow
            # but as a safeguard:
            error_msg = f"Cannot resume: workflow state not found for novel {novel_id}."
            print(f"ERROR: {error_msg}")
            # This function needs to return a state dict, so construct one indicating error.
            # However, without the original state, we can't do much.
            # This highlights the need for robust state management by the caller (API layer).
            # For now, return a minimal error state if possible, or raise an exception that the API layer must handle.
            raise ValueError(error_msg) # Or return a specific error state dict

        current_state_snapshot: NovelWorkflowState = json.loads(loaded_data["full_workflow_state_json"])

        # Re-initialize transient fields after loading from JSON
        user_input_loaded = current_state_snapshot.get("user_input", {})
        if user_input_loaded.get("auto_mode", False):
            # If the manager instance itself was created in 'auto' mode matching the state's mode, use its ADE
            if self.mode == "auto" and self.auto_decision_engine:
                 current_state_snapshot["auto_decision_engine"] = self.auto_decision_engine
            else: # Otherwise, (e.g. manager is 'human' mode, or state is 'auto' but manager's ADE is None) create a fresh ADE
                 current_state_snapshot["auto_decision_engine"] = AutoDecisionEngine()
        else:
            current_state_snapshot["auto_decision_engine"] = None

        # Ensure db_name is present in the loaded state for agents that need it.
        # If not already there from initial state, set it from the manager instance.
        if "db_name" not in current_state_snapshot or not current_state_snapshot["db_name"]:
            current_state_snapshot["db_name"] = self.db_name


        history = current_state_snapshot.get("history", []) # Get history early for logging

        # Apply the decision payload to the state. This will be processed by the relevant node.
        current_state_snapshot["user_made_decision_payload"] = {
            "source_decision_type": decision_type_from_api,
            **decision_payload_from_api # This now includes custom_data for character_multi_selection
        }

        # Clear pending decision fields as they are now being processed
        current_state_snapshot["pending_decision_type"] = None
        current_state_snapshot["pending_decision_options"] = None
        current_state_snapshot["pending_decision_prompt"] = None
        current_state_snapshot["workflow_status"] = f"resuming_after_{decision_type_from_api}" # General resuming status
        current_state_snapshot["error_message"] = None # Clear previous errors

        history = _log_and_update_history(history, f"Resuming workflow for decision type '{decision_type_from_api}'. Payload set. New status: {current_state_snapshot['workflow_status']}")
        current_state_snapshot["history"] = history
        logger.info(f"Resuming workflow for {decision_type_from_api}. Payload: {decision_payload_from_api}. New status: {current_state_snapshot['workflow_status']}")


        # Specific payload processing for some decision types if needed before node execution (mostly handled by nodes now)
        if decision_type_from_api == "outline_selection":
            # The present_outlines_for_selection_cli node will handle the logic based on user_made_decision_payload
            pass
        elif decision_type_from_api == "worldview_selection":
            # The present_worldviews_for_selection_cli node will handle this
            pass
        elif decision_type_from_api == "character_multi_selection":
            # The present_character_options_for_selection node will handle this
            pass
        elif decision_type_from_api == "conflict_review":
            # Conflict review has more complex state changes that might need pre-processing here
            # or ensure the prepare_conflict_review_for_api node handles it robustly when resuming.
            # For now, the generic payload setting above is assumed to be sufficient for prepare_conflict_review_for_api
            # to pick up the user's action.
            # The logic within resume_workflow for conflict_review (applying suggestions etc.)
            # needs to be carefully reviewed if it's still needed or if prepare_conflict_review_for_api
            # should fully manage the state based on user_made_decision_payload.
            # For this refactor, we assume prepare_conflict_review_for_api handles it.
            # Removing the extensive conflict_review logic block from here.
            logger.info(f"Conflict review decision received. Node 'prepare_conflict_review_for_api' will process: {decision_payload_from_api}")
            # Ensure the user_made_decision_payload is correctly structured for prepare_conflict_review_for_api
            # The generic setting above should suffice.
            pass
        elif decision_type_from_api == "plot_twist_selection":
            # Ensure payload contains selected_option_id (which is the twist_opt_idx string)
            # This is already generically handled by the user_made_decision_payload setup.
            # The present_plot_twist_options_for_selection node will use this.
            logger.info(f"Plot twist selection decision received. Node 'present_plot_twist_options_for_selection' will process: {decision_payload_from_api}")
            pass
        elif decision_type_from_api == "manual_chapter_review":
            # Payload structure: {"action": "submit_edit" / "use_as_is", "edited_content_provided": bool}
            # This is already set in user_made_decision_payload by the generic logic.
            # The _route_after_prepare_manual_review node will process this.
            logger.info(f"Manual chapter review decision received. Node '_route_after_prepare_manual_review' will process: {decision_payload_from_api}")
            pass


        # Common state updates for any decision type before re-invocation (some might be overridden by conflict logic)
        if not current_state_snapshot["workflow_status"].startswith("paused_for_"): # If not specifically re-paused by conflict logic
            current_state_snapshot["workflow_status"] = f"resuming_after_{decision_type_from_api}"
            # These are already cleared above, but as a safeguard:
            current_state_snapshot["pending_decision_type"] = None
            current_state_snapshot["pending_decision_options"] = None
            current_state_snapshot["pending_decision_prompt"] = None
        current_state_snapshot["error_message"] = None # Clear previous errors before resuming


        num_chapters = current_state_snapshot.get("user_input", {}).get("chapters", 3)
        # Increment execution_count from the loaded state
        current_state_snapshot["execution_count"] = current_state_snapshot.get("execution_count", 0) + 1
        recursion_limit = max(50, 15 + (4 * num_chapters) + 10 + current_state_snapshot["execution_count"])

        print(f"DEBUG: Resuming workflow execution for novel {novel_id}. Execution count: {current_state_snapshot['execution_count']}")

        final_state_after_resume: NovelWorkflowState
        try:
            final_state_after_resume = self.app.invoke(current_state_snapshot, {"recursion_limit": recursion_limit})
        except Exception as e:
            print(f"CRITICAL: Workflow resumption for novel {novel_id} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            current_state_snapshot["error_message"] = f"Workflow resumption failed critically: {e}"
            current_state_snapshot["workflow_status"] = "resumption_critical_error"
            final_state_after_resume = current_state_snapshot # type: ignore

        # After invocation, handle DB update based on the outcome
        final_status = final_state_after_resume.get("workflow_status", "unknown_after_resume")

        # Use static helper to prepare final state for JSON storage
        prepared_final_state_for_json_dict = WorkflowManager._prepare_state_for_json_static(dict(final_state_after_resume))
        final_snapshot_json_for_db = json.dumps(prepared_final_state_for_json_dict)

        if final_status and final_status.startswith("paused_for_"):
            # If it paused again, update_novel_pause_state should have been called from the decision node itself
            # which should use the _prepare_state_for_json method.
            # Re-saving here is a fallback or for cases where invoke ends before a node's explicit save.
            print(f"Workflow for novel {novel_id} resumed and then paused again for: {final_status}")
            # The decision node that re-paused should have already saved the *prepared* state.
            # This save here is a safety net if the pause was due to recursion limit or unexpected exit.
            # If this save is truly needed, it should also get the latest pending_decision fields from final_state_after_resume
            # and pass the *prepared* final_snapshot_json_for_db.
            # For now, assuming decision nodes handle their own saving of prepared state if they pause.
            # If a generic save is needed here for an unexpected pause, it should be the prepared JSON:
            # db_manager.update_novel_pause_state(
            #     novel_id, final_status,
            #     final_state_after_resume.get("pending_decision_type"),
            #     json.dumps(self._prepare_state_for_json(final_state_after_resume.get("pending_decision_options", []))), # Ensure options are also prepared if complex
            #     final_state_after_resume.get("pending_decision_prompt"),
            #     final_snapshot_json_for_db # This is already prepared
            # )
            pass # Assuming decision node handled its own saving of prepared state.
        else: # Completed, failed, or other terminal/intermediate state that isn't a formal pause
            print(f"Workflow for novel {novel_id} resumed. Final status: {final_status}.")
            db_manager.update_novel_status_after_resume(novel_id, final_status, final_snapshot_json_for_db)

        return final_state_after_resume

    @staticmethod
    def _prepare_state_for_json_static(state_dict: Dict) -> Dict:
        """Removes non-serializable fields from a state dictionary before JSON dump."""
        serializable_state = dict(state_dict).copy() # Ensure it's a dict and copy
        serializable_state.pop("auto_decision_engine", None)
        serializable_state.pop("lore_keeper_instance", None) # Defensive, though not in TypedDict
        # Add any other runtime objects that shouldn't be serialized by popping them here
        return serializable_state

    # Keep the instance method version if it's used by other instance methods directly,
    # or refactor those calls as well. For now, resume_workflow was updated to use static.
    # This instance method can be removed if no other *instance* methods of WorkflowManager call it.
    # For now, let's keep it simple and assume _prepare_state_for_json_static is the primary one.
    # If self._prepare_state_for_json is called by another instance method, it will correctly delegate.
    # def _prepare_state_for_json(self, state_dict: Dict) -> Dict:
    #     return WorkflowManager._prepare_state_for_json_static(state_dict)
    # Removing the instance method as it's not strictly needed if all calls go to static.

    def _should_prompt_user(self, decision_point: Optional[str] = None) -> bool:
        """
        Determines if the user should be prompted for a decision based on the current mode.

        Args:
            decision_point: An optional string identifying the decision point (for logging/future use).

        Returns:
            True if in "human" mode, False otherwise.
        """
        if decision_point:
            print(f"Decision point '{decision_point}': _should_prompt_user called in '{self.mode}' mode. Returning {self.mode == 'human'}")
        return self.mode == "human"

    def _make_auto_decision(self, options: List[Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Makes an automated decision using the AutoDecisionEngine.

        Args:
            options: A list of options to choose from.
            context: Optional context for the decision.

        Returns:
            The selected option.

        Raises:
            RuntimeError: If called when AutoDecisionEngine is not available (i.e., not in 'auto' mode).
        """
        if not self.auto_decision_engine:
            raise RuntimeError("AutoDecisionEngine is not available in the current mode.")

        print(f"Making auto decision with context: {context.get('decision_type', 'N/A') if context else 'N/A'}")
        return self.auto_decision_engine.decide(options, context)

    def _build_graph(self):
        self.workflow.add_node("narrative_pathfinder", execute_narrative_pathfinder_agent)
        self.workflow.add_node("present_outlines_cli", present_outlines_for_selection_cli)
        self.workflow.add_node("persist_novel_record", persist_novel_record_node)
        self.workflow.add_node("persist_initial_outline", persist_initial_outline_node)
        self.workflow.add_node("outline_quality_guardian", execute_outline_quality_guardian) # New node
        self.workflow.add_node("world_weaver", execute_world_weaver_agent)
        self.workflow.add_node("present_worldviews_cli", present_worldviews_for_selection_cli)
        self.workflow.add_node("persist_worldview", persist_worldview_node)
        self.workflow.add_node("plot_architect", execute_plot_architect_agent)
        self.workflow.add_node("persist_plot", persist_plot_node)
        self.workflow.add_node("character_sculptor", execute_character_sculptor_agent)
        self.workflow.add_node("present_character_options_for_selection", present_character_options_for_selection) # New Node
        self.workflow.add_node("persist_selected_characters", persist_selected_characters) # New Node
        self.workflow.add_node("lore_keeper_initialize", execute_lore_keeper_initialize)
        self.workflow.add_node("prepare_for_chapter_loop", prepare_for_chapter_loop)
        # Plot Twist Nodes
        self.workflow.add_node("execute_plot_twist_agent", execute_plot_twist_agent)
        self.workflow.add_node("present_plot_twist_options_for_selection", present_plot_twist_options_for_selection)
        self.workflow.add_node("apply_selected_plot_twist", apply_selected_plot_twist)
        # Regular Chapter Nodes
        self.workflow.add_node("context_synthesizer", execute_context_synthesizer_agent)
        self.workflow.add_node("chapter_chronicler", execute_chapter_chronicler_agent)
        self.workflow.add_node("content_integrity_review", execute_content_integrity_review) # Existing
        self.workflow.add_node("should_retry_chapter", _should_retry_chapter) # Ensure this node is added
        self.workflow.add_node("lore_keeper_update_kb", execute_lore_keeper_update_kb)
        self.workflow.add_node("conflict_detection", execute_conflict_detection)
        self.workflow.add_node("execute_conflict_resolution_auto", execute_conflict_resolution_auto)
        self.workflow.add_node("prepare_conflict_review_for_api", prepare_conflict_review_for_api) # New node
        self.workflow.add_node("execute_plot_twist_agent", execute_plot_twist_agent) # New Node
        self.workflow.add_node("execute_outline_enhancement_agent", execute_outline_enhancement_agent) # New Node
        self.workflow.add_node("prepare_for_manual_chapter_review", prepare_for_manual_chapter_review) # New Node
        self.workflow.add_node("increment_chapter_number", increment_chapter_number)
        self.workflow.add_node("cleanup_resources", cleanup_resources)
        self.workflow.add_node("generate_kb_visualization_data", generate_kb_visualization_data)

        self.workflow.set_entry_point("narrative_pathfinder")
        self.workflow.add_conditional_edges("narrative_pathfinder", _check_node_output, {"continue": "present_outlines_cli", "stop_on_error": END})

        # present_outlines_cli now goes to _check_workflow_pause_status
        self.workflow.add_conditional_edges("present_outlines_cli", _check_workflow_pause_status, {
            "WORKFLOW_PAUSED": END, # End this invocation if paused
            "continue_workflow": "persist_novel_record" # If not paused, proceed
        })
        # Then _check_node_output for persist_novel_record
        self.workflow.add_conditional_edges("persist_novel_record", _check_node_output, {"continue": "persist_initial_outline", "stop_on_error": END})

        self.workflow.add_conditional_edges("persist_initial_outline", _check_node_output, {"continue": "outline_quality_guardian", "stop_on_error": END})

        # Outline Quality Guardian now leads to a decision point
        self.workflow.add_conditional_edges("outline_quality_guardian", _check_node_output, {"continue": "_decide_outline_processing_path", "stop_on_error": END})
        self.workflow.add_conditional_edges(
            "_decide_outline_processing_path",
            _decide_outline_processing_path,
            {
                "proceed_to_world_weaver": "world_weaver",
                "enhance_outline": "execute_outline_enhancement_agent"
            }
        )
        self.workflow.add_conditional_edges("execute_outline_enhancement_agent", _check_node_output, {"continue": "world_weaver", "stop_on_error": END})

        self.workflow.add_conditional_edges("world_weaver", _check_node_output, {"continue": "present_worldviews_cli", "stop_on_error": END})

        # present_worldviews_cli now goes to _check_workflow_pause_status
        self.workflow.add_conditional_edges("present_worldviews_cli", _check_workflow_pause_status, {
            "WORKFLOW_PAUSED": END, # End this invocation if paused
            "continue_workflow": "persist_worldview" # If not paused, proceed
        })
        # Then _check_node_output for persist_worldview
        self.workflow.add_conditional_edges("persist_worldview", _check_node_output, {"continue": "plot_architect", "stop_on_error": END})

        self.workflow.add_conditional_edges("plot_architect", _check_node_output, {"continue": "persist_plot", "stop_on_error": END})
        self.workflow.add_conditional_edges("persist_plot", _check_node_output, {"continue": "character_sculptor", "stop_on_error": END})

        # Character sculptor now leads to selection, then persistence
        self.workflow.add_conditional_edges("character_sculptor", _check_node_output, {"continue": "present_character_options_for_selection", "stop_on_error": END})
        self.workflow.add_conditional_edges("present_character_options_for_selection", _check_workflow_pause_status, {"WORKFLOW_PAUSED": END, "continue_workflow": "persist_selected_characters"})
        self.workflow.add_conditional_edges("persist_selected_characters", _check_node_output, {"continue": "lore_keeper_initialize", "stop_on_error": END})

        self.workflow.add_conditional_edges("lore_keeper_initialize", _check_node_output, {"continue": "prepare_for_chapter_loop", "stop_on_error": END})

        # Chapter Loop Start (from prepare_for_chapter_loop or increment_chapter_number)
        # Instead of going directly to context_synthesizer, it first checks if a twist should be generated.
        self.workflow.add_conditional_edges("prepare_for_chapter_loop", _check_node_output, {"continue": "_should_generate_twist", "stop_on_error": END})

        self.workflow.add_conditional_edges(
            "_should_generate_twist",
            _should_generate_twist,
            {
                "generate_twist": "execute_plot_twist_agent",
                "skip_twist": "context_synthesizer" # Skip to normal chapter flow
            }
        )

        self.workflow.add_conditional_edges("execute_plot_twist_agent", _check_node_output, {"continue": "present_plot_twist_options_for_selection", "stop_on_error": "context_synthesizer"}) # If twist agent errors, fallback to normal flow
        self.workflow.add_conditional_edges("present_plot_twist_options_for_selection", _check_workflow_pause_status, {"WORKFLOW_PAUSED": END, "continue_workflow": "apply_selected_plot_twist"})
        self.workflow.add_conditional_edges("apply_selected_plot_twist", _check_node_output, {"continue": "context_synthesizer", "stop_on_error": END}) # After applying twist, proceed to context for (potentially new) chapter

        # Regular chapter flow nodes
        self.workflow.add_conditional_edges("context_synthesizer", _check_node_output, {"continue": "chapter_chronicler", "stop_on_error": END})
        self.workflow.add_conditional_edges("chapter_chronicler", _check_node_output, {"continue": "content_integrity_review", "stop_on_error": END})

        # content_integrity_review now goes to _check_node_output first, then to should_retry_chapter
        self.workflow.add_conditional_edges("content_integrity_review", _check_node_output, {
            "continue": "should_retry_chapter", # Output of content_integrity_review goes to should_retry_chapter
            "stop_on_error": END
        })

        # should_retry_chapter conditional edges
        self.workflow.add_conditional_edges(
            "should_retry_chapter",
            _should_retry_chapter,
            {
                "retry_chapter": "context_synthesizer",
                "initiate_manual_review": "prepare_for_manual_chapter_review", # New path
                "proceed_to_kb_update": "lore_keeper_update_kb"
            }
        )

        # Edges for prepare_for_manual_chapter_review
        # This node now uses a dedicated router function to handle both pausing and resuming logic.
        self.workflow.add_conditional_edges(
            "prepare_for_manual_chapter_review",
            _route_after_prepare_manual_review,
            {
                "PAUSE_FOR_USER": END, # If pausing, end this graph run.
                "RESUME_TO_REINTEGRITY_REVIEW": "content_integrity_review", # If resumed and chose edit
                "RESUME_TO_KB_UPDATE": "lore_keeper_update_kb" # If resumed and chose use_as_is
            }
        )

        self.workflow.add_conditional_edges("lore_keeper_update_kb", _check_node_output, {"continue": "conflict_detection", "stop_on_error": END})

        # Conflict detection now goes to a decision node
        self.workflow.add_conditional_edges("conflict_detection", _check_node_output, {"continue": "_decide_after_conflict_detection", "stop_on_error": END})

        # Decision node after conflict detection
        self.workflow.add_conditional_edges(
            "_decide_after_conflict_detection",
            _decide_after_conflict_detection,
            {
                "resolve_conflicts_auto": "execute_conflict_resolution_auto",
                "human_api_conflict_pending": "prepare_conflict_review_for_api", # Now points to the new node
                "proceed_to_increment": "increment_chapter_number"
            }
        )

        # After auto-resolution, proceed to increment chapter
        self.workflow.add_conditional_edges("execute_conflict_resolution_auto", _check_node_output, {"continue": "increment_chapter_number", "stop_on_error": END})

        # After preparing for API review, check pause status (should pause)
        self.workflow.add_conditional_edges("prepare_conflict_review_for_api", _check_workflow_pause_status, {
            "WORKFLOW_PAUSED": END,
            # If it doesn't pause (e.g. error in prepare_conflict_review_for_api before setting pause status),
            # or if it's resuming and processed the decision, it should continue.
            # The node itself will change workflow_status from "paused_..." to "running_..." if resuming.
            "continue_workflow": "increment_chapter_number" # Path if resuming and decision processed
        })

        self.workflow.add_conditional_edges(
            "increment_chapter_number", _should_continue_chapter_loop, # _should_continue_chapter_loop decides where to go next
            {
                "continue_loop": "_should_generate_twist", # Back to check for twist before next chapter
                "end_loop": "cleanup_resources",
                "end_loop_on_error": "cleanup_resources",
                "end_loop_on_safety": "cleanup_resources"
            }
        )
        self.workflow.add_conditional_edges("cleanup_resources", _check_node_output, # type: ignore
                                           {"continue": "generate_kb_visualization_data",
                                            "stop_on_error": "generate_kb_visualization_data"}) # Try to generate data even if cleanup had issues
        self.workflow.add_conditional_edges("generate_kb_visualization_data", _check_node_output,
                                           {"continue": END, "stop_on_error": END})
        print("Workflow graph built.")

    def run_workflow(self, user_input_data: Dict[str, Any]) -> NovelWorkflowState:
        current_history = list(self.initial_history)
        current_history.append(f"Starting workflow with input: {user_input_data}")
        print(f"Starting workflow with input: {user_input_data}")

        # Get number of chapters from user input, default to 3
        num_chapters = user_input_data.get("chapters", 3)
        words_per_chapter = user_input_data.get("words_per_chapter", 1000)
        print(f"INFO: Will generate {num_chapters} chapters with {words_per_chapter} words each")

        initial_state = NovelWorkflowState(
            user_input=UserInput(
                theme=user_input_data.get("theme","A default theme if none provided"),
                style_preferences=user_input_data.get("style_preferences"),
                chapters=num_chapters,  # 新增：传递用户指定的章节数
                words_per_chapter=words_per_chapter,
                auto_mode=user_input_data.get("auto_mode", False),  # 新增：自动模式支持
                interaction_mode=user_input_data.get("interaction_mode", "cli") # Default to cli
            ),
            error_message=None, history=current_history,
            novel_id=None, novel_data=None,
            narrative_outline_text=None, all_generated_outlines=None,
            outline_id=None, outline_data=None, outline_review=None, # Added outline_review
            all_generated_worldviews=None, selected_worldview_detail=None,
            worldview_id=None, worldview_data=None,
            plot_id=None, detailed_plot_data=None, plot_data=None,
            all_generated_character_options=None, # Initialize new field
            selected_detailed_character_profiles=None, # Initialize new field
            saved_characters_db_model=None, # Initialize renamed field
            lore_keeper_initialized=False,
            current_chapter_number=0,
            total_chapters_to_generate=num_chapters,  # Use user-specified number
            generated_chapters=[],
            active_character_ids_for_chapter=None,
            current_chapter_plot_summary=None, # This key is no longer directly set by context_synthesizer for chronicler
            current_plot_focus_for_chronicler=None, # New key
            chapter_brief=None,
            db_name=self.db_name,  # Add db_name to state
            current_chapter_review=None,
            current_chapter_quality_passed=None,
            current_chapter_conflicts=None,
            auto_decision_engine=AutoDecisionEngine() if user_input_data.get("auto_mode", False) else None, # Initialize ADE if auto_mode
            knowledge_graph_data=None,
            # Chapter Retry Mechanism Fields
            current_chapter_retry_count=0,
            max_chapter_retries=user_input_data.get("max_chapter_retries", 1), # Default to 1, allow override from input
            current_chapter_original_content=None,
            current_chapter_feedback_for_retry=None,
            # API Interaction / Human-in-the-loop state
            workflow_status="running", # Initial status
            pending_decision_type=None,
            pending_decision_options=None,
            pending_decision_prompt=None,
            user_made_decision_payload=None,
            original_chapter_content_for_conflict_review=None,
            # Plot Twist State Fields
            available_plot_twist_options=None,
            selected_plot_twist_option=None,
            chapter_number_for_twist=None,
            # Plot Branching State Fields
            available_plot_branch_options=None,
            selected_plot_branch_path=None,
            chapter_number_for_branching=None,
            # Manual Chapter Review State Fields
            chapter_pending_manual_review_id=None,
            chapter_content_for_manual_review=None,
            chapter_review_feedback_for_manual_review=None,
            # 循环安全参数
            loop_iteration_count=0,
            max_loop_iterations=max(10, num_chapters * 3),  # 设置合理的最大迭代次数
            execution_count=0  # 新增：执行计数器初始化
        )

        # Calculate recursion limit based on number of chapters
        # Each chapter needs: context_synthesizer -> chapter_chronicler -> lore_keeper_update_kb -> increment_chapter_number
        # Plus initial setup nodes: ~15 nodes
        # So: 15 + (4 * num_chapters) + buffer
        recursion_limit = max(50, 15 + (4 * num_chapters) + 10)
        print(f"INFO: Setting recursion limit to {recursion_limit} for {num_chapters} chapters")

        try:
            print(f"DEBUG: Starting workflow execution with recursion_limit={recursion_limit}")
            final_state = self.app.invoke(initial_state, {"recursion_limit": recursion_limit})
            print(f"DEBUG: Workflow execution completed successfully")
            if final_state.get('error_message'):
                 print(f"Workflow error: {final_state.get('error_message')}")
            return final_state
        except Exception as e:
            print(f"CRITICAL: Workflow execution failed with exception: {e}")
            import traceback
            traceback.print_exc()
            # 返回一个包含错误信息的状态
            return initial_state.copy().update({"error_message": f"Workflow execution failed: {e}"}) or initial_state

if __name__ == "__main__":
    print("--- Workflow Manager Full Integration Test ---")
    if not os.path.exists(".env") and not os.getenv("OPENAI_API_KEY"):
        print("Creating a dummy .env file for WorkflowManager test (for LLMClient dependent agents)...")
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEY=\"sk-dummykeyforworkflowmanagertest\"\n")
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("CRITICAL: OPENAI_API_KEY not found. Some agents will fail to initialize.")
    elif "dummykey" in os.getenv("OPENAI_API_KEY","").lower():
        print("INFO: Using a DUMMY OPENAI_API_KEY. Real LLM calls will likely fail or be handled by agent mocks if any.")
    else:
        print("INFO: A potentially valid OPENAI_API_KEY is set. Attempting live LLM calls.")

    default_db_name = "novel_workflow_test.db"
    default_chroma_dir = "./novel_workflow_chroma_db"
    import shutil
    if os.path.exists(default_db_name): os.remove(default_db_name)
    if os.path.exists(default_chroma_dir): shutil.rmtree(default_chroma_dir)
    _ = DatabaseManager(db_name=default_db_name)
    manager = WorkflowManager(db_name=default_db_name, mode="auto") # Specify mode
    sample_user_input = {
        "theme": "a detective investigating anomalies in a city where time flows differently in various districts",
        "style_preferences": "chronopunk mystery with noir elements",
        "auto_mode": True, # Ensure this is set for nodes that check it
        "chapters": 2 # Shorten for faster testing
    }
    print(f"\nRunning workflow with: {sample_user_input}")
    final_result_state = manager.run_workflow(sample_user_input)
    print("\n--- Workflow Final State ---")
    for key, value in final_result_state.items():
        if key == "history": print(f"History entries: {len(value)}")
        elif key == "outline_review" and value: # Added to print outline_review
            print("Outline_review:")
            if isinstance(value, dict):
                for r_key, r_value in value.items(): print(f"  {r_key.replace('_',' ').capitalize()}: {r_value}")
            else: print(f"  {value}")
        elif key in ["all_generated_outlines", "all_generated_worldviews", "detailed_plot_data", "generated_chapters", "saved_characters_db_model", "selected_detailed_character_profiles"] and isinstance(value, list):
            print(f"{key.replace('_', ' ').capitalize()}: ({len(value)} items)")
            if value and isinstance(value[0], dict):
                for i, item_dict in enumerate(value):
                    item_summary = item_dict.get('title', item_dict.get('name', f"Item {i+1}")) # 'name' for characters
                    print(f"  - {item_summary} (details in full state if needed)")
            elif value and isinstance(value[0], str): # e.g. for all_generated_outlines
                 for i, item_str in enumerate(value): print(f"  - Outline {i+1} Snippet: {item_str[:70]}...")
        elif key == "all_generated_character_options" and isinstance(value, dict):
            print(f"{key.replace('_', ' ').capitalize()}: ({sum(len(opts) for opts in value.values())} total options for {len(value)} concepts)")
            for concept, opts_list in value.items():
                print(f"  Concept '{concept}': {len(opts_list)} options")
                if opts_list and isinstance(opts_list[0], dict):
                    print(f"    - Option 1 Name: {opts_list[0].get('name', 'N/A')}")
        elif key == "knowledge_graph_data" and value:
            print("Knowledge Graph Data:")
            if isinstance(value, dict):
                print(f"  Nodes found: {len(value.get('nodes', []))}")
                print(f"  Edges found: {len(value.get('edges', []))}")
                if value.get("error"):
                    print(f"  Error generating graph data: {value['error']}")
                # Optionally print a few nodes/edges if needed for quick check
                # for node_item in value.get('nodes', [])[:2]:
                #     print(f"    Sample Node: {node_item.get('id')} - {node_item.get('label')}")
            else:
                print(f"  Unexpected graph data format: {value}")
        elif key == "current_chapter_conflicts" and value:
            print("Last Chapter Conflicts:")
            if isinstance(value, list) and value:
                if len(value) == 1 and value[0].get("error"):
                     print(f"  Error in conflict detection: {value[0]['error']}")
                else:
                    for idx, conflict in enumerate(value):
                        print(f"  Conflict {idx+1}: Type: {conflict.get('type')}, Severity: {conflict.get('severity')}, Desc: {conflict.get('description')}")
            elif not value:
                print("  No conflicts detected or reported.")
            else: # Should be a list or None
                print(f"  Unexpected conflict data: {value}")
        elif key == "current_chapter_review" and value: # For the last chapter processed
            print("Last Chapter Review:")
            if isinstance(value, dict):
                print(f"  Overall Score: {value.get('overall_score')}")
                print(f"  Justification: {value.get('justification')}")
                if value.get('scores'):
                    for r_key, r_value in value['scores'].items():
                        print(f"    {r_key.replace('_',' ').capitalize()}: {r_value}")
                if value.get('error'):
                    print(f"  Error: {value.get('error')}")
            else:
                print(f"  {value}")
        elif key == "current_chapter_quality_passed" and value is not None:
            print(f"Last Chapter Quality Passed: {value}")
        elif isinstance(value, dict):
            print(f"{key.capitalize()}:")
            for k_item, v_item in value.items(): print(f"  {k_item}: {str(v_item)[:100]}{'...' if len(str(v_item)) > 100 else ''}")
        else:
            print(f"{key.capitalize()}: {str(value)[:200]}{'...' if len(str(value)) > 200 else ''}")
    print(f"\nError Message at end of workflow: {final_result_state.get('error_message')}")
    if os.path.exists(default_db_name): os.remove(default_db_name)
    if os.path.exists(default_chroma_dir): shutil.rmtree(default_chroma_dir)
    if os.path.exists(".env"):
        with open(".env", "r") as f_env:
            if "dummykeyforworkflowmanagertest" in f_env.read(): os.remove(".env")
    print("\n--- Workflow Manager Full Integration Test Finished ---")
