# Installing and using the connector

rubricator runs inside the Claude you already use. It needs **no API key and no model account of its own**: Claude supplies the judgement, rubricator supplies the tools, the method and a place to keep the work.

> **Your analyses are kept for 30 days after their last write.** Every save restarts the clock, so work you come back to stays; an analysis nobody touches for 30 days is deleted. To keep one for good, export it (see [Keeping an analysis](#keeping-an-analysis)). The window is a setting of the store, and the connector tells Claude the value your store actually uses.

## In a few lines

    uv tool install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"
    claude mcp add rubricator -- rubricator-mcp          # Claude Code
    # then, in Claude: "Use rubricator to compare ... "

For Claude Desktop, see below. Requires Python 3.10 or newer. rubricator is not on PyPI yet, so it installs from GitHub.

## 1. Install

Pick one. All three install the `rubricator-mcp` command and no model client (the `mcp` extra is the MCP framework and nothing else).

    uv tool install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"
    pipx install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"
    pip install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"      # in a virtual environment

Check it: `rubricator-mcp --help` prints the options, and `rubricator demo` runs a small analysis end to end with no client at all.

Find where the command landed (you need the full path for Claude Desktop): `which rubricator-mcp` on macOS and Linux, `where rubricator-mcp` on Windows.

## 2. Connect a client

### Claude Code

    claude mcp add rubricator -- rubricator-mcp

Add `--scope user` to have it in every project rather than the current one. To keep analyses in a folder you choose:

    claude mcp add rubricator -- rubricator-mcp --root ~/analyses

Check with `claude mcp list`, or `/mcp` inside a session. Claude Code starts the command itself when a session needs it.

### Claude Desktop

Claude Desktop starts local servers from its config file. Open **Settings → Developer → Edit Config**, which opens `claude_desktop_config.json` (on macOS in `~/Library/Application Support/Claude/`, on Windows in `%APPDATA%\Claude\`), and add the server:

    {
      "mcpServers": {
        "rubricator": {
          "command": "/full/path/to/rubricator-mcp"
        }
      }
    }

Use the **full path** from `which rubricator-mcp`: a desktop app does not see the `PATH` of your shell, and `"command": "rubricator-mcp"` is the usual reason a server fails to appear. To choose where analyses go, add `"args": ["--root", "/full/path/to/analyses"]`; give `--root` an absolute path for the same reason. Quit Claude Desktop completely and reopen it; start a new chat and the rubricator tools are listed among the chat's tools.

### Over HTTP, and the web app

`rubricator-mcp --transport http` serves the same tools on `http://127.0.0.1:8765/mcp`, for any client that speaks MCP over HTTP (`claude mcp add --transport http rubricator http://127.0.0.1:8765/mcp` in Claude Code). It has **no authentication** and listens on your machine only. The web app at claude.ai reaches connectors from Anthropic's servers, so it cannot reach a loopback address, and exposing the server publicly is not supported yet. Read [connector-http.md](connector-http.md) before going further.

## 3. Run a first analysis

Start a new chat, make sure the rubricator tools are on, and ask in plain words:

> Use rubricator to compare three note-taking apps for a two-person team. Start by asking me what matters before you score anything.

What the method asks of Claude, so nothing surprises you (Claude is a model, so steer it if it drifts):

1. **Claude asks about the frame first**: what is being compared, what for, who decides. This is deliberate and is the valuable part; answer it properly rather than skipping it.
2. **It proposes criteria** with definitions and what evidence would justify each score, and **asks you to confirm** them before any cell is scored. Say what you would change.
3. **It scores cells one at a time**, each with a confidence, a one-line justification and a citation to a span of the source, not to a whole document. Where the sources say nothing, the cell is left **blank with a reason** (`not-evidenced`, `indeterminate`, `not-assessed`) instead of a plausible guess. A blank is a finding, not a gap.
4. Everything is saved as it goes, so a closed chat loses nothing. Ask for a summary or the completeness counts at any point.

Give Claude your material by pasting it or pointing at files it can already read; rubricator records the sources and cites spans of them.

The method lives in prompts that Claude reads by calling the `prompts_get` tool, so if it seems to be improvising, ask it to "list the rubricator prompts and follow them". Prompts for the criteria, their confirmation, scoring a cell and resuming are written; the frame and alternatives steps are driven by the tools alone for now, and a single `run-analysis` instruction is tracked in [#77](https://github.com/thorwhalen/rubricator/issues/77). The prompts do not yet show up as slash commands in your client: that is [#80](https://github.com/thorwhalen/rubricator/issues/80).

### Coming back later

Start a new chat and say which analysis you were working on, by its id (ask Claude for the id before you close the chat): "Resume rubricator analysis `notes-apps`." Claude reads what was stored, restates where it stands, including which blanks are settled answers and which cells nobody has looked at, and proposes the next step without taking it. Within 30 days of the last write, nothing needs redoing, including your confirmation of the criteria.

## Where things are kept

Analyses are JSON files in a folder: `~/.local/share/rubricator/working/` on macOS and Linux, `%LOCALAPPDATA%\rubricator\working\` on Windows. Set `RUBRICATOR_DATA_DIR` to move the whole data root, or pass `--root` to move just the analyses. Nothing is sent anywhere by rubricator itself; what Claude reads and writes through the tools goes through your Claude client like the rest of your conversation.

### Keeping an analysis

    rubricator show notes-apps > notes-apps.json          # add --root DIR if you used one

prints the merged analysis as a [comparanda](https://github.com/thorwhalen/comparanda) document. The file is yours: the 30-day window applies only to the working folder, never to a file you exported.

## When it does not work

| symptom | usual cause |
|---|---|
| Desktop shows no rubricator tools | `command` is not a full path; or Desktop was not fully quit and reopened |
| Desktop reports the server "disconnected" | run the command by hand and read the error; a Python older than 3.10 is the usual one |
| `--root is empty` at start-up | the folder comes from a variable your client config leaves unset |
| "analysis not found" for an id you used | more than 30 days since its last write, or a different `--root` / `RUBRICATOR_DATA_DIR` than last time |
| Claude Code lists the server as failed | `claude mcp list` shows the command it ran; run that command in a terminal |
