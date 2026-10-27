"""terminal-notify for Hermes: registers the hooks that raise a notification."""

import threading

try:
    from . import notify
except ImportError:  # loaded by path, not as a package
    import importlib.util
    import os

    _spec = importlib.util.spec_from_file_location(
        "terminal_notify_core", os.path.join(os.path.dirname(__file__), "notify.py")
    )
    notify = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(notify)

# A subagent's turns run in the same process, under their own session id: only
# the main agent's turns ask for the person.
_children = set()
_lock = threading.Lock()


def _subagent_start(child_session_id=None, **kwargs):
    with _lock:
        _children.add(child_session_id)


def _subagent_stop(child_session_id=None, **kwargs):
    with _lock:
        _children.discard(child_session_id)


def _on_complete(assistant_response=None, session_id=None, **kwargs):
    with _lock:
        if session_id in _children:
            return
    notify.notify("complete", {"assistant_response": assistant_response})


def _on_approval(command=None, description=None, **kwargs):
    notify.notify("permission", {"command": command, "description": description})


def _on_input(kind=None, prompt=None, **kwargs):
    # An approval prompt is announced by `pre_approval_request`.
    if kind == "approval":
        return
    notify.notify("question", {"kind": kind, "prompt": prompt})


def register(ctx):
    ctx.register_hook("post_llm_call", _on_complete)
    ctx.register_hook("pre_approval_request", _on_approval)
    ctx.register_hook("on_human_input_request", _on_input)
    ctx.register_hook("subagent_start", _subagent_start)
    ctx.register_hook("subagent_stop", _subagent_stop)
