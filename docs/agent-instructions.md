# Maintaining agent instructions

## Shared baseline

`AGENTS.md` is the canonical baseline. `.github/copilot-instructions.md` is an identical generated
copy, and `CLAUDE.md` imports the baseline using `@AGENTS.md`.

After editing the baseline, run these commands from the repository root with Python 3:

```sh
python scripts/sync_agent_instructions.py
python scripts/sync_agent_instructions.py --check
```

Commit both baseline files together. The script uses only the standard library and does not require
the model environment. A future CI workflow can run the check command. Keep the baseline short:
shared practices and task routing belong here; detailed specialized workflows do not.

## Portability and limits

The full Copilot baseline is deliberate: it does not depend on an interface following a link to
`AGENTS.md`, supporting skills, or checking out symlinks correctly on Windows. Some agents may load
both copies, so keep them identical and concise. This accepts possible duplication of the small
baseline in exchange for broader compatibility; detailed guides are never copied into it.

Open Lighthouse as the project root. Custom instructions must be enabled in the client. Automatic
loading depends on client version, interface, feature support, and settings; this framework cannot
force every Copilot surface (including inline completions) to read instructions or open task guides.
When a client cannot retrieve files, attach the baseline and the one relevant guide to the request.

To check a new client, ask it to identify the repository instructions and explain when it would load
a task guide. Inspect its instruction references/context display where available. For a registered
guide, try both a matching request and an unrelated request, and verify that only the matching request
loads the detailed guide. This is a client smoke check, not a guarantee of instruction adherence.

## Adding task guides

1. Copy `agent-tasks/TEMPLATE.md` to a descriptive filename in `agent-tasks`.
2. Define clear triggers, exclusions, required context, workflow, and acceptance criteria.
3. Add a short entry and link to `agent-tasks/index.md`.
4. Put large examples and specifications in supporting files and link them where needed.

The index is intentionally small. Agents read it for specialized work and retrieve only matching
guides. This uses ordinary Markdown and file access rather than a vendor-specific invocation syntax.
Do not use automatic imports for detailed task guides: imports would make them always-on context.

Native skills are an optional discovery layer. Codex and supported Copilot agents can discover
`.agents/skills/<task>/SKILL.md`. Such a skill should have a precise name/description and instruct the
agent to read the canonical task guide, avoiding a second copy of the workflow. Claude native skills
use a separate entry point; explicit routing through the baseline already provides a common fallback.
Introduce these wrappers when a real task guide is ready, not as empty skills that activate prematurely.

## Reference documentation

- [Codex repository instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Codex skills](https://learn.chatgpt.com/docs/build-skills)
- [Copilot repository instructions across IDEs](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions-in-your-ide/add-repository-instructions-in-your-ide)
- [Copilot skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- [Claude instruction imports](https://code.claude.com/docs/en/memory)
