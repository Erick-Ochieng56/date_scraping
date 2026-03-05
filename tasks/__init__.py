"""
Project-level Celery tasks package.

Celery autodiscovery is configured for Django apps; we expose a shim in
`crawler/tasks.py` that imports these tasks so they are discovered.
"""

