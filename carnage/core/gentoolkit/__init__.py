"""Shared primitives for the gentoolkit wrappers."""

import threading

portage_lock = threading.Lock()
"""
Serializes in-process portage access across worker threads.

Portage is not thread-safe for concurrent use (its config object raises
"Configuration is locked" and its lazy imports race). The single-thread
executors in the sibling modules serialize within one module, but workers
in different modules - or direct queries like parsed_contents() - still
meet inside portage. Hold this around any blocking portage call made off
the loop.
"""
