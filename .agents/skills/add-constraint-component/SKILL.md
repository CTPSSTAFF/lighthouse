---
name: add-constraint-component
description: Add a person or household constraint component to Lighthouse, beginning with user questions to establish its behavioral meaning, population, evidence, and downstream scope. Use for new constraint attributes and substantive changes to their definition, not routine calibration, unrelated components, or general code cleanup.
---

# Add a constraint component

Draft for team review. Follow the repository baseline and read the canonical
[task guide](../../../docs/agent-tasks/add-constraint-component.md) before implementation.

Start by establishing what the user wants. Ask about unresolved modeling decisions rather than
borrowing behavioral assumptions from worked examples. Present the resulting component contract for
confirmation before implementing behavior, unless the user has already confirmed that contract in the conversation.
While awaiting answers, inspect existing code and dependencies without making speculative changes.

The canonical guide contains the modeling rationale, annotated Python and configuration examples,
and integration checks. No external design document or pull request is needed to use it. Examples
illustrate mechanics; they do not establish the user's intended rules or parameter values.
