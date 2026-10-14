# Running the connector over Streamable HTTP

The connector has two transports and one server. `rubricator-mcp` (stdio) is how a desktop client starts it as a child process; `rubricator-mcp --transport http` serves the same tools, prompts and resources over the MCP Streamable HTTP transport. Both run the single server that `rubricator.mcp.server.make_server` builds, so the advertised surface cannot differ between them.

    rubricator-mcp --transport http                 # http://127.0.0.1:8765/mcp
    rubricator-mcp --transport http --port 9000 --root ./analyses

## Auth: there is none, and that is a stated assumption

**The server authenticates nobody.** It assumes one trusted user on one machine. Everything it does follows from that:

- **It binds to loopback (`127.0.0.1`) by default**, and refuses to bind anything else unless you pass `--allow-remote`. The flag exists so that a remote bind is a decision, not an accident; it does not add protection.
- **There is one store and one trust domain.** Anyone who can reach the port can list, read, write and overwrite every analysis in the `--root` directory. There is no per-user separation and no read-only mode.
- **The Host and Origin headers are checked.** A page open in the user's browser cannot drive a loopback server through DNS rebinding or a cross-origin request from a remote site: a foreign `Host` is answered `421`, a foreign `Origin` `403`. It is not authentication (a non-browser client sets any header it likes), and a page served from *another local port* (`http://localhost:3000`) counts as local, so do not run untrusted web apps on the same machine while this is up.
- **No TLS.** Traffic is plain HTTP. Fine on loopback; not across a network.

### Putting it on a network

Do not, without something in front that authenticates and terminates TLS (a reverse proxy with its own login, an SSH tunnel, a private network such as a VPN). A hosted connector reached from a vendor's cloud needs a public HTTPS URL and a real authorisation flow; this server provides neither, and shipping that is tracked in [#214](https://github.com/thorwhalen/rubricator/issues/214). When fronting it with a proxy that rewrites `Host`, list the public name:

    rubricator-mcp --transport http --allow-host rubricator.example.org

`--allow-host` takes plain names (wildcards are refused: the check would otherwise be silently off) and adds to the loopback names. A non-loopback bind (`--host 0.0.0.0 --allow-remote`) prints a warning to stderr and accepts, as `Host`, the bound address, the loopback names and whatever `--allow-host` names; a remote client reaching it by any other name is answered `421` until the name is listed. The framework's `FASTMCP_HTTP_ALLOWED_HOSTS` environment variable is merged into that list, so keep it out of the environment unless you mean it.

## Options

| flag | default | |
|---|---|---|
| `--transport` | `stdio` | `stdio` or `http` |
| `--host` | `127.0.0.1` | non-loopback needs `--allow-remote` |
| `--port` | `8765` | |
| `--path` | `/mcp` | the endpoint a client connects to |
| `--allow-remote` | off | permit a non-loopback `--host` |
| `--allow-host` | none | extra accepted `Host` name, repeatable |
| `--root` | user-data store | where analyses live; both transports |
