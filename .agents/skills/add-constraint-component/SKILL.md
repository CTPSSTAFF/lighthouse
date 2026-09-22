---
name: add-constraint-component
description: Add a person or household constraint component to Lighthouse, beginning with user questions to establish its behavioral meaning, population, evidence, and downstream scope. Use for new constraint attributes and substantive changes to their definition, not routine calibration, unrelated components, or general code cleanup.
---

# Add a constraint component

Draft for team review. Follow the repository baseline and read the canonical
[task guide](../../../docs/agent-tasks/add-constraint-component.md) before implementation.

Start by establishing what the user wants. Ask about unresolved modeling decisions rather than
borrowing answers from example PRs. Present the resulting component contract for confirmation before
implementing behavior, unless the user has already confirmed that contract in the conversation.
While awaiting answers, inspect existing code and dependencies without making speculative changes.

Read the guide's source notes only when checking rationale, resolving a conflict, or adapting one of
the PR examples. Do not load the original design document and both PRs on every invocation.
