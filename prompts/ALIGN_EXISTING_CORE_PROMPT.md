# CONTEXT

This project already has an existing core implementation.

You must strictly follow in /DOCS directory

- CORE_CONCEPTS.md
- ARCHITECTURE_RULES.md
- UI_COMPONENTS.md
- REFERENCE_WORKFLOWS.md

Your role is NOT to rebuild the project from scratch.
Your role is to analyze the existing core, align it with the project rules, and prepare it for safe incremental development.

---

# OBJECTIVE

Review the existing core implementation and determine:

- what already matches the architecture
- what violates the architecture
- what is missing for the next workflow
- what should be kept, refactored, or removed

---

# SCOPE

Analyze the current codebase, especially:

- domain models
- application services
- storage / repositories
- reusable UI components
- current tree / graph related code if present

Do NOT rewrite everything.
Do NOT replace working code without justification.

---

# TASK

Produce an alignment review of the existing core.

You must:

1. identify existing concepts already implemented
2. map them to CORE_CONCEPTS.md
3. identify divergences
4. identify duplications
5. identify dangerous abstractions
6. propose the minimal refactoring path

---

# CONSTRAINTS

- Do NOT invent new concepts
- Do NOT create a parallel architecture
- Do NOT rebuild from scratch unless a part is fundamentally broken
- Prefer adaptation over replacement
- Prefer small refactors over large rewrites
- Keep the existing core if it is compatible enough

---

# OUTPUT FORMAT

1. CURRENT CORE MAP
   - existing files/modules
   - responsibility of each
   - mapping to official concepts

2. ARCHITECTURE GAPS
   - violations of CORE_CONCEPTS.md
   - violations of ARCHITECTURE_RULES.md
   - UI reuse problems
   - duplication / overlap

3. KEEP / REFACTOR / REMOVE
   - what should stay as is
   - what should be refactored
   - what should be removed or deprecated

4. MINIMAL ALIGNMENT PLAN
   - ordered steps
   - smallest safe path forward

5. NEXT SAFE IMPLEMENTATION TARGET
   - recommend the next workflow or component to implement

---

# CRITICAL RULE

Do not produce a theoretical redesign.
Base the analysis on the actual codebase.

If the current code is good enough, preserve it.
If something is wrong, explain precisely why.

---

# FINAL INSTRUCTION

The goal is to make the current project safer, clearer, and more reusable without restarting the project.