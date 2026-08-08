"""DSS internal platform — FastAPI application package.

The API process and the worker process both import from this package, so shared
concerns (settings, database engine, models, services) live here exactly once.
"""
