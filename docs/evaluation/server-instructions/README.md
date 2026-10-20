# Server instructions: does a connector-only model find the method?

[#216](https://github.com/thorwhalen/rubricator/issues/216). A model that has only the connector sees the server instructions (`_INSTRUCTIONS` in `rubricator/mcp/server.py`), the tool list and the prompt names, and nothing else. Before this change, nothing it read told it that the method lives in the prompts, or that it should ask the user about the frame before calling `frame_set`.

**The check.** Each subject saw a packet with the server instructions, every implemented tool's contract line, the list of prompt names, and one user message: *"Use rubricator to compare three note-taking apps for a two-person team, in an analysis called `notes-apps`."* It answered with the tool calls it would make before its first reply, and that reply. There was one blind run per arm. The "before" arm used the instructions on main; the "after" arm used this change.

| arm | reads `run-analysis` before writing | reads a stage prompt | writes a frame the user did not give | asks for the decision / who decides |
|---|---|---|---|---|
| before, Haiku | no | no | no | partly (who decides) |
| before, Sonnet | no | `frame` | no | yes |
| **after, Haiku** | **yes** | `frame` | no | yes |
| **after, Sonnet** | **yes** | `frame` | no | yes |

- **What changed.** Both models now read `run-analysis` before their first write, so the stage-by-stage prompts reach them. Before, Haiku read no prompt at all.
- **What did not change.** No arm wrote a frame before asking, even before this change. On this one opening message, the "elicit the frame first" sentence is not what kept them from writing; the tool contracts already pushed them to ask. It is kept because the opening message is the easy case.
- **Not established.** One run per arm, a single turn, and scenarios written by the change's author. Nothing here shows a whole run staying on the method.
