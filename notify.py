"""terminal-notify: a Hermes plugin that raises a desktop notification through
the terminal Hermes runs in (OSC 777, 9 or 99, or a bell, picked for the
terminal).

Made by the team behind Agent Terminal: https://4nuva.dev/agent-terminal/

Hermes ignores what an observer hook returns, so the sequence is written to
the controlling terminal. There is no network and no dependency. Every
function here swallows its errors: a notification must never get in the way
of a session.
"""

import os
import re
from typing import Optional

ESC = "\x1b"
BEL = "\x07"
ST = ESC + "\\"

FORMATS = ("auto", "osc777", "osc9", "osc99", "all", "bell", "off")

# Known key and token shapes, masked before any text leaves the session: a
# notification can land on a lock screen or a paired phone.
SECRETS = [
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{12,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{8,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:@/]+:[^\s@/]+@", re.I),  # credentials in a URL
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
    re.compile(
        r"\b(api[_-]?key|token|secret|password|passwd|pwd|authorization)(\s*[=:]\s*)\S+", re.I
    ),
    re.compile(r"\b[A-Za-z0-9+/_-]{40,}={0,2}"),
]

# C0, DEL and C1 control characters.
_CONTROL = re.compile("[%s-%s%s-%s]" % (chr(0), chr(0x1F), chr(0x7F), chr(0x9F)))
# Mongolian vowel separator and zero-width space: blank to the eye.
_BLANK = chr(0x180E) + chr(0x200B)
_BLANKS = re.compile(r"[\r\n\t]+")
_SPACES = re.compile(r"\s+")


def mask(s: str) -> str:
    for rx in SECRETS:
        s = rx.sub(
            lambda m: f"{m.group(1)}{m.group(2)}***" if rx.groups == 2 else "***", s
        )
    return s


def clean(s) -> str:
    """One line of plain text: no control characters (C0, DEL, C1), so nothing
    in it can end the escape sequence early or start another one."""
    s = "" if s is None else str(s)
    s = _CONTROL.sub("", _BLANKS.sub(" ", s))
    return _SPACES.sub(" ", mask(s)).strip()


def cap(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def first_sentences(text, count: int) -> str:
    """The first sentences of a reply, without code blocks or inline code."""
    t = str(text or "")
    t = re.sub(r"```[\s\S]*?(```|$)", " ", t)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"^#+\s+", "", t, flags=re.M)
    t = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", t)
    t = clean(t)
    if not t:
        return ""
    parts = re.findall(r"[^.!?]+(?:[.!?]+(?=\s|$)|$)", t) or [t]
    return " ".join(p.strip() for p in parts[:count]).strip()


def summarize(value) -> str:
    """The part of a tool call worth naming: its command, file, URL, ..."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for k in ("command", "file_path", "path", "url", "pattern", "query", "description", "prompt"):
        if isinstance(value.get(k), str) and value[k]:
            return value[k]
    for v in value.values():
        if isinstance(v, str) and v:
            return v
    return ""


def option(env, key: str, fallback: str) -> str:
    """A setting from the environment: `TERMINAL_NOTIFY_<KEY>`."""
    v = env.get(f"TERMINAL_NOTIFY_{key.upper()}")
    return v.strip() if isinstance(v, str) and v.strip() else fallback


def flag(env, key: str, fallback: bool) -> bool:
    v = option(env, key, "")
    if not v:
        return fallback
    return not re.fullmatch(r"(0|false|no|off)", v, re.I)


def detect_format(env) -> str:
    """Which sequence the terminal shows as a notification."""
    program = str(env.get("TERM_PROGRAM", "")).lower()
    term = str(env.get("TERM", "")).lower()
    # Agent Terminal shows OSC 777 with its title and body, and forwards it to
    # the phones paired with it.
    if env.get("AGENT_TERMINAL_SESSION_ID"):
        return "osc777"
    if env.get("KITTY_WINDOW_ID") or term == "xterm-kitty":
        return "osc99"
    if (
        program in ("ghostty", "warpterminal")
        or env.get("GHOSTTY_RESOURCES_DIR")
        or "rxvt" in term
    ):
        return "osc777"
    if program in ("iterm.app", "wezterm") or env.get("WT_SESSION") or env.get("ConEmuPID"):
        return "osc9"
    # Terminals with no notification sequence: the bell at least gets a look.
    if program in ("apple_terminal", "vscode"):
        return "bell"
    return "osc9"


def sequence(fmt: str, title: str, body: str) -> Optional[str]:
    if fmt == "osc777":
        # `;` separates the fields, so neither part may hold one.
        return f"{ESC}]777;notify;{title.replace(';', ',')};{body.replace(';', ',')}{BEL}"
    if fmt == "osc9":
        # A body that starts with a number reads as a ConEmu command (`9;4`
        # progress, ...).
        text = f"{title}: {body}"
        if re.match(r"^[\s" + _BLANK + r"]*[+-]?\d", text):
            text = f"· {text}"
        return f"{ESC}]9;{text}{BEL}"
    if fmt == "osc99":
        return f"{ESC}]99;;{(title + ': ' + body).replace(';', ',')}{ST}"
    if fmt == "all":
        # Every notification sequence, for a terminal the detection does not
        # know. 777 goes last: Agent Terminal keeps the last notice of a
        # burst, and 777 is the one that carries the title.
        return "".join(sequence(f, title, body) for f in ("osc9", "osc99", "osc777"))
    if fmt == "bell":
        return BEL
    return None


def build(event: str, data: dict, env, cwd: str = "") -> Optional[dict]:
    """The notification for a Hermes event, or None when it raises none.

    `event` is one of "complete" (a turn finished), "permission" (a command
    needs approval) and "question" (Hermes asks the person for input).
    """
    if not isinstance(data, dict):
        return None
    details = flag(env, "details", True)
    if event == "complete":
        ctx = first_sentences(data.get("assistant_response"), 2) if details else ""
        body = "Task complete" + (f": {ctx}" if ctx else "")
    elif event == "permission":
        sum_ = cap(clean(summarize(data.get("command") or data.get("description"))), 80) if details else ""
        body = "Permission needed" + (f": {sum_}" if sum_ else "")
    elif event == "question":
        q = clean(data.get("prompt")) if details else ""
        body = "Question" + (f": {q}" if q else " waiting")
    else:
        return None
    folder = os.path.basename(str(cwd or "").rstrip("/\\")) or "Hermes"
    # Both separators: a Windows cwd on a POSIX host keeps its backslashes.
    folder = folder.split("\\")[-1] or "Hermes"
    return {"title": cap(clean(f"Hermes · {folder}"), 80), "body": cap(clean(body), 200)}


def render(event: str, data: dict, env, cwd: str = "") -> Optional[str]:
    """The escape sequence for an event, or None."""
    fmt = option(env, "format", "auto").lower()
    if fmt not in FORMATS:
        fmt = "auto"
    if fmt == "off":
        return None
    if fmt == "auto":
        fmt = detect_format(env)
    n = build(event, data, env, cwd)
    return sequence(fmt, n["title"], n["body"]) if n else None


def write_to_terminal(seq: str) -> bool:
    """Write to the controlling terminal. Hermes owns stdout, and a hook's
    return value is dropped, so the sequence goes straight to the TTY."""
    for target in ("/dev/tty", "CONOUT$"):
        try:
            with open(target, "w", encoding="utf-8", errors="ignore") as tty:
                tty.write(seq)
                tty.flush()
            return True
        except OSError:
            continue
    return False


def notify(event: str, data: dict) -> None:
    try:
        seq = render(event, data, os.environ, os.getcwd())
        if seq:
            write_to_terminal(seq)
    except Exception:
        pass
