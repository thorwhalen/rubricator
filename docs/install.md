# Installing and using the connector

rubricator runs inside the Claude you already use. It needs **no API key and no model account of its own**: Claude supplies the judgement, rubricator supplies the tools, the method and a place to keep the work.

> **Your analyses are kept for 30 days after their last write.** After that they are expired and may be deleted at any time (deletion happens when something next asks for the analysis, so do not count on an expired one lingering either). Each save restarts the clock; merely opening or reading an analysis does not. This holds for whatever folder the connector stores into, including one you choose with `--root`. To keep an analysis for good, export it (see [Keeping an analysis](#keeping-an-analysis)). The window is 30 days for `rubricator-mcp`; the connector states it to Claude in the description of `analysis_open`.

## In a few lines

    uv tool install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"
    claude mcp add rubricator -- rubricator-mcp          # Claude Code
    # then, in Claude: "Use rubricator to compare ... " (the exact words are in step 3)

For Claude Desktop, see below. Requires Python 3.10 or newer. rubricator is not on PyPI yet, so it installs from GitHub.

## 1. Install

Pick one. All three install the `rubricator-mcp` command and no model client (the `mcp` extra is the MCP framework and nothing else).

    uv tool install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"
    pipx install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"
    pip install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"      # in a virtual environment

If the command is not found afterwards, the tool's bin folder is not on your `PATH` (`uv tool update-shell` or `pipx ensurepath` fix that, then open a new terminal); with `pip`, activate the virtual environment first, and launch Claude Code from it.

Check it: `rubricator-mcp --help` prints the options, and `rubricator demo` runs a small analysis end to end with no client at all.

Find where the command landed (you need the full path for Claude Desktop): `which rubricator-mcp` on macOS and Linux, `where rubricator-mcp` on Windows.

## 2. Connect a client

### Claude Code

    claude mcp add rubricator -- rubricator-mcp

Options of `claude mcp add` go before the name: `claude mcp add --scope user rubricator -- rubricator-mcp` makes it available in every project rather than only the current one. Everything after `--` is the command and its arguments. To keep analyses in a folder you choose:

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

Use the **full path** from `which rubricator-mcp` (on Windows write the backslashes doubled, `C:\\Users\\...\\rubricator-mcp.exe`, or use forward slashes, since JSON treats a single backslash as an escape): a desktop app does not see the `PATH` of your shell, and `"command": "rubricator-mcp"` is the usual reason a server fails to appear. To choose where analyses go, add `"args": ["--root", "/full/path/to/analyses"]`; give `--root` an absolute path for the same reason. Quit Claude Desktop completely and reopen it; start a new chat and the rubricator tools are listed among the chat's tools.

### Over HTTP, and the web app

`rubricator-mcp --transport http` serves the same tools on `http://127.0.0.1:8765/mcp`, for any client that speaks MCP over HTTP (`claude mcp add --transport http rubricator http://127.0.0.1:8765/mcp` in Claude Code). It has **no authentication** and listens on your machine only. The web app at claude.ai reaches connectors from Anthropic's servers, so it cannot reach a loopback address, and a hosted connector needs a public HTTPS address and a real authorisation flow, which is not built ([#214](https://github.com/thorwhalen/rubricator/issues/214)). Read [connector-http.md](connector-http.md) before going further.

## 3. Run a first analysis

Start a new chat, make sure the rubricator tools are on, and ask in plain words. The server's instructions tell Claude to read the `run-analysis` prompt before it writes anything, and to ask you about the frame first ([#216](https://github.com/thorwhalen/rubricator/issues/216)):

> Use rubricator to compare three note-taking apps for a two-person team, in an analysis called `notes-apps`.

The method the prompts ask of Claude (it is a model, so steer it if it drifts):

1. **The frame comes first.** Claude should ask what the comparison is for before it writes anything; if it starts writing a frame you did not describe, stop it. A good frame says what is being compared, for what decision and who decides. The tools refuse to write a score until the frame, alternatives and criteria are confirmed (step 2), unless the analysis was opened with the confirmation explicitly skipped, which Claude should do only if you told it to; so skipping the conversation normally costs you a refused write, not a wrong score.
2. **It proposes criteria** with a definition and the evidence that would justify each score, and **asks you to confirm** them in chat before any cell is scored. Say what you would change.
3. **It scores one cell at a time**, each with a confidence, a justification and a quoted span of the source, not a whole document. Where it cannot score, the cell is left blank *with a reason*, and the reasons mean different things: `not-evidenced` (the sources are silent) and `indeterminate` (they conflict) are findings about the subject, finished work; `not-assessed` only means nobody has looked yet, and is still to do. A qualified blank beats a plausible guess.
4. **What Claude has written through the tools is saved as it goes**, so a closed chat loses that; criteria you discussed but Claude had not yet recorded are lost. Ask for the completeness counts at any point.

Give Claude your material by pasting it or pointing at files it can already read; rubricator records the sources and cites spans of them.

Prompts for the criteria, their confirmation, scoring a cell and resuming are written. The frame and alternatives steps are driven by the tools alone for now, and a single `run-analysis` instruction is tracked in [#77](https://github.com/thorwhalen/rubricator/issues/77). The prompts do not yet show up as slash commands in your client: that is [#80](https://github.com/thorwhalen/rubricator/issues/80).

### Coming back later

Start a new chat and say which analysis you were working on, by its id (the one you named, or ask Claude for it before you close the chat): "Use rubricator to resume analysis `notes-apps`; read the `resume` prompt first." Claude reads what was stored, restates where it stands, keeping settled blanks apart from cells nobody has looked at, and proposes the next step without taking it. A confirmation you already gave is read from the record rather than asked again, unless the criteria have changed since or only part of the analysis was confirmed. Resuming mostly reads, but it can write (for example a pending confirmation request), and any write restarts the 30 days; do not rely on resuming alone to keep an analysis alive.

## Where things are kept

Analyses are JSON files in a folder: `~/.local/share/rubricator/working/` on macOS and Linux (`$XDG_DATA_HOME/rubricator/working/` if that variable is set), `%LOCALAPPDATA%\rubricator\working\` on Windows. Set `RUBRICATOR_DATA_DIR` to move the whole data root, or pass `--root` to move just the analyses. Nothing is sent anywhere by rubricator itself; what Claude reads and writes through the tools goes through your Claude client like the rest of your conversation.

### Keeping an analysis

    rubricator show notes-apps > notes-apps.json          # add --root DIR if you used one; check the file is not empty

prints the merged analysis as a [comparanda](https://github.com/thorwhalen/comparanda) document. The file is yours: the 30-day window applies to the store, never to a file you exported. It holds the analysis document, not the confirmation and corpus records kept beside it, and it is a record to read and render, not a way back in: there is no import yet, so an exported file cannot be resumed in rubricator.

## When it does not work

| symptom | usual cause |
|---|---|
| Desktop shows no rubricator tools | `command` is not a full path; or Desktop was not fully quit and reopened |
| Desktop reports the server "disconnected" | run the same command by hand in a terminal and read its error; a wrong or unescaped path in the config is the usual cause |
| `--root is empty` at start-up | the folder comes from a variable your client config leaves unset |
| An old analysis id comes back empty, or "analysis not found" | more than 30 days since its last write (opening an expired id with a question can start a fresh empty analysis under it), or a different `--root` / `RUBRICATOR_DATA_DIR` than last time |
| Claude Code lists the server as failed | `claude mcp list` shows the command it ran; run that command in a terminal |
