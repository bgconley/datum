# Claude Code Datum Hooks

These hooks enforce Datum Phase 9 lifecycle discipline for Claude Code sessions:

- `read-before-write`
- `append-after-write`
- `finalize-before-stop`

## Files

- `session-start.sh`: starts or resumes the Datum lifecycle session and injects lightweight context
- `pre-tool-use.sh`: blocks or warns on mutating tools when no Datum preflight exists
- `post-tool-use.sh`: records deltas for mutating tool activity
- `pre-compact.sh`: flushes accumulated deltas before compaction
- `stop.sh`: blocks dirty-session stop in blocking mode; otherwise flushes/finalizes
- `session-end.sh`: best-effort flush/finalize cleanup
- `install-hooks.sh`: prints a Claude Code hook config JSON snippet

## Usage

Generate the Claude Code hook config:

```bash
bash hooks/claude/install-hooks.sh http://localhost:8001/api/v1 your-project-slug
```

Set these environment variables if needed:

- `DATUM_API`
- `DATUM_API_KEY`
- `DATUM_PROJECT_SLUG`

`session-start.sh` also writes `DATUM_SESSION_ID` into `CLAUDE_ENV_FILE` when Claude provides it so subsequent Bash tools can reuse the same lifecycle session.
