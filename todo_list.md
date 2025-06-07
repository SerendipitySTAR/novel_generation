# Project Todo List (Based on README.md)

This document tracks the implementation status of features and components described in the main `README.md`.

**Legend:**
*   `[x]` DONE: Feature is implemented as per MVP requirements or initial description.
*   `[p]` PARTIALLY DONE: Basic structure exists, but requires further development, real LLM integration, or full feature implementation.
*   `[ ]` TODO: Feature or component has not been started or is minimally stubbed.

---

## 1. Core Architecture Layers

*   **[p] User Input & Interaction Layer (UIL - README 4.1)**
    *   `[x]` Basic CLI for user input (theme, style) via `main.py`.
    *   `[ ]` Structure user input for the orchestration layer (Implicitly DONE via CLI args).
    *   `[p]` Present AI-generated options...to user (CLI selection for outlines & worldviews implemented; broader multi-option/scoring TODO).
    *   `[ ]` Text editor for user modifications (TODO).
    *   `[ ]` User session management (TODO).
    *   [p] Web UI (FastAPI backend initiated with core endpoints for novel generation start, status, and KB visualization. Frontend TODO).
*   **[x] Orchestration & Workflow Layer (OLC - README 4.2)**
    *   `[x]` LangGraph based `WorkflowManager` implemented.
    *   `[x]` Manages sequence for outline, worldview, plot, characters, and chapter loop.
    *   `[x]` Includes CLI-based user selection nodes for outlines and worldviews.
    *   `[p]` Integration of `QualityGuardianAgent` for informational review of outlines (review displayed in CLI; no workflow branching yet).
    *   `[p]` Conditional branching (Basic error handling exists. Complex branching based on scores/user input TODO).
    *   `[x]` Chapter generation loop structure implemented.
    *   `[x]` Global state management within workflow (MVP level).
    *   [p] Automated chapter quality control via ContentIntegrityAgent scores, including a retry mechanism for low-quality chapters in Auto-Mode.
    *   [p] Integration of human input nodes for user decisions (WorkflowManager decision nodes updated to support pausing for API-driven human mode; state saved to DB. API endpoints for querying/submitting decisions implemented. Full E2E flow for API human decisions needs testing & refinement).
    *   [p] Mode-specific conflict handling: Auto-Mode now attempts auto-resolution via (stub) `ConflictResolutionAgent`. Human-Mode (API) now prepares conflict data using (stub) `ConflictResolutionAgent` and pauses for user decision via API.
*   **[p] Agent Layer (AL - README 4.3)**
    *   (Individual agent status below)
*   **[x] LLM Abstraction Layer (LLMAL - README 4.5)**
    *   `[x]` `LLMClient` for OpenAI API implemented.
    *   `[p]` Management of different models/configs (Basic model name passing; enhanced error logging for API issues implemented).
    *   `[p]` API retry, error handling, rate limiting (Enhanced error logging in LLMClient; specific retry/rate limit logic TODO).
    *   `[ ]` Support for local models (TODO).
    *   [ ] LLM Caching (Deprioritized due to local model usage and quality focus).
*   **[p] Knowledge Base Layer (KBL - README 4.4 & 6)**
    *   `[x]` `KnowledgeBaseManager` for RAG using ChromaDB implemented.
    *   `[p]` Vector DB (ChromaDB) for RAG: Stores text chunks from agents. (Live embedding calls implemented; full functionality requires real API key).
    *   `[ ]` Knowledge Graph (KG) for structured facts (TODO).
    *   [p] Knowledge Base Visualization (Backend API endpoint `/novels/{novel_id}/knowledge_graph` implemented to serve data from LoreKeeperAgent. Frontend visualization TODO).
    *   `[x]` SQL DB for storing `KnowledgeBaseEntry` metadata.
*   **[x] Data Persistence Layer (DPL - README 4.6)**
    *   `[x]` `DatabaseManager` for SQLite implemented.
    *   `[x]` Schema for novels, outlines, worldviews, plots (stores List[PlotChapterDetail] as JSON), characters (stores each character's DetailedCharacterProfile as JSON in `description` field), chapters, kb_entries; Novels table extended with fields for workflow_status, pending_decision_info, and full_workflow_state_json to support resumable workflows.
    *   `[ ]` User info/auth storage (TODO).
    *   `[ ]` Versioning of generated content (TODO).
    *   `[ ]` Storing user edits/selections (TODO).

## 2. Agents (from README 4.3)

*   **[p] Narrative Pathfinder Agent (概述智能体 - README 4.3.1)**
    *   `[x]` Basic agent structure in `src/agents/narrative_pathfinder_agent.py`.
    *   `[p]` Generates multiple core creative overviews (MVP: 2). Workflow selects the first via CLI user prompt. (Live LLM call fully enabled; prompt refined; README specifies 3-5 options, 500-1000 words, further UI for selection TODO).
    *   `[ ]` Expand selected overview to detailed plot synopsis (README optional item).
    *   `[ ]` User selection from multiple overviews (TODO for more advanced UI than CLI default).
*   **[p] World Weaver Agent (世界观智能体 - README 4.3.2)**
    *   `[x]` Basic agent structure in `src/agents/world_weaver_agent.py`.
    *   `[p]` Generates multiple structured worldview options (`WorldviewDetail` TypedDict). CLI selection integrated. (Live LLM call enabled; prompt & parsing for simple structure implemented; README specifies 3-5 options, further detail/refinement TODO).
    *   `[ ]` Output in specified structured format (partially, current mock is just text).
    *   `[ ]` User selection/editing of structured worldview (TODO).
*   **[p] Plot Architect Agent (大纲智能体 - README 4.3.3)**
    *   `[x]` Basic agent structure in `src/agents/plot_architect_agent.py`.
    *   `[p]` Enhanced for detailed chapter structures (`PlotChapterDetail`). (Live LLM call implemented. Prompt and parser underwent major refinement iteration with 'BEGIN CHAPTER X:'/'END CHAPTER X:' delimiters and more robust internal field parsing. Further significant iterative live testing and refinement performed on prompt & parser to improve stability and output quality for detailed structures. System is set up with a dedicated test script for ongoing live LLM testing. Prompt has now also undergone an initial quality pass aiming for more creative and distinct chapter elements. README goal: 1-2 detailed chapter outlines.)
    *   `[ ]` Support for multi-line narrative (TODO).
    *   `[ ]` User selection/editing of plot (TODO).
*   **[p] Character Sculptor Agent (人物刻画智能体 - README 4.3.4)**
    *   `[x]` MVP agent implemented in `src/agents/character_sculptor_agent.py`.
    *   `[p]` Significantly enhanced to generate detailed character profiles (`DetailedCharacterProfile` TypedDict) with many fields (background, personality, skills, goals, etc.). Serializes profile to JSON in DB's `description` field. `DatabaseManager` handles deserialization. (Live LLM call implemented; prompt and complex parsing logic for detailed structure added. Prompt has now also undergone an initial quality pass aiming for better interrelation between fields and character depth. Requires significant iterative refinement with live LLM testing to ensure consistency and completeness of all fields).
    *   `[ ]` User selection/editing of characters (TODO).
*   **[p] Chapter Chronicler Agent (章节智能体 - README 4.3.5)**
    *   `[x]` MVP agent implemented in `src/agents/chapter_chronicler_agent.py`.
    *   `[p]` Generates chapter (title, content, summary). (Live LLM call fully enabled. Prompt and parsing logic significantly refined with improved fallbacks, better logging, and more directive instructions on using context, based on (simulated) live testing. Prompt has now also undergone an initial quality pass aiming for more engaging prose, better use of character detail, and effective RAG context integration. Further refinement on content quality and full RAG utilization needed).
    *   `[p]` Takes style preferences into account (Prompt is there, but live LLM call needs verification of adherence).
    *   `[ ]` Generate 2-3 plot branch options at key points (TODO).
*   **[p] Context Synthesizer Agent (总结智能体 - README 4.3.8)**
    *   `[x]` MVP agent implemented in `src/agents/context_synthesizer_agent.py`.
    *   `[x]` Gathers data from DB (novel, outline, worldview, plot, previous chapters, characters).
    *   [p] Retrieves context from LoreKeeperAgent and detailed plot from PlotArchitectAgent; uses detailed character profiles. Brief construction now includes hierarchical history of previous chapters (N-1 full text snippet, N-X summaries, older chapter titles). (RAG needs real API key & live tuning; plot/character data usage enhanced. Advanced key event summaries for distant chapters TODO).
    *   `[x]` Synthesizes a text brief for `ChapterChroniclerAgent`.
    *   `[ ]` Generate different granularity of summaries (TODO - currently one detailed brief for chapter agent).
    *   `[ ]` Highlight key info in summaries (TODO).
*   **[p] Lore Keeper Agent (知识库管理员智能体 - README 4.3.9)**
    *   `[x]` MVP agent implemented in `src/agents/lore_keeper_agent.py`.
    *   `[x]` Uses `KnowledgeBaseManager` for RAG.
    *   `[p]` Initializes KB from outline, worldview, plot, and now detailed characters. (Live embedding calls implemented; full RAG functionality requires real API key; character data processing for KB now leverages rich DetailedCharacterProfile objects).
    *   `[p]` Updates KB with chapter summaries. (Live embedding calls implemented; full functionality requires real API key).
    *   `[ ]` Structured information extraction from generated content (NLP/LLM assisted) (TODO).
    *   [p] Conflict detection (`ConflictDetectionAgent` enhanced for RAG-based context awareness and improved LLM analysis. `WorkflowManager` uses this enhanced agent. Placeholders for resolution/display remain. Advanced KG-based detection and actual resolution logic TODO).
    *   `[ ]` User validation of KB entries (TODO).
*   **[p] Quality Guardian Agent (质量审核智能体 - README 4.3.6)** Implemented to review selected outline based on Clarity, Originality, Conflict Potential, Overall Score, and provide Justification. Review is informational (printed to CLI). (Live LLM call enabled; parsing implemented; advanced features/integration TODO).
*   [p] Content Integrity Agent (内容审核智能体 - README 4.3.7)** (Basic agent implemented with 7-dimensional scoring. WorkflowManager includes chapter retry mechanism in Auto-Mode based on its scores. Full retry strategy and human-in-the-loop for quality TODO).
*   [p] ConflictDetectionAgent (内容冲突检测智能体 - README 4.3.x - Assuming a number): Enhanced to use Knowledge Base context (RAG via LoreKeeperAgent) for detecting conflicts. Uses improved LLM prompting to categorize conflict type and severity. Integrated into WorkflowManager with `novel_id`. Unit tests updated.
*   [p] ConflictResolutionAgent (内容冲突解决智能体 - README 4.3.x): Stub agent created with methods for `attempt_auto_resolve` and `suggest_revisions_for_human_review`. Integrated into WorkflowManager for both auto-mode resolution attempts and human-mode API conflict review data preparation.
*   **[ ] Polish & Refinement Agent (润色智能体 - README 4.3.10)** (TODO)

## 3. Key Features & Workflow (from README 5 & others)

*   **[p] MVP End-to-End Workflow (CLI based)**
    *   `[x]` User input (theme, style) via CLI.
    *   `[x]` Orchestration of Outline -> Worldview -> Plot -> Characters -> KB Init -> Chapter Loop.
    *   `[p]` User selection of generated outlines & worldviews via CLI.
    *   `[p]` Informational review of selected outline by QualityGuardianAgent.
    *   `[p]` Plot generation uses detailed `PlotChapterDetail` structure.
    *   `[p]` Character generation uses `DetailedCharacterProfile` structure, stored as JSON in DB.
    *   `[p]` Chapter Loop (Context Synthesis -> Chapter Generation -> KB Update). (Structure DONE, RAG is partial pending real API key, live LLM calls for content).
    *   `[x]` Persistence of all generated artifacts to SQLite DB (Plot & Character descriptions stored as JSON).
    *   `[x]` CLI output of generated components.
*   **[p] Knowledge Base & RAG**
    *   `[x]` Initial setup of ChromaDB for vector storage.
    *   `[p]` Storing embeddings of novel components and chapter summaries. (Live embedding calls implemented; full functionality requires real API key).
    *   `[p]` Retrieving relevant context for chapter generation. (Live RAG calls implemented; conceptual verification done; quality of retrieval needs live testing & tuning).
    *   `[ ]` Advanced KG features (TODO).
    *   `[ ]` Automated information extraction and conflict detection in `LoreKeeperAgent` (TODO).
*   **User Interaction & Control**
    *   `[p]` User selection between multiple AI-generated outlines & worldviews (CLI implemented). (Broader multi-option for other artifacts TODO).
    *   `[ ]` User editing of generated content at various stages (TODO).
    *   `[ ]` User validation for knowledge base entries (TODO).
    *   `[ ]` User control over plot branches (TODO).
*   **[p] Multi-Option Generation by Agents**
    *   `[p]` Narrative Pathfinder: Generates 2 outlines (MVP), CLI selection.
    *   `[p]` WorldWeaverAgent: Generates 2 worldview options (MVP), CLI selection.
    *   (TODO for other agents as per README).
*   **[ ] Advanced Agent Capabilities (as per README detailed descriptions)**
    *   (e.g., Narrative Pathfinder: detailed synopsis; Plot Architect: full chapter outlines, multi-line; Character Sculptor: detailed attributes, arcs, relationships) (TODO for deeper features of existing agents).

## 4. Development Roadmap Items from README (Section 8)

*   **[x] Phase 0: Environment Setup & Basic Validation** (Largely DONE through initial setup and previous steps)
*   **[p] Phase 1: MVP - Core Skeleton & Flow 打通**
    *   `[x]` User input (simplified CLI).
    *   `[p]` Narrative Pathfinder Agent (Generates multiple outlines, live LLM, CLI selection).
    *   `[p]` World Weaver Agent (Generates multiple worldviews, live LLM, CLI selection).
    *   `[p]` Plot Architect Agent (Generates detailed chapter structures as `PlotChapterDetail`, live LLM, stored as JSON).
    *   `[p]` Character Sculptor Agent (Generates `DetailedCharacterProfile`, live LLM, stored as JSON).
    *   `[p]` Chapter Chronicler Agent (Live LLM, refined prompt/parser).
    *   `[p]` Lore Keeper Agent (RAG structure done, live embedding calls implemented, uses detailed character profiles; full functionality needs real API key).
    *   `[p]` Context Synthesizer Agent (MVP, uses LoreKeeper, adapted for detailed plot & characters, refined brief structure).
    *   `[ ]` Basic frontend UI (TODO).
    *   `[x]` Data Persistence Layer (SQLite, Plot & Character descriptions stored as JSON).
    *   `[x]` Orchestration Layer (LangGraph, includes CLI outline & worldview selection, Quality Guardian for outline). Now includes chapter quality retry logic (Auto-Mode) and placeholders for mode-specific conflict handling.
*   **[p] Phase 1.b: Live LLM Testing, Prompt Tuning, and Output Stabilization**
    *   `[x]` Configure and Secure OpenAI API Key (Docs updated, .env.example created).
    *   `[x]` Enable Real LLM Calls in Agents & Workflow.
    *   `[p]` Iteratively Refine Agent Prompts & Parsing based on Real Outputs (Initial major pass DONE for PlotArchitect, ChapterChronicler; ongoing as needed for all).
    *   `[p]` Verify Knowledge Base (RAG) Functionality (Conceptual verification DONE; live performance TBD).
    *   `[x]` Address Token Limits and API Errors (Enhanced logging in LLMClient, initial max_token review DONE).
*   **[p] Phase 2.A: User Interaction for Outline Selection & Enhanced Plot Detailing**
    *   `[x]` Modify WorkflowManager & CLI for Outline Selection.
    *   `[p]` Enhance PlotArchitectAgent for Detailed Chapter Structures (Initial implementation of prompt, parsing, and DB storage of List[PlotChapterDetail] DONE; requires significant iterative refinement with live LLM).
    *   `[x]` Testing with Real LLM Calls (Conceptual test and identification of PlotArchitectAgent as key area for refinement DONE for this phase's scope).
*   **[p] Phase 2.B: Worldview Selection and Initial Quality Guardian Agent**
    *   `[x]` Enhance WorldWeaverAgent for Multiple, Structured Worldviews (MVP version).
    *   `[x]` Modify WorkflowManager & CLI for Worldview Selection.
    *   `[x]` Develop QualityGuardianAgent (Basic - for Outlines).
    *   `[x]` Integrate QualityGuardianAgent into Workflow (for selected outline, informational).
    *   `[p]` Testing with Real LLM Calls (Conceptual test for Phase 2.B features DONE; live testing and refinement of new agents ongoing).
*   **[p] Phase 2.C: Detailed Character Generation (CharacterSculptorAgent)**
    *   `[x]` Define DetailedCharacterProfile TypedDict in src/core/models.py.
    *   `[p]` Enhance CharacterSculptorAgent (prompt, parsing, JSON persistence for detailed profiles). (Initial heavy implementation DONE; needs iterative refinement with live LLM).
    *   `[x]` Update Database Interaction (DatabaseManager deserialization of character JSON, WorkflowManager to use DetailedCharacterProfile).
    *   `[p]` Testing with Real LLM Calls (Conceptual test for CharacterSculptorAgent's new capabilities DONE; live testing and refinement ongoing/needed).
*   **[p] Phase 2.D: Live Testing & Core Generation Loop Stabilization**
    *   `[x]` Targeted Live Testing & Refinement: `PlotArchitectAgent` (Intensive prompt/parser refinement iterations completed).
    *   `[x]` Targeted Live Testing & Refinement: `CharacterSculptorAgent` (Completed in prior Phase 2.C; live testing implicitly part of full workflow runs).
    *   `[x]` Full Workflow Live Test & `ChapterChroniclerAgent` Refinement (Intensive prompt/parser/context-usage refinement iterations completed for ChapterChronicler & ContextSynthesizer).
    *   `[x]` Basic Coherence Review (Conceptual review of more stabilized loop completed).
*   **[p] Phase 3.A: Real-Use Enablement - Live Workflow Hardening & Quality Pass (Revised Focus)**
    *   `[x]` Enhance RAG Context Logging.
    *   `[x]` Initial Quality Pass on Prompts (Content Focus for PlotArchitect, CharacterSculptor, ChapterChronicler DONE).
    *   [ ] (Implicit) Intensive Live End-to-End Workflow Testing (`main.py`) - This is ongoing / covered by the need for further agent refinement.
    *   [ ] (Implicit) Critical Bug Fixing & Parser Robustness (Iterative) - Initial major pass done, ongoing as needed.
    *   [ ] (Implicit) RAG System - Live Functional Check - Basic logging in place, deeper functional check & tuning needed.
    *   [ ] (Implicit) Basic Coherence Review - Initial conceptual review done, ongoing with live tests.
*   **[p] Phase 2: Web Interface & Advanced Features (as per original issue doc)**
    *   `[p]` Develop the core features of the Web interface:
        *   `[p]` FastAPI backend: Implemented `POST /novels/` for async generation start.
        *   `[p]` FastAPI backend: Implemented `GET /novels/{novel_id}/status` for status checks.
        *   [p] FastAPI backend: Implemented `GET /decisions/next` and `POST /decisions/{type}` endpoints for user decisions in Human-Mode. `WorkflowManager` adapted to pause/resume with DB state persistence.
        *   `[ ]` Frontend UI (React/Vue/Svelte etc.) (TODO).
    *   `[p]` Implement visual management of the knowledge base:
        *   `[p]` FastAPI backend: Implemented `GET /novels/{novel_id}/knowledge_graph` to serve KB data.
        *   `[ ]` Frontend component to display the knowledge graph (TODO).
    *   `[p]` Establish an intelligent conflict detection mechanism:
        *   `[p]` Conceptual outline for advanced conflict detection (RAG, KG, better LLM prompts) defined.
        *   [p] Implementation of advanced conflict detection in `ConflictDetectionAgent` (Agent enhanced with RAG for KB context, improved LLM prompting for type/severity. Core logic implemented; further refinement and broader context integration ongoing).
        *   [p] Implementation of conflict auto-resolution (Auto-Mode) or user-choice presentation (Human-Mode) in `WorkflowManager`: Auto-mode calls stub `ConflictResolutionAgent`. Human-mode API flow prepares conflict data via stub agent and pauses for user review/decision (backend logic for pause/resume complete). Actual LLM-based resolution/suggestion by agent is TODO.
*   **[p] Phase 3: Optimizations & Advanced Features (as per original issue doc)**
    *   `[p]` Optimize context management and cost control:
        *   `[x]` Analysis of current context usage and cost drivers completed.
        *   `[ ]` LLM Request/Response Caching in `LLMClient` (Deprioritized based on user feedback for local models; quality focus).
        *   [p] Hierarchical Context Management for `ChapterChroniclerAgent` (Implemented initial version in `ContextSynthesizerAgent`: N-1 full text snippet, N-X summaries, older chapter titles. Unit tests added. Advanced key event summaries for distant chapters and further RAG query refinement TODO).
        *   `[ ]` Hybrid Model Strategy (Conceptual planning TODO).
    *   `[ ]` Implement advanced interactive features for Human-Mode (TODO - further breakdown needed).
    *   `[ ]` Establish a user preference learning system (TODO - further breakdown needed).


## 5. Other Considerations

*   **[ ] Responsible AI & Ethics (README 10)** (TODO - Content filtering, bias mitigation beyond basic LLM behavior).
*   **[p] Testing & Quality Assurance (README 11)**
    *   [p] Unit tests (Basic `if __name__ == '__main__'` tests for agents; More comprehensive unittest suites for key agents like ConflictDetectionAgent, ContextSynthesizerAgent).
    *   `[p]` Integration tests (Workflow manager tests with mocked/live agent interactions).
    *   `[p]` End-to-end tests (CLI `main.py` provides basic E2E test capability).
    *   `[ ]` Dedicated KB testing, consistency testing, prompt performance testing, UAT (TODO).
*   **[ ] Deployment & Ops (README 12)** (TODO).

---
This list will be updated as development progresses.
