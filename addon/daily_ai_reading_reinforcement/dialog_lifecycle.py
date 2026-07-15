"""Process-wide cancellation registry for DAIRR add-on dialogs.

Only lifecycle managers are weakly registered here; no Qt widget or Anki
collection is retained.  Supported Anki hooks may call ``invalidate_all`` on
profile/collection teardown, while each dialog also invalidates its own
manager from ``done``/``closeEvent``.
"""

from __future__ import annotations

from threading import RLock
from typing import Any
from weakref import WeakSet

try:
    from .background_operations import AddonBackgroundOperations
except ImportError:  # source-tree tests without importing the aqt wrapper
    from background_operations import AddonBackgroundOperations


_lock = RLock()
_managers: WeakSet[AddonBackgroundOperations] = WeakSet()


def register(manager: AddonBackgroundOperations) -> None:
    with _lock:
        _managers.add(manager)


def unregister(manager: AddonBackgroundOperations) -> None:
    with _lock:
        _managers.discard(manager)


def invalidate_all(*_args: Any, **_kwargs: Any) -> None:
    with _lock:
        managers = tuple(_managers)
    for manager in managers:
        manager.invalidate()


def register_supported_hooks(gui_hooks: Any) -> tuple[str, ...]:
    """Attach only hooks exposed by the running Anki version."""
    if gui_hooks is None:
        return ()
    attached: list[str] = []
    for name in ("profile_will_close", "collection_will_close"):
        hook = getattr(gui_hooks, name, None)
        append = getattr(hook, "append", None)
        if not callable(append):
            continue
        try:
            if invalidate_all not in hook:
                append(invalidate_all)
                attached.append(name)
        except TypeError:
            # Some hook collections do not implement membership checks.
            append(invalidate_all)
            attached.append(name)
    return tuple(attached)
