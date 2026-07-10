"""Platform-agnostic learning and article-generation core for DAIRR.

This package deliberately has no dependency on Anki's ``aqt``/``mw`` APIs or
on a particular application shell. Hosts provide persistence and background
execution through the adapter contracts in :mod:`dairr_core.adapters`.
"""
