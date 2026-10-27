# terminal-notify

> **From the makers of [Agent Terminal](https://4nuva.dev/agent-terminal/).**
> In Agent Terminal these notifications also reach your paired phone, where you
> can open the session and reply.

A Hermes plugin that raises a desktop notification through your terminal when Hermes:

- finishes a turn: `Task complete: Fixed the failing test. All 42 tests pass.`
- needs a permission: `Permission needed: npm run deploy`
- asks you a question: `Question: Which database should I use?`

The title names the project folder (`Hermes · my-app`), so you can tell sessions apart.

## Install

```
hermes plugins install 4nuva/hermes-terminal-notify --enable
```

No dependencies.

## Terminals

The plugin writes a notification escape sequence to the terminal, and picks the sequence for the terminal it detects:

| Terminal | Sequence |
| --- | --- |
| [Agent Terminal](https://4nuva.dev/agent-terminal/) (desktop and phone) | OSC 777 |
| Ghostty, Warp, urxvt | OSC 777 |
| Windows Terminal, iTerm2, WezTerm, ConEmu | OSC 9 |
| kitty | OSC 99 |
| macOS Terminal, VS Code | bell |
| anything else | OSC 9 |

Some terminals only show notifications while their window is in the background, and some need notifications turned on in their own settings (iTerm2: Profiles → Terminal → Notifications). Inside tmux, sequences reach the outer terminal only with `allow-passthrough on`.

## Options

Set these as environment variables:

| Variable | Default | What it does |
| --- | --- | --- |
| `TERMINAL_NOTIFY_FORMAT` | `auto` | `auto`, `osc777`, `osc9`, `osc99`, `all`, `bell` or `off`. `all` sends all three sequences, for a terminal `auto` does not know; a terminal that reads more than one (Ghostty reads 9 and 777) shows more than one. |
| `TERMINAL_NOTIFY_DETAILS` | on | Set to `false` to leave the start of the reply, the command a permission is for and the question out of notifications. |

## Privacy

Nothing leaves your machine except through your terminal. Before any text goes into a notification, known key and token formats (API keys, GitHub and Slack tokens, JWTs, bearer tokens, `password=...`, credentials in URLs, long random strings) are replaced with `***`. Turn details off to keep reply text and commands out of notifications entirely, for example when notifications show on a lock screen.

Subagents' turns do not notify; only the main session's do.

## Development

```
python3 -m unittest discover -s tests
```

## License

The code is MIT. The Agent Terminal name is not covered by that licence; all rights reserved. See [LICENSE](LICENSE).

---

**[Agent Terminal](https://4nuva.dev/agent-terminal/)** is a terminal for running coding agents, on your desktop and your phone. It shows these notifications on the desktop and forwards them to your paired phone.
