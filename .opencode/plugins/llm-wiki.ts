import { type Plugin, tool } from "@opencode-ai/plugin";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs";
import path from "path";

const execAsync = promisify(exec);

export const LlmWikiPlugin: Plugin = async ({ client, directory }) => {
  const isWin = process.platform === "win32";
  
  // Resolve the CLI command. Try to use a local venv if it exists within the .opencode/engine folder.
  let cliCmd = "llm-wiki";
  const localVenvWin = path.join(directory, ".opencode", "engine", "venv", "Scripts", "llm-wiki.exe");
  const localVenvMac = path.join(directory, ".opencode", "engine", "venv", "bin", "llm-wiki");
  
  if (isWin && fs.existsSync(localVenvWin)) {
    cliCmd = `"${localVenvWin}"`;
  } else if (!isWin && fs.existsSync(localVenvMac)) {
    cliCmd = `"${localVenvMac}"`;
  }
    
  const kbDir = "my-research";

  // Helper to execute commands safely
  const runCmd = async (command: string) => {
    try {
      const fullCmd = `${cliCmd} --dir "${kbDir}" ${command}`;
      const { stdout, stderr } = await execAsync(fullCmd, { cwd: directory });
      return stdout || stderr || "Command executed successfully.";
    } catch (e: any) {
      return `Error: ${e.message}\n${e.stderr || ""}`;
    }
  };

  return {
    // 1. Session integration: Injecting context mid-session during auto-compaction
    "experimental.session.compacting": async (input, output) => {
      try {
         const result = await runCmd(`session-context`);
         if (result && !result.startsWith("Error:")) {
            // Inject additional context into the compaction prompt
            output.context.push(
              `## Knowledge Base Context\n\n${result}`
            );
         }
      } catch (e) {
         client.app.log({ level: "error", message: `Failed to inject context: ${e}` });
      }
    },

    // 2. Automated memory extraction 
    "session.compacted": async (event: any) => {
      // Auto-flush memory automatically using the conversation context available in the event payload
      try {
        if (event && event.transcript_path) {
          await runCmd(`flush "${event.transcript_path}"`);
          client.app.log({ level: "info", message: "Auto-flushed session memory." });
        } else if (event && event.messages) {
          const fs = await import("fs/promises");
          const path = await import("path");
          const tempPath = path.join(directory, "temp_transcript.txt");
          const text = event.messages.map((m: any) => `${m.role}: ${m.content}`).join("\n");
          await fs.writeFile(tempPath, text, "utf-8");
          await runCmd(`flush "${tempPath}"`);
          await fs.unlink(tempPath);
          client.app.log({ level: "info", message: "Auto-flushed session memory from messages." });
        }
      } catch (e) {
        client.app.log({ level: "error", message: `Failed to auto-flush memory: ${e}` });
      }
    },

    // 3. Exposing manual commands to the OpenCode AI Agent as custom tools
    tools: [
      tool({
        name: "kb_init",
        description: "Initialize a new LLM Knowledge Base (folder structure and SQLite DB) in the project.",
        args: {},
        async execute() {
          return await runCmd(`init`);
        },
      }),

      tool({
        name: "kb_ingest",
        description: "Ingest a new raw source file into the LLM Knowledge Base. Leave source empty to ingest all pending.",
        args: {
          source: tool.schema.string().optional(),
          force: tool.schema.boolean().optional(),
        },
        async execute({ source, force }) {
          let cmd = `ingest`;
          if (source) cmd += ` "${source}"`;
          if (force) cmd += ` --force`;
          return await runCmd(cmd);
        },
      }),

      tool({
        name: "kb_compile",
        description: "Compile extracted concepts into draft wiki articles.",
        args: {
          force: tool.schema.boolean().optional(),
        },
        async execute({ force }) {
          let cmd = `compile`;
          if (force) cmd += ` --force`;
          return await runCmd(cmd);
        },
      }),

      tool({
        name: "kb_approve",
        description: "Approve draft(s) and publish to the wiki.",
        args: {
          draft: tool.schema.string().optional(),
        },
        async execute({ draft }) {
          let cmd = `approve`;
          if (draft) cmd += ` "${draft}"`;
          return await runCmd(cmd);
        },
      }),

      tool({
        name: "kb_reject",
        description: "Reject a draft with feedback for the LLM to learn from.",
        args: {
          draft: tool.schema.string(),
          feedback: tool.schema.string(),
        },
        async execute({ draft, feedback }) {
          return await runCmd(`reject "${draft}" --feedback "${feedback}"`);
        },
      }),

      tool({
        name: "kb_query",
        description: "Query the LLM Knowledge Base to answer a complex question.",
        args: {
          question: tool.schema.string(),
          file_back: tool.schema.boolean().optional(),
        },
        async execute({ question, file_back }) {
          const safeQuestion = question.replace(/"/g, '\\"');
          let cmd = `query "${safeQuestion}"`;
          if (file_back) cmd += ` --file-back`;
          return await runCmd(cmd);
        },
      }),

      tool({
        name: "kb_lint",
        description: "Perform a health check on the wiki to detect broken links, orphans, or contradictions.",
        args: {
          llm: tool.schema.boolean().optional(),
        },
        async execute({ llm }) {
          let cmd = `lint`;
          if (llm) cmd += ` --llm`;
          return await runCmd(cmd);
        },
      }),
      
      tool({
        name: "kb_flush",
        description: "Extract important knowledge from a conversation transcript and append to daily log.",
        args: {
          transcript: tool.schema.string(),
        },
        async execute({ transcript }) {
          return await runCmd(`flush "${transcript}"`);
        }
      })
    ]
  };
};
