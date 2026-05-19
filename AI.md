# AI Setup & CLI-Based Coding Guide

This project emphasizes a **CLI-based coding workflow**. We will leverage various AI models to assist in development, debugging, and documentation directly from the terminal or integrated CLI tools.

## 1. Primary AI Tools

We will be using the following AI tools in our workflow:

-   **GitHub Copilot:** For real-time code completions and CLI assistance.
-   **Claude:** For complex reasoning, architectural design, and deep code analysis.
-   **Codex:** For specialized code generation and legacy support.
-   **Gemini:** For integrated codebase exploration and multi-step engineering tasks using the Gemini CLI.

## 2. Setting Up Your CLI Environment

### GitHub Copilot CLI
1. Install the GitHub CLI: [cli.github.com](https://cli.github.com/)
2. Install the Copilot extension:
   ```powershell
   gh extension install github/gh-copilot
   ```
3. Use `gh copilot suggest` for command-line help.

### Gemini CLI
The Gemini CLI is our primary tool for interacting with the codebase.
1. Install via npm:
   ```powershell
   npm install -g @google/gemini-cli
   ```
2. **Account Access:** Log in using your authorized package account credentials as directed by your instructor.

### Claude & Codex (via CLI Tools)
- Use CLI-based interfaces or integrated environment tools that leverage your package accounts for Claude (Anthropic) and Codex (OpenAI).
- **Account-Based Access:** Ensure you are logged into the relevant platform accounts; do not manage or store raw credentials in this project.

## 3. CLI-Based Workflow Best Practices

-   **The Golden Rule:** It is significantly harder to fix large-scale changes caused by wrong information or poorly formed instructions. **Get it right before you start.**
-   **Divide and Conquer:** Break your complex problems down into small, manageable pieces. Solving small parts sequentially is more effective than attempting a massive change at once.
-   **Context Management (CLI Commands):**
    -   Use `/clear` when switching to a completely different problem to prevent old context from interfering.
    -   Use `/compress` to distill your current conversation and stay within the AI's most effective context window.
-   **Research First:** Use external chat apps or web-based AI interfaces for broad research and complex technical questions. Get a clear mental picture of the solution before you start coding.
-   **Vibe Coding Readiness:** Only transition to "vibe coding" (direct CLI-based generation) once you have a solid plan. Avoid blind execution.
-   **Clear & Concise Instructions:** Always provide clear and specific instructions to the AI. Remember **GIGO** (Garbage In, Garbage Out).
-   **Plan Before Execution:** Use AI to help you design and plan your approach *before* you start writing or generating code.
-   **Always Check for Regression:** After integrating AI-generated changes, verify that existing functionality still works as expected.
-   **Pipe to AI:** Practice piping terminal output (like build errors) directly into your AI tools for rapid debugging.
-   **Context is King:** When using CLI tools, always ensure you are pointing the AI to the relevant files in the `src/` or `include/` directories.
-   **Verification:** AI can hallucinate. Always verify generated code by running:
    ```powershell
    pio run
    ```
-   **Documentation:** Record significant AI-assisted changes in your commit messages or a dedicated development log.

## 4. Working with Documentation & PRDs

When using AI to help with technical documentation or Product Requirements Documents (PRDs):

-   **Surgical Context Extraction:** Never feed a large PDF (like a 100-page datasheet or a massive requirement doc) into the AI if you only need a small portion.
-   **Extract First:** Manually identify and extract only the relevant tables, requirements, or function signatures.
-   **Avoid Noise:** Providing too much irrelevant context can lead to "hallucinations" or diluted results. The AI works best when the input is dense with relevant information and free of noise.
-   **PRD Alignment:** Frequently ask the AI to verify its proposed code against your specific PRD requirements to ensure the "vibe" matches the actual goals.

## 5. Code Sanity & Stability

Maintain the integrity of your codebase by following these sanity checks after any AI-assisted change:

-   **Build Verification:** Always run `pio run` immediately after integrating AI-generated code. If it doesn't compile, it's not a solution.
-   **Race Conditions & Concurrency:** AI often overlooks thread safety. If your code uses multiple tasks (FreeRTOS) or interrupts, ensure shared resources are protected by **mutexes** or **semaphores**.
-   **Memory Safety:** Check for potential memory leaks and buffer overflows. Avoid dynamic memory allocation (`malloc`/`new`) in the main loop; prefer static allocation or object pooling.
-   **Non-Blocking Logic:** Ensure the AI doesn't introduce blocking `delay()` calls in tasks that require high responsiveness. Use timers or state machines instead.
-   **Separation of Concerns:** Ensure that each logic block or function has a single, clear responsibility. Don't let AI bundle unrelated tasks into one "god function."
-   **Single Source of Truth (SSOT):** Data and configuration should live in one place. Avoid hardcoding values that should be centralized in headers or config files.
-   **No Unnecessary Duplication (DRY):** Do not repeat yourself. If you see the AI generating similar code in multiple places, refactor it into a reusable function or component.
-   **No "Black Boxes":** Do not commit code that you don't fully understand. If the AI generates a complex logic block, ask it to explain it line-by-line before you accept it.
-   **Type Safety & Error Handling:** AI often skips edge cases or proper error handling. Manually check for null pointers, buffer overflows, and return value validations.
-   **Idiomatic Consistency:** Ensure the AI-generated code follows the project's existing naming conventions and architectural patterns.
-   **Minimalism:** Avoid "spaghetti code." If an AI-generated solution feels overly complex, challenge it to provide a simpler, more direct alternative.
-   **Surgical Edits:** Prefer targeted, surgical changes over large, sweeping refactors generated by AI. This makes debugging and regression testing much easier.
