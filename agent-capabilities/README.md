# Agent capabilities

Tool-agnostic definitions of the reusable workflows and specialised subagents used in this repository. The process they implement is `docs/process.md`; the role texts they point at are `docs/team/`.

| Folder | What | Form |
|---|---|---|
| `implement-issue/` | Run one issue through PM → author review → engineer → QA → PR | Skill (`SKILL.md`, Agent Skills convention) |
| `review-api-change/` | Launch the API reviewer on the current branch | Skill |
| `debug-ci-failure/` | Investigate a red CI run (arrives with issue #16) | Skill |
| `subagents/` | `pm`, `software-engineer`, `qa-engineer`, `api-reviewer` | Markdown with frontmatter (`name`, `description`, optional `tools`) |

**How a coding agent finds them.** Claude Code discovers `.claude/skills/<name>/SKILL.md` and `.claude/agents/<name>.md`; those paths are symbolic links into this folder, so there is one copy. Other agents (Codex, OpenCode, Cursor and the rest) read `.agents/skills/` and `.agents/agents/` or can be pointed at these folders directly. The `tools:` line restricts what a subagent may use in Claude Code; agents that do not support it ignore it, and the role text says the same restriction in words.
