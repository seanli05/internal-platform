"""Background worker — a second entrypoint over the same `app` package.

Phase 0 is a stub: it logs a liveness line on an interval and shuts down cleanly.
Photo processing (CLIP embeddings, face detection) arrives in Phase 4.
"""
