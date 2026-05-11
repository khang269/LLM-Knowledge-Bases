# OpenCode LLM Knowledge Base

A Python-based, tool-agnostic Local LLM Knowledge Base and Memory Compiler.

Adapted from Andrej Karpathy's LLM Knowledge Base architecture and the Claude Memory Compiler, this project allows you to seamlessly ingest external documents (articles, papers) and automatically extract knowledge from your AI coding conversations into a permanently queryable, structured markdown wiki.

Instead of relying on fragile RAG (Retrieval-Augmented Generation) with vector databases, this system uses **Semantic Graph Traversal**. It maintains a central `index.md` catalog of all your concepts, allowing the LLM to intelligently navigate through interconnected concepts and raw source files to synthesize accurate, ground-truth answers.

## 🚀 Core Strengths

- **Semantic Graph RAG:** Unlike vector search which can be "hit or miss," our system uses the LLM to pick entry points from the index and then programmatically traverses the graph of `[[wikilinks]]` and `source_file` breadcrumbs. This ensures the LLM always has the relevant context and the raw ground-truth data.
- **Hybrid Memory System:** Uses concise, LLM-generated summaries for fast navigation and indexing, but automatically fetches the full, unedited **Raw Sources** during queries to ensure 100% accuracy and prevent hallucination.
- **Multi-Threaded & Resilient Performance:** High-speed ingestion and compilation pipelines use parallel processing to handle dozens of documents in minutes. API calls are automatically wrapped with exponential backoff retries using `tenacity`, ensuring the system cleanly survives rate limits and network timeouts without skipping files.
- **Global Cross-Workspace Memory:** Defaults to a unified global knowledge base (`~/.llm-wiki/`), allowing your AI agents to "remember" decisions and patterns across every project you work on.
- **Safe & Structured:** Uses strict Pydantic schemas and a local SQLite database to track state, hashes, and links. The LLM never has raw write access to your filesystem.

## Features

- **Platform Integrations:** Natively hooks into AI coding agents like OpenCode to silently capture conversations and provide autonomous file management tools.
- **Multi-Provider Support:** Works with Google (Gemini), OpenAI, Anthropic, and Groq via the `instructor` library.
- **Dual Ingestion:** Ingests raw external notes and continuously flushes daily AI conversation transcripts into a date-nested hierarchy.
- **Multi-Format Imports:** Uses `microsoft/markitdown` to natively convert PDFs, Word docs, Excel, YouTube transcripts, and raw web URLs directly into Markdown.
- **LLM Vision OCR:** Automatically routes images and diagrams found inside imported documents through your chosen LLM provider to generate rich Markdown descriptions.
- **Drafting & Approval System:** New knowledge is generated into namespaced `.drafts/` sub-folders. You review and approve before it officially enters your live wiki.
- **Advanced Linting:** Fast structural health checks (broken links, orphans, missing YAML) combined with LLM-driven contradiction hunting across the entire graph.

## Folder Architecture

The library automatically manages the following Obsidian-compatible structure:

```text
my-research/
├── raw/                 # Unprocessed source materials
│   ├── daily/           # Date-nested AI conversation memory logs
│   ├── articles/        # Web imports
│   ├── papers/          # PDF/Word imports
│   └── ...              
├── wiki/                # The compiled, LLM-managed knowledge base
│   ├── concepts/        # Atomic knowledge articles
│   ├── connections/     # Cross-cutting insights linking 2+ concepts
│   ├── sources/         # Auto-generated summaries of raw inputs
│   ├── qa/              # Filed answers to complex queries
│   ├── index.md         # Master catalog - the core retrieval mechanism
│   ├── log.md           # Append-only chronological operation log
│   └── .drafts/         # Namespaced sub-folders waiting for approval
└── _meta/               
    └── state.db         # SQLite database tracking file hashes and relationships
```

## Platform Integrations

### 🔌 OpenCode Integration
We provide a native TypeScript plugin for OpenCode that automates session extraction and exposes the knowledge base to the AI as native tools.
👉 **[Read the OpenCode SETUP.md Guide](.opencode/SETUP.md)**

---

## Standalone CLI Installation

We provide two cross-platform installation scripts that will install the `llm-wiki` executable globally to your system PATH using `pipx`.

**On Mac / Linux:**
```bash
curl -sL https://raw.githubusercontent.com/khang269/LLM-Knowledge-Bases/main/install.sh | bash
```

**On Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri https://raw.githubusercontent.com/khang269/LLM-Knowledge-Bases/main/install.ps1 -OutFile install.ps1; .\install.ps1
```

*(Note: These scripts will automatically install Python 3 and pipx if they are missing from your system, and apply a high timeout to handle large dependencies).*

### Global Configuration (Required)
Once installed globally, you can securely set your preferences once and share them across all projects. **You must set a provider and API key before running any workflows:**

```bash
# Set your provider and model (google, openai, anthropic, groq)
llm-wiki config set provider google
llm-wiki config set model gemini-2.5-flash

# Set your API keys (Stored securely in ~/.llm-wiki/.env)
llm-wiki config set-key GOOGLE_API_KEY your_api_key_here

# (Optional) Set query limits and concurrency for the Graph Traversal and Compilation
llm-wiki config set max_chars 100000
llm-wiki config set max_depth 2
llm-wiki config set max_workers 3
```

---

## Usage

By default, the CLI operates on a **Global Knowledge Base** at `~/.llm-wiki/knowledge_base`. Use the `--dir` flag to target a project-specific folder.

### 1. Initialization
Bootstrap the folder structure and SQLite database:
```bash
llm-wiki init
```

### 2. Import External Documents
Download and convert external formats (PDFs, URLs, YouTube) using the `markitdown` pipeline:
```bash
# Defaults to today's daily log (raw/daily/YYYY-MM-DD/)
llm-wiki import "https://example.com/article"

# Or target a specific sub-folder in raw/
llm-wiki import /path/to/paper.pdf --dest raw --subfolder papers
```

### 3. 1-Click Automatic Build (Recommended)
Sync everything instantly: ingest raw files, extract concepts, compile relationships, and publish to the live wiki.
```bash
llm-wiki build
```

### 4. The Staged Workflow
For strict control, run the pipeline step-by-step:
1. **Ingest:** Extracts concepts and creates Source Summaries in `.drafts/sources/`.
2. **Compile:** Synthesizes Concept and Connection articles into `.drafts/`.
3. **Approve:** Moves reviewed markdown files to their final wiki destinations.

### 5. Querying (Semantic Graph RAG)
Ask complex questions. The system will navigate the index, traverse the graph of concepts, fetch raw sources, and synthesize an answer.
```bash
llm-wiki query "How does our authentication strategy work?" --file-back
```

### 6. Memory Flush
Pass a raw conversation transcript from an AI agent to extract decisions and lessons learned.
```bash
llm-wiki flush path/to/transcript.txt
```

## Testing
To run the automated multi-threaded test suite:
```bash
python -m pytest tests/ -v -s
```
