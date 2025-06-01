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
    *   `[ ]` Present AI-generated options, scores, reasons to user (TODO - No multi-option generation yet).
    *   `[ ]` Text editor for user modifications (TODO).
    *   `[ ]` User session management (TODO).
    *   `[ ]` Web UI (FastAPI/Flask backend, React/Vue/Svelte frontend) (TODO).
*   **[x] Orchestration & Workflow Layer (OLC - README 4.2)**
    *   `[x]` LangGraph based `WorkflowManager` implemented.
    *   `[x]` Manages sequence for outline, worldview, plot, characters, and chapter loop.
    *   `[p]` Conditional branching (Basic error handling exists. Complex branching based on scores/user input TODO).
    *   `[x]` Chapter generation loop structure implemented.
    *   `[x]` Global state management within workflow (MVP level).
    *   `[ ]` Integration of human input nodes for user decisions (TODO).
*   **[p] Agent Layer (AL - README 4.3)**
    *   (Individual agent status below)
*   **[x] LLM Abstraction Layer (LLMAL - README 4.5)**
    *   `[x]` `LLMClient` for OpenAI API implemented.
    *   `[ ]` Management of different models/configs (Basic, model name can be passed; advanced config/switching TODO).
    *   `[ ]` API retry, error handling, rate limiting (Basic error handling in client; advanced features TODO).
    *   `[ ]` Support for local models (TODO).
*   **[p] Knowledge Base Layer (KBL - README 4.4 & 6)**
    *   `[x]` `KnowledgeBaseManager` for RAG using ChromaDB implemented.
    *   `[p]` Vector DB (ChromaDB) for RAG: Stores text chunks from agents. (PARTIALLY DONE - embedding/retrieval needs real API key).
    *   `[ ]` Knowledge Graph (KG) for structured facts (TODO).
    *   `[x]` SQL DB for storing `KnowledgeBaseEntry` metadata.
*   **[x] Data Persistence Layer (DPL - README 4.6)**
    *   `[x]` `DatabaseManager` for SQLite implemented.
    *   `[x]` Schema for novels, outlines, worldviews, plots, characters, chapters, kb_entries.
    *   `[ ]` User info/auth storage (TODO).
    *   `[ ]` Versioning of generated content (TODO).
    *   `[ ]` Storing user edits/selections (TODO).

## 2. Agents (from README 4.3)

*   **[p] Narrative Pathfinder Agent (概述智能体 - README 4.3.1)**
    *   `[x]` Basic agent structure in `src/agents/narrative_pathfinder_agent.py`.
    *   `[p]` Generates 1 core creative overview (Currently mocked in `WorkflowManager` for dummy key runs. README specifies 3-5 options, 500-1000 words).
    *   `[ ]` Expand selected overview to detailed plot synopsis (README optional item).
    *   `[ ]` User selection from multiple overviews (TODO).
*   **[p] World Weaver Agent (世界观智能体 - README 4.3.2)**
    *   `[x]` Basic agent structure in `src/agents/world_weaver_agent.py`.
    *   `[p]` Generates 1 worldview (Currently mocked in `WorkflowManager` for dummy key runs. README specifies 3-5 structured options).
    *   `[ ]` Output in specified structured format (partially, current mock is just text).
    *   `[ ]` User selection/editing of structured worldview (TODO).
*   **[p] Plot Architect Agent (大纲智能体 - README 4.3.3)**
    *   `[x]` Basic agent structure in `src/agents/plot_architect_agent.py`.
    *   `[p]` Generates high-level plot points. (Workflow mock currently creates chapter-by-chapter summaries. README specifies 1-2 detailed chapter outlines).
    *   `[ ]` Support for multi-line narrative (TODO).
    *   `[ ]` User selection/editing of plot (TODO).
*   **[p] Character Sculptor Agent (人物刻画智能体 - README 4.3.4)**
    *   `[x]` MVP agent implemented in `src/agents/character_sculptor_agent.py`.
    *   `[p]` Generates 1-2 basic characters (name, desc, role). (Uses internal mock LLM. README specifies 1-2 *detailed* sets of characters with more attributes like background, personality, arc, relationships).
    *   `[ ]` User selection/editing of characters (TODO).
*   **[p] Chapter Chronicler Agent (章节智能体 - README 4.3.5)**
    *   `[x]` MVP agent implemented in `src/agents/chapter_chronicler_agent.py`.
    *   `[p]` Generates chapter (title, content, summary). (Uses internal mock LLM. README specifies using detailed brief, KB context).
    *   `[p]` Takes style preferences into account (Prompt is there, but mock LLM doesn't use it).
    *   `[ ]` Generate 2-3 plot branch options at key points (TODO).
*   **[p] Context Synthesizer Agent (总结智能体 - README 4.3.8)**
    *   `[x]` MVP agent implemented in `src/agents/context_synthesizer_agent.py`.
    *   `[x]` Gathers data from DB (novel, outline, worldview, plot, previous chapters, characters).
    *   `[p]` Retrieves context from `LoreKeeperAgent` (PARTIALLY DONE - RAG needs real API key).
    *   `[x]` Synthesizes a text brief for `ChapterChroniclerAgent`.
    *   `[ ]` Generate different granularity of summaries (TODO - currently one detailed brief for chapter agent).
    *   `[ ]` Highlight key info in summaries (TODO).
*   **[p] Lore Keeper Agent (知识库管理员智能体 - README 4.3.9)**
    *   `[x]` MVP agent implemented in `src/agents/lore_keeper_agent.py`.
    *   `[x]` Uses `KnowledgeBaseManager` for RAG.
    *   `[p]` Initializes KB from outline, worldview, plot, characters. (PARTIALLY DONE - embedding needs real API key).
    *   `[p]` Updates KB with chapter summaries. (PARTIALLY DONE - embedding needs real API key).
    *   `[ ]` Structured information extraction from generated content (NLP/LLM assisted) (TODO).
    *   `[ ]` Conflict detection (TODO).
    *   `[ ]` User validation of KB entries (TODO).
*   **[ ] Quality Guardian Agent (质量审核智能体 - README 4.3.6)** (TODO)
*   **[ ] Content Integrity Agent (内容审核智能体 - README 4.3.7)** (TODO)
*   **[ ] Polish & Refinement Agent (润色智能体 - README 4.3.10)** (TODO)

## 3. Key Features & Workflow (from README 5 & others)

*   **[p] MVP End-to-End Workflow (CLI based)**
    *   `[x]` User input (theme, style) via CLI.
    *   `[x]` Orchestration of Outline -> Worldview -> Plot -> Characters -> KB Init -> Chapter Loop.
    *   `[p]` Chapter Loop (Context Synthesis -> Chapter Generation -> KB Update). (Structure DONE, content is mocked, RAG is partial).
    *   `[x]` Persistence of all generated artifacts to SQLite DB.
    *   `[x]` CLI output of generated components.
*   **[p] Knowledge Base & RAG**
    *   `[x]` Initial setup of ChromaDB for vector storage.
    *   `[p]` Storing embeddings of novel components and chapter summaries. (PARTIALLY DONE - needs real API key).
    *   `[p]` Retrieving relevant context for chapter generation. (PARTIALLY DONE - needs real API key).
    *   `[ ]` Advanced KG features (TODO).
    *   `[ ]` Automated information extraction and conflict detection in `LoreKeeperAgent` (TODO).
*   **User Interaction & Control**
    *   `[ ]` User selection between multiple AI-generated options (outlines, worldviews, etc.) (TODO).
    *   `[ ]` User editing of generated content at various stages (TODO).
    *   `[ ]` User validation for knowledge base entries (TODO).
    *   `[ ]` User control over plot branches (TODO).
*   **[ ] Multi-Option Generation by Agents**
    *   (e.g., Narrative Pathfinder: 3-5 overviews; World Weaver: 3-5 worldviews) (TODO for all relevant agents).
*   **[ ] Advanced Agent Capabilities (as per README detailed descriptions)**
    *   (e.g., Narrative Pathfinder: detailed synopsis; Plot Architect: full chapter outlines, multi-line; Character Sculptor: detailed attributes, arcs, relationships) (TODO for deeper features of existing agents).

## 4. Development Roadmap Items from README (Section 8)

*   **[x] Phase 0: Environment Setup & Basic Validation** (Largely DONE through initial setup and previous steps)
*   **[p] Phase 1: MVP - Core Skeleton & Flow 打通**
    *   `[x]` User input (simplified CLI).
    *   `[p]` Narrative Pathfinder Agent (MVP structure, mocked output).
    *   `[p]` Plot Architect Agent (MVP structure, workflow mock for chapter plots).
    *   `[p]` Character Sculptor Agent (MVP with internal mock).
    *   `[p]` Chapter Chronicler Agent (MVP with internal mock).
    *   `[p]` Lore Keeper Agent (RAG基础版 - structure done, embedding needs API key).
    *   `[x]` Context Synthesizer Agent (MVP).
    *   `[ ]` Basic frontend UI (TODO).
    *   `[x]` Data Persistence Layer (SQLite).
    *   `[x]` Orchestration Layer (LangGraph).
*   **[ ] Phase 2: Core Function Refinement & Initial Agent Shaping** (TODO)
    *   (Includes implementing all agents from README, multi-option selection, quality/content review agents, Polish & Refinement agent, enhanced Lore Keeper, UI improvements)
*   **[ ] Phase 3: Advanced Features & UX Optimization** (TODO)
*   **[ ] Phase 4: Commercialization Prep & Continuous Iteration** (TODO)

## 5. Other Considerations

*   **[ ] Responsible AI & Ethics (README 10)** (TODO - Content filtering, bias mitigation beyond basic LLM behavior).
*   **[p] Testing & Quality Assurance (README 11)**
    *   `[p]` Unit tests (Basic `if __name__ == '__main__'` tests for agents).
    *   `[p]` Integration tests (Workflow manager tests with mocked agent interactions).
    *   `[p]` End-to-end tests (CLI `main.py` provides basic E2E test capability with mocks).
    *   `[ ]` Dedicated KB testing, consistency testing, prompt performance testing, UAT (TODO).
*   **[ ] Deployment & Ops (README 12)** (TODO).

---
This list will be updated as development progresses.
