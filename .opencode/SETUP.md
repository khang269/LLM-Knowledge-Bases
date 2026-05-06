# LLM Knowledge Base Plugin for OpenCode: Setup Guide

This guide will walk you through installing and configuring the LLM Knowledge Base (Wiki) plugin for OpenCode. This setup ensures that OpenCode can autonomously capture your daily conversations, compile them into a searchable markdown wiki, and inject context back into your sessions—regardless of what framework or language your main project uses.

## Prerequisites

1. **Python 3.10+**: The core knowledge base engine runs on Python.
2. **OpenCode**: Ensure you have OpenCode installed and initialized in your project.
3. **Bun** (or npm): OpenCode uses Bun to install plugin dependencies on startup.

---

## Step 1: Set Up the Python Engine

The heavy lifting (LLM calls, SQLite state tracking, Pydantic validation) is handled by the `llm-wiki` Python package.

### Option A: Global Installation (Recommended)
If you install the engine globally using `pipx`, you can use it across **all** your OpenCode projects without needing to reinstall it every time.

**On Mac / Linux:**
```bash
curl -sL https://raw.githubusercontent.com/khang269/LLM-Knowledge-Bases/main/install.sh | bash
```

**On Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri https://raw.githubusercontent.com/khang269/LLM-Knowledge-Bases/main/install.ps1 -OutFile install.ps1; .\install.ps1
```

Configure your API keys globally so all your projects can share them:
```bash
llm-wiki config set provider google
llm-wiki config set-key GOOGLE_API_KEY your_api_key_here
```

### Option B: Local Isolated Installation
If you prefer to keep the engine completely isolated within this specific project, install it inside the `.opencode/engine` folder:
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
*Note: If you use this local method, you must create a `.env` file inside `.opencode/engine/` to hold your API keys instead of using the global config.*

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
   OpenCode loads external packages using a local `package.json`. Navigate to the `.opencode` directory and install the dependencies:
   ```bash
   cd .opencode
   bun install
   ```

3. **Verify the Executable:**
   The `llm-wiki.ts` plugin is smart! On startup, it checks if you have a local `.opencode/engine/venv` installed. If it finds one, it runs totally isolated. If it doesn't find one, it safely falls back to using your global system `llm-wiki` installation. You don't need to configure any paths manually!

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
- *"Import this YouTube video into my daily log."* -> Triggers `kb_import`
- *"Sync my entire knowledge base automatically."* -> Triggers `kb_build`
- *"Process the new files in my raw folder into drafts."* -> Triggers `kb_ingest`
- *"Compile the drafts for my knowledge base."* -> Triggers `kb_compile`
- *"Read the drafts in wiki/.drafts and approve them."* -> Triggers `kb_approve`
- *"Query the knowledge base: How does our auth system work? Save the answer."* -> Triggers `kb_query` with `--file-back`
- *"Run a lint check on the wiki to find broken links."* -> Triggers `kb_lint`

Welcome to your auto-compiling, permanent AI memory system!
