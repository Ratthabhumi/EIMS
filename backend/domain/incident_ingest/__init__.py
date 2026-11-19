"""Incident Core v1.1 event-to-incident ingestion (outbox, dispatcher, consumer).

Kept as a sibling of ``backend.domain.incident`` on purpose: that package's
``__init__`` imports the HTTP controller and auth chain, which the telemetry
worker and analyzer emitters must not pull in (import-cycle and weight risk).
Nothing here is imported eagerly; import the concrete submodule you need.
"""
