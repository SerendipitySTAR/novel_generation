from langgraph.graph import StateGraph, END
from typing import TypedDict, Any, List, Annotated, Dict, Optional
import operator
import os
import json
import gc
from dotenv import load_dotenv
from src.core.auto_decision_engine import AutoDecisionEngine

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
    characters: Optional[List[Character]] # This will become List[DetailedCharacterProfile] after CharacterSculptor update
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
        decision_payload = state.get("user_made_decision_payload")
        if decision_payload and decision_payload.get("selected_option_id"):
            # Resuming from API decision
            try:
                selected_option_id_str = decision_payload["selected_option_id"]
                # Find the selected outline by its ID (which is stringified index+1)
                # This assumes options were presented with ID "1", "2", ...
                selected_outline_text = None
                original_options = state.get("all_generated_outlines", [])
                for i, outline_text_option in enumerate(original_options):
                    if str(i+1) == selected_option_id_str:
                        selected_outline_text = outline_text_option
                        selected_index = i # For logging
                        break

                if selected_outline_text is None:
                    raise ValueError(f"Selected option ID '{selected_option_id_str}' not found in available outlines.")

                log_msg = f"API Mode: Resumed with selected Outline {selected_index + 1}."
                history = _log_and_update_history(history, log_msg)
                state["narrative_outline_text"] = selected_outline_text
                state["user_made_decision_payload"] = None # Clear consumed decision
                state["workflow_status"] = "running_after_outline_decision"
                # Clear pending decision fields that were set for pausing
                state["pending_decision_type"] = None
                state["pending_decision_options"] = None
                state["pending_decision_prompt"] = None
                state["history"] = history
                state["error_message"] = None
                state["execution_count"] = execution_count
                return state
            except (ValueError, TypeError) as e:
                msg = f"API Mode: Error processing outline decision: {e}. Invalid payload: {decision_payload}"
                state["error_message"] = msg
                state["history"] = _log_and_update_history(history, msg, True)
                state["execution_count"] = execution_count
                return state # Error state will be caught by _check_node_output
        else:
            # Pausing for API decision
            options_for_api = []
            for i, outline_text_option in enumerate(all_outlines):
                options_for_api.append({
                    "id": str(i + 1), # API decision will refer to this ID
                    "text_summary": outline_text_option[:150] + "...",
                    "full_data": outline_text_option
                })
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
                # Create a serializable version of the state for JSON dump
                # This is tricky because state can contain non-serializable objects like agent instances
                # For now, we'll attempt a direct dump, but this might need a custom encoder or selective serialization
                serializable_state = {k: v for k, v in state.items() if isinstance(v, (type(None), str, int, float, bool, list, dict))}
                state_json = json.dumps(serializable_state) # Might fail if state has complex objects
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
        decision_payload = state.get("user_made_decision_payload")
        if decision_payload and decision_payload.get("selected_option_id"):
            # Resuming from API decision
            try:
                selected_option_id_str = decision_payload["selected_option_id"]
                selected_wv_detail = None
                original_options = state.get("all_generated_worldviews", [])
                for i, wv_option in enumerate(original_options):
                    if str(i+1) == selected_option_id_str:
                        selected_wv_detail = wv_option
                        selected_index = i # for logging
                        break

                if selected_wv_detail is None:
                    raise ValueError(f"Selected option ID '{selected_option_id_str}' not found in available worldviews.")

                log_msg = f"API Mode: Resumed with selected Worldview {selected_index + 1} ('{selected_wv_detail.get('world_name', 'N/A')}')."
                history = _log_and_update_history(history, log_msg)
                state["selected_worldview_detail"] = selected_wv_detail
                state["user_made_decision_payload"] = None # Clear consumed decision
                state["workflow_status"] = "running_after_worldview_decision"
                # Clear pending decision fields
                state["pending_decision_type"] = None
                state["pending_decision_options"] = None
                state["pending_decision_prompt"] = None
                state["history"] = history
                state["error_message"] = None
                return state # Return the full state dict
            except (ValueError, TypeError) as e:
                msg = f"API Mode: Error processing worldview decision: {e}. Invalid payload: {decision_payload}"
                state["error_message"] = msg
                state["history"] = _log_and_update_history(history, msg, True)
                return state # Error state will be caught by _check_node_output
        else:
            # Pausing for API decision
            options_for_api = []
            for i, wv_detail_option in enumerate(all_worldviews):
                options_for_api.append({
                    "id": str(i + 1),
                    "text_summary": f"{wv_detail_option.get('world_name', 'N/A')} - {wv_detail_option.get('core_concept', 'N/A')[:100]}...",
                    "full_data": wv_detail_option
                })
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
                serializable_state = {k: v for k, v in state.items() if isinstance(v, (type(None), str, int, float, bool, list, dict))}
                state_json = json.dumps(serializable_state)
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
        # The CharacterSculptorAgent now returns List[DetailedCharacterProfile]
        characters_profiles = agent.generate_and_save_characters(
            novel_id=novel_id, narrative_outline=outline['overview_text'],
            worldview_data_core_concept=worldview_text_for_chars, plot_summary_str=plot_summary_for_chars,
            character_concepts=character_concepts
        )
        if characters_profiles: # Check if list is not empty
            history = _log_and_update_history(history, f"Generated and saved {len(characters_profiles)} detailed character profiles.")
            # The 'characters' field in state should now hold List[DetailedCharacterProfile]
            return {"characters": characters_profiles, "history": history, "error_message": None}
        else:
            msg = "Character Sculptor Agent failed to generate characters."
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

        # characters state now holds List[DetailedCharacterProfile]
        # LoreKeeperAgent's initialize_knowledge_base expects List[Character] (the DB model)
        # We need to adapt this. For now, we can create basic Character objects for KB init
        # or update LoreKeeperAgent to handle DetailedCharacterProfile.
        # For this step, let's pass the detailed profiles, assuming LoreKeeper can extract name/role/description.
        character_details_for_kb = state["characters"]

        if not all([novel_id, outline, worldview_db_object, plot_db_object, character_details_for_kb is not None]):
            msg = "Missing data for Lore Keeper initialization."
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
        # characters state now holds List[DetailedCharacterProfile]
        character_profiles = state.get("characters", [])

        if not all([novel_id is not None, detailed_plot, character_profiles is not None]):
            msg = "Missing data for Context Synthesizer (novel_id, detailed_plot_data, characters)."
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
            if state.get("current_chapter_retry_count", 0) > 0:
                feedback_for_retry = state.get("current_chapter_feedback_for_retry")
                if feedback_for_retry:
                    retry_message = (
                        f"\n\n--- IMPORTANT: THIS IS A RETRY ATTEMPT (Attempt {state['current_chapter_retry_count']}) ---\n"
                        f"Feedback from the previous attempt's quality review:\n"
                        f"{feedback_for_retry}\n"
                        f"Please carefully review this feedback and address all points in this new version of the chapter.\n"
                        f"--- END OF RETRY FEEDBACK ---\n"
                    )
                    chapter_brief_text += retry_message
                    history = _log_and_update_history(history, f"Appended retry feedback to chapter brief for Chapter {current_chapter_num}.")
                    print(f"INFO: Appended retry feedback to brief for Chapter {current_chapter_num}, Retry Attempt: {state['current_chapter_retry_count']}")

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
            # Still clear retry-specific fields even if KB update fails, as we are moving on from this chapter attempt
            return {
                "history": history,
                "error_message": None, # 不设置error_message，允许继续
                "current_chapter_original_content": None,
                "current_chapter_feedback_for_retry": None
            }

    except Exception as e:
        msg = f"Error in Lore Keeper Update KB node for Chapter {current_chapter_num}: {e}"
        # Also clear retry fields in case of other errors in this node before returning
        return {
            "error_message": msg,
            "history": _log_and_update_history(history, msg, True),
            "current_chapter_original_content": None,
            "current_chapter_feedback_for_retry": None
        }

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
        "history": history,
        "error_message": None
    }
    print(f"DEBUG: increment_chapter_number - Reset retry count to 0 for the new chapter {new_num}.")
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

        if passed_quality_check:
            history = _log_and_update_history(history, f"Chapter '{chapter_title}' PASSED quality check (Score: {overall_score} >= Threshold: {quality_threshold}).")
            print(f"INFO: Chapter '{chapter_title}' PASSED quality check (Score: {overall_score} >= Threshold: {quality_threshold}).")
        else:
            history = _log_and_update_history(history, f"Chapter '{chapter_title}' FAILED quality check (Score: {overall_score} < Threshold: {quality_threshold}).")
            print(f"WARNING: Chapter '{chapter_title}' FAILED quality check (Score: {overall_score} < Threshold: {quality_threshold}).")
            # Store original content and feedback for retry
            current_chapter_original_content = chapter_content
            feedback_summary = f"Review Justification: {review_results.get('justification', 'N/A')}. " \
                               f"Overall Score: {overall_score}. " \
                               f"Detailed Scores: {review_results.get('scores', {})}"
            current_chapter_feedback_for_retry = feedback_summary
            history = _log_and_update_history(history, f"Stored original content and feedback for potential retry of chapter '{chapter_title}'.")

        # Update state
        result = dict(state)
        result.update({
            "current_chapter_review": review_results,
            "current_chapter_quality_passed": passed_quality_check,
            "current_chapter_original_content": current_chapter_original_content if not passed_quality_check else None,
            "current_chapter_feedback_for_retry": current_chapter_feedback_for_retry if not passed_quality_check else None,
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
        serializable_state = {k: v for k, v in state.items() if isinstance(v, (type(None), str, int, float, bool, list, dict))}
        full_state_json = json.dumps(serializable_state)

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
        return "proceed_to_increment"


def _should_retry_chapter(state: NovelWorkflowState) -> str:
    """
    Determines if the current chapter should be retried based on quality and retry limits.
    """
    history = _log_and_update_history(state.get("history", []), "Conditional Node: Should Retry Chapter?")
    print("DEBUG: _should_retry_chapter - Function called")

    auto_mode = state.get("user_input", {}).get("auto_mode", False)
    quality_passed = state.get("current_chapter_quality_passed", True) # Default to True to avoid accidental retries
    current_retry_count = state.get("current_chapter_retry_count", 0)
    max_retries = state.get("max_chapter_retries", 1)

    print(f"DEBUG: _should_retry_chapter - Auto Mode: {auto_mode}, Quality Passed: {quality_passed}, Retries: {current_retry_count}/{max_retries}")

    if auto_mode and not quality_passed and current_retry_count < max_retries:
        new_retry_count = current_retry_count + 1
        state["current_chapter_retry_count"] = new_retry_count # Update state directly
        history = _log_and_update_history(history, f"Chapter failed quality. Incrementing retry count to {new_retry_count}. Will attempt retry.")
        print(f"INFO: Chapter retry {new_retry_count}/{max_retries} will be attempted.")
        state["history"] = history # Persist history update
        return "retry_chapter"
    else:
        if auto_mode and not quality_passed and current_retry_count >= max_retries:
            history = _log_and_update_history(history, f"Chapter failed quality, but max retries ({max_retries}) reached. Proceeding without retry.")
            print(f"WARNING: Max retries reached for chapter. Proceeding without further retries.")
        elif not auto_mode and not quality_passed:
            history = _log_and_update_history(history, "Chapter failed quality, but not in auto_mode. Proceeding without retry.")
            print("INFO: Chapter failed quality, but not in auto_mode. No retry.")
        elif quality_passed:
            history = _log_and_update_history(history, "Chapter passed quality check. Proceeding.")
            print("INFO: Chapter passed quality. No retry needed.")

        # Reset retry count for the next chapter in all cases where we don't retry
        state["current_chapter_retry_count"] = 0
        state["history"] = history # Persist history update
        print("DEBUG: _should_retry_chapter - Resetting retry count to 0 for next chapter.")
        return "proceed_to_kb_update"

class WorkflowManager:
    def __init__(self, db_name="novel_mvp.db", mode="human"): # mode is now less relevant here, user_input drives it.
        self.db_name = db_name
        # self.mode = mode # Keep for now if auto_decision_engine relies on it
        # self.auto_decision_engine = AutoDecisionEngine() if self.mode == "auto" else None
        # The auto_decision_engine should be part of the state if it's mode-dependent
        # For now, assume it's instantiated if needed based on state.user_input.auto_mode

        print(f"WorkflowManager initialized (DB: {self.db_name}).")
        self.initial_history = [f"WorkflowManager initialized (DB: {self.db_name}) and graph compiled."]
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

        # It's expected that user_made_decision_payload_json was set by API via record_user_decision
        # And that pending_decision_type was cleared by record_user_decision
        # So, the state loaded from DB should reflect that a decision *was* made.
        # The decision_payload_from_api is the source of truth for applying the decision here.

        # Basic validation (API layer should do more thorough validation against stored pending_decision_type)
        # This is a sanity check within the resume logic.
        # The `record_user_decision` in DB manager might have already cleared `pending_decision_type`
        # so `current_state_snapshot["pending_decision_type"]` might be None here if loaded from DB after `record_user_decision`.
        # The crucial part is that the API called this `resume_workflow` with the correct `decision_type_from_api`.

        # Store the raw decision payload for the target node to process
        current_state_snapshot["user_made_decision_payload"] = {"source_decision_type": decision_type_from_api, **decision_payload_from_api}

        if decision_type_from_api == "conflict_review":
            original_content = current_state_snapshot.get("original_chapter_content_for_conflict_review")
            conflicts_at_pause = current_state_snapshot.get("current_chapter_conflicts", []) # These are the conflicts presented to user

            # Correctly access action directly from the payload
            action = decision_payload_from_api.get("action")
            conflict_id_from_payload = decision_payload_from_api.get("conflict_id")
            suggestion_index_from_payload = decision_payload_from_api.get("suggestion_index")
            user_comment = decision_payload_from_api.get("user_comment") # Log this if present

            history = current_state_snapshot.get("history", [])
            if user_comment:
                history = _log_and_update_history(history, f"User comment on conflict resolution action '{action}': {user_comment}")
                current_state_snapshot["history"] = history

            # This is the text that might have been modified by *previous* actions in the same review session
            current_chapter_text_being_edited = current_state_snapshot.get("generated_chapters", [])[-1]["content"]

            # This is the list of conflicts as presented to the user, potentially with 'llm_suggestions'
            # We need to update this list in-place for 'resolution_status' for re-pausing.
            # The options are List[DecisionOption] from API, which has full_data as the conflict dict
            # So, pending_decision_options is List[Dict] where each dict is a DecisionOption structure.
            # The actual conflict is in 'full_data' of that.
            current_conflicts_for_review = current_state_snapshot.get("pending_decision_options", [])


            if action == "apply_suggestion":
                if not conflict_id_from_payload or suggestion_index_from_payload is None:
                    current_state_snapshot["error_message"] = "apply_suggestion action requires conflict_id and suggestion_index."
                else:
                    target_conflict_option = next((c for c in current_conflicts_for_review if c["id"] == conflict_id_from_payload), None)
                    if target_conflict_option and target_conflict_option["full_data"]:
                        target_conflict_dict = target_conflict_option["full_data"] # This is the actual conflict dict
                        original_excerpt = target_conflict_dict.get("excerpt")
                        suggestions = target_conflict_dict.get("llm_suggestions", [])
                        if original_excerpt and 0 <= suggestion_index_from_payload < len(suggestions):
                            chosen_suggestion_text = suggestions[suggestion_index_from_payload]

                            excerpt_start_index = current_chapter_text_being_edited.find(original_excerpt)
                            if excerpt_start_index != -1:
                                before_excerpt = current_chapter_text_being_edited[:excerpt_start_index]
                                after_excerpt = current_chapter_text_being_edited[excerpt_start_index + len(original_excerpt):]
                                current_chapter_text_being_edited = before_excerpt + chosen_suggestion_text + after_excerpt

                                current_state_snapshot["generated_chapters"][-1]["content"] = current_chapter_text_being_edited
                                target_conflict_dict["resolution_status"] = "applied_suggestion"
                                target_conflict_dict["applied_suggestion_text"] = chosen_suggestion_text
                                history = _log_and_update_history(history, f"Applied suggestion for conflict {conflict_id_from_payload}.")
                                current_state_snapshot["history"] = history
                            else:
                                history = _log_and_update_history(history, f"Warning: Original excerpt for conflict {conflict_id_from_payload} not found in current text. Suggestion not applied.", True)
                                target_conflict_dict["resolution_status"] = "apply_failed_excerpt_not_found"
                        else:
                             history = _log_and_update_history(history, f"Warning: Invalid suggestion index or missing excerpt for conflict {conflict_id_from_payload}.", True)
                             if target_conflict_dict: target_conflict_dict["resolution_status"] = "apply_failed_invalid_suggestion"
                    else:
                        history = _log_and_update_history(history, f"Warning: Conflict ID {conflict_id_from_payload} not found for applying suggestion.", True)
                # After applying one suggestion, we re-pause to show updated state.
                current_state_snapshot["workflow_status"] = f"paused_for_conflict_review_ch_{current_state_snapshot.get('current_chapter_number')}"
                # The user_made_decision_payload needs to signal to prepare_conflict_review_for_api that an action was taken
                current_state_snapshot["user_made_decision_payload"]["action_taken_in_resume"] = "apply_suggestion"


            elif action == "ignore_conflict":
                if not conflict_id_from_payload:
                    current_state_snapshot["error_message"] = "ignore_conflict action requires conflict_id."
                else:
                    target_conflict_option = next((c for c in current_conflicts_for_review if c["id"] == conflict_id_from_payload), None)
                    if target_conflict_option and target_conflict_option["full_data"]:
                        target_conflict_option["full_data"]["resolution_status"] = "ignored_by_user"
                        history = _log_and_update_history(history, f"Conflict {conflict_id_from_payload} marked as ignored.")
                        current_state_snapshot["history"] = history
                    else:
                        history = _log_and_update_history(history, f"Warning: Conflict ID {conflict_id_from_payload} not found for ignoring.", True)
                current_state_snapshot["workflow_status"] = f"paused_for_conflict_review_ch_{current_state_snapshot.get('current_chapter_number')}"
                current_state_snapshot["user_made_decision_payload"]["action_taken_in_resume"] = "ignore_conflict"


            elif action == "rewrite_all_auto_remaining":
                history = _log_and_update_history(history, "Attempting auto-resolve for remaining unresolved conflicts.")
                current_state_snapshot["history"] = history

                unresolved_conflicts = [
                    c["full_data"] for c in current_conflicts_for_review
                    if not c.get("full_data", {}).get("resolution_status")
                ]
                if unresolved_conflicts:
                    llm_client = LLMClient()
                    resolver_agent = ConflictResolutionAgent(llm_client=llm_client, db_name=self.db_name)
                    novel_context = current_state_snapshot.get("user_input")

                    revised_text = resolver_agent.attempt_auto_resolve(
                        novel_id, current_chapter_text_being_edited, unresolved_conflicts, novel_context=novel_context
                    )
                    if revised_text and revised_text != current_chapter_text_being_edited:
                        current_state_snapshot["generated_chapters"][-1]["content"] = revised_text
                        history = _log_and_update_history(history, "Chapter text modified by 'rewrite_all_auto_remaining'.")
                        current_state_snapshot["history"] = history
                    else:
                         history = _log_and_update_history(history, "'rewrite_all_auto_remaining' made no changes to text.")
                         current_state_snapshot["history"] = history
                else:
                    history = _log_and_update_history(history, "No unresolved conflicts found for 'rewrite_all_auto_remaining'.")
                    current_state_snapshot["history"] = history

                # This action implies we are done with this pause cycle.
                current_state_snapshot["workflow_status"] = "running_after_conflict_review"
                current_state_snapshot["pending_decision_type"] = None
                current_state_snapshot["pending_decision_options"] = None
                current_state_snapshot["pending_decision_prompt"] = None
                current_state_snapshot["original_chapter_content_for_conflict_review"] = None
                current_state_snapshot["current_chapter_conflicts"] = [] # Assume all processed or remaining are accepted as is after auto attempt.
                current_state_snapshot["user_made_decision_payload"]["action_taken_in_resume"] = "rewrite_all_auto_remaining"


            elif action == "proceed_with_remaining":
                history = _log_and_update_history(history, "Proceeding with remaining conflicts as they are.")
                current_state_snapshot["history"] = history
                # Mark all remaining unresolved conflicts
                for c_option in current_conflicts_for_review:
                    if not c_option.get("full_data",{}).get("resolution_status"):
                        c_option["full_data"]["resolution_status"] = "proceeded_without_change"

                current_state_snapshot["workflow_status"] = "running_after_conflict_review"
                current_state_snapshot["pending_decision_type"] = None
                current_state_snapshot["pending_decision_options"] = None # Cleared as we are proceeding
                current_state_snapshot["pending_decision_prompt"] = None
                current_state_snapshot["original_chapter_content_for_conflict_review"] = None
                # current_chapter_conflicts might remain as is in state if some were ignored/proceeded, for record keeping,
                # but they won't be presented again for this pause cycle. Or clear them. Let's clear.
                current_state_snapshot["current_chapter_conflicts"] = []
                current_state_snapshot["user_made_decision_payload"]["action_taken_in_resume"] = "proceed_with_remaining"

            else: # Default or unknown action
                history = _log_and_update_history(history, f"Unknown action '{action}' for conflict review. Defaulting to re-pause.")
                current_state_snapshot["history"] = history
                current_state_snapshot["workflow_status"] = f"paused_for_conflict_review_ch_{current_state_snapshot.get('current_chapter_number')}"
                current_state_snapshot["user_made_decision_payload"]["action_taken_in_resume"] = "unknown_action"


            # If an individual action was taken ("apply_suggestion", "ignore_conflict") that might re-pause,
            # we need to update the pending_decision_options in the snapshot before saving it via update_novel_pause_state later.
            if current_state_snapshot["workflow_status"].startswith("paused_for_conflict_review"):
                 current_state_snapshot["pending_decision_options"] = current_conflicts_for_review # Save updated statuses

        # Common state updates for any decision type before re-invocation (some might be overridden by conflict logic)
        if not current_state_snapshot["workflow_status"].startswith("paused_for_"): # If not specifically re-paused by conflict logic
            current_state_snapshot["workflow_status"] = f"resuming_after_{decision_type_from_api}"
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
        final_snapshot_json_for_db = json.dumps({k: v for k, v in final_state_after_resume.items() if isinstance(v, (type(None), str, int, float, bool, list, dict))})

        if final_status and final_status.startswith("paused_for_"):
            # If it paused again, update_novel_pause_state will be called from the decision node itself.
            # So, this specific call might be redundant if the decision node handles its own pause saving.
            # However, if invoke ends due to recursion limit before hitting a save point, this save is crucial.
            print(f"Workflow for novel {novel_id} resumed and then paused again for: {final_status}")
            # The decision node (e.g. present_outlines_cli) should have already saved its pause state.
            # If we save here, ensure it's the absolute latest state.
            # db_manager.update_novel_pause_state(
            #     novel_id, final_status,
            #     final_state_after_resume.get("pending_decision_type"),
            #     json.dumps(final_state_after_resume.get("pending_decision_options")) if final_state_after_resume.get("pending_decision_options") else None,
            #     final_state_after_resume.get("pending_decision_prompt"),
            #     final_snapshot_json_for_db
            # )
        else: # Completed, failed, or other terminal/intermediate state that isn't a formal pause
            print(f"Workflow for novel {novel_id} resumed. Final status: {final_status}.")
            db_manager.update_novel_status_after_resume(novel_id, final_status, final_snapshot_json_for_db)

        return final_state_after_resume

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
        self.workflow.add_node("lore_keeper_initialize", execute_lore_keeper_initialize)
        self.workflow.add_node("prepare_for_chapter_loop", prepare_for_chapter_loop)
        self.workflow.add_node("context_synthesizer", execute_context_synthesizer_agent)
        self.workflow.add_node("chapter_chronicler", execute_chapter_chronicler_agent)
        self.workflow.add_node("content_integrity_review", execute_content_integrity_review)
        self.workflow.add_node("should_retry_chapter", _should_retry_chapter) # New conditional node
        self.workflow.add_node("lore_keeper_update_kb", execute_lore_keeper_update_kb)
        self.workflow.add_node("conflict_detection", execute_conflict_detection)
        self.workflow.add_node("execute_conflict_resolution_auto", execute_conflict_resolution_auto)
        self.workflow.add_node("prepare_conflict_review_for_api", prepare_conflict_review_for_api) # New node
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

        # Updated edges for Quality Guardian
        self.workflow.add_conditional_edges("persist_initial_outline", _check_node_output, {"continue": "outline_quality_guardian", "stop_on_error": END})
        self.workflow.add_conditional_edges("outline_quality_guardian", _check_node_output, {"continue": "world_weaver", "stop_on_error": END})

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
        self.workflow.add_conditional_edges("character_sculptor", _check_node_output, {"continue": "lore_keeper_initialize", "stop_on_error": END})
        self.workflow.add_conditional_edges("lore_keeper_initialize", _check_node_output, {"continue": "prepare_for_chapter_loop", "stop_on_error": END})
        self.workflow.add_conditional_edges("prepare_for_chapter_loop", _check_node_output, {"continue": "context_synthesizer", "stop_on_error": END})
        self.workflow.add_conditional_edges("context_synthesizer", _check_node_output, {"continue": "chapter_chronicler", "stop_on_error": END})
        self.workflow.add_conditional_edges("chapter_chronicler", _check_node_output, {"continue": "content_integrity_review", "stop_on_error": END})
        # content_integrity_review now goes to should_retry_chapter
        self.workflow.add_conditional_edges("content_integrity_review", _check_node_output, {"continue": "should_retry_chapter", "stop_on_error": END})
        # should_retry_chapter branches
        self.workflow.add_conditional_edges("should_retry_chapter", _should_retry_chapter, {
            "retry_chapter": "context_synthesizer", # Loop back to context synthesizer
            "proceed_to_kb_update": "lore_keeper_update_kb"
        })
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
            "increment_chapter_number", _should_continue_chapter_loop,
            {
                "continue_loop": "context_synthesizer",
                "end_loop": "cleanup_resources",
                "end_loop_on_error": "cleanup_resources",
                "end_loop_on_safety": "cleanup_resources"  # 新增安全退出条件
            }
        )
        self.workflow.add_conditional_edges("cleanup_resources", _check_node_output,
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
            characters=None, lore_keeper_initialized=False,
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
            auto_decision_engine=self.auto_decision_engine, # Add this line
            knowledge_graph_data=None,
            # Chapter Retry Mechanism Fields
            current_chapter_retry_count=0,
            max_chapter_retries=1, # Default to 1 retry
            current_chapter_original_content=None,
            current_chapter_feedback_for_retry=None,
            # API Interaction / Human-in-the-loop state
            workflow_status="running", # Initial status
            pending_decision_type=None,
            pending_decision_options=None,
            pending_decision_prompt=None,
            user_made_decision_payload=None,
            original_chapter_content_for_conflict_review=None,
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
        elif key in ["all_generated_outlines", "all_generated_worldviews", "detailed_plot_data", "generated_chapters", "characters"] and isinstance(value, list):
            print(f"{key.replace('_', ' ').capitalize()}: ({len(value)} items)")
            if value and isinstance(value[0], dict):
                for i, item_dict in enumerate(value):
                    item_summary = item_dict.get('title', item_dict.get('name', f"Item {i+1}"))
                    print(f"  - {item_summary} (details in full state if needed)")
            elif value and isinstance(value[0], str):
                 for i, item_str in enumerate(value): print(f"  - Outline {i+1} Snippet: {item_str[:70]}...")
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
