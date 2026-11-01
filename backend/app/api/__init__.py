"""
The HTTP API: the URLs the frontend calls.

One file per group of endpoints:

    deps.py           shared "dependencies" (settings, a database connection)
    health.py         GET  /api/health
    config_routes.py  GET  /api/config          (modes, badge, limits; no secrets)
    projects.py       /api/projects ...         (create, list, get, rename, delete)
    messages.py       /api/projects/{id}/messages
    runs.py           /api/projects/{id}/runs and /api/runs/{id}
    sample_briefs.py  GET  /api/sample-briefs   (demo data)
    demo_events.py    GET  /api/demo/events     (demo live-progress stream)

Every route file creates a `router`; app/main.py plugs them all in. To add a
group of endpoints, add a file here and one `include_router` line in main.py.

Learn more: LEARNING_GUIDE.md topic 34.
"""
