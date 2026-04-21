# LLM Knowledge Base Plugin for OpenCode: Setup Guide

This guide will walk you through installing and configuring the LLM Knowledge Base (Wiki) plugin for OpenCode. This setup ensures that OpenCode can autonomously capture your daily conversations, compile them into a searchable markdown wiki, and inject context back into your sessions—regardless of what framework or language your main project uses.

## Prerequisites

1. **Python 3.10+**: The core knowledge base engine runs on Python.
2. **OpenCode**: Ensure you have OpenCode installed and initialized in your project.
3. **Bun** (or npm): OpenCode uses Bun to install plugin dependencies on startup.

---

## Step 1: Set Up the Python Engine

The heavy lifting (LLM calls, SQLite state tracking, Pydantic validation) is handled by a robust Python backend package.

1. **Install the Package in the `.opencode` directory:**
   To keep your project's main repository clean, we recommend installing the Python engine entirely inside the `.opencode/engine` folder:
   ```bash
   mkdir -p .opencode/engine
   cd .opencode/engine
   
   # Create a virtual environment specifically for the knowledge base
   python -m venv venv
   
   # On Windows:
   .\venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   
   # Install the package directly from GitHub
   pip install git+https://github.com/khang269/LLM-Knowledge-Bases.git
   ```

2. **Configure API Keys:**
   Create a `.env` file inside your `.opencode/engine/` folder (or in your project root):
   ```env
   # .opencode/engine/.env
   LLM_PROVIDER=gemini  # Options: gemini, openai, anthropic, groq
   
   GEMINI_API_KEY=your_gemini_api_key
   OPENAI_API_KEY=your_openai_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   GROQ_API_KEY=your_groq_api_key
   ```

---

## Step 2: Install the OpenCode Plugin

OpenCode supports custom plugins written in TypeScript. We have provided a plugin that bridges OpenCode's event hooks to the `llm-wiki` CLI.

1. **Copy Plugin Files:**
   Ensure the `.opencode` folder in your project root contains the following structure:
   ```text
   .opencode/
   ├── package.json
   └── plugins/
       └── llm-wiki.ts
   ```

2. **Install Plugin Dependencies:**
   OpenCode loads external packages using a local `package.json`. Navigate to the `.opencode` directory and install the dependencies. OpenCode normally runs `bun install` on startup, but you can do it manually to be safe:
   ```bash
   cd .opencode
   bun install
   ```

3. **Verify the Python Executable:**
   The `llm-wiki.ts` plugin is pre-configured to look for the CLI tool specifically inside `.opencode/engine/venv/`. It will automatically use this isolated virtual environment. You don't need to manually configure any system paths or modify your primary project's backend!

---

## Step 3: Initialize Your Knowledge Base

Now that both the Python engine and the OpenCode plugin are installed, you can initialize the system.

1. Launch OpenCode in your project.
2. In the OpenCode terminal, simply ask the AI:
   > *"Initialize the LLM Knowledge Base for this project."*
3. The AI will invoke the `kb_init` tool. You should see a `my-research` folder appear in your project root containing `daily/`, `wiki/`, and `_meta/` directories.

*(Note: Add `my-research/` to your project's `.gitignore` if you do not want to track your personal knowledge base in your project's repository).*

---

## How It Works in OpenCode

Once installed, the plugin operates in two ways:

### 1. Passive Memory Capture (Automatic)
You don't need to do anything. As you chat with OpenCode, the plugin listens to background events:
- **`session.compacted`**: When a conversation is compacted, the transcript is silently flushed to the Python engine, which extracts "Lessons Learned" and "Decisions" and appends them to today's `daily/YYYY-MM-DD.md` log.
- **`experimental.session.compacting`**: Before OpenCode drops old context, the plugin fetches your `wiki/index.md` and injects it back into the prompt, ensuring OpenCode never forgets your architectural rules.

### 2. Autonomous AI Tools (Active)
OpenCode now has access to custom tools it can use during your conversations. You can explicitly ask OpenCode to:
- *"Compile the drafts for my knowledge base."* -> Triggers `kb_compile`
- *"Read the drafts in wiki/.drafts and approve them."* -> Triggers `kb_approve`
- *"Query the knowledge base: How does our auth system work? Save the answer."* -> Triggers `kb_query` with `--file-back`
- *"Run a lint check on the wiki to find broken links."* -> Triggers `kb_lint`

Welcome to your auto-compiling, permanent AI memory system!
