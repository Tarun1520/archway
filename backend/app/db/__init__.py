"""
Storage: saving and loading Archway's own data in SQLite.

    connection.py     open a database connection
    migrations.py     create or upgrade the tables (runs the files in sql/)
    errors.py         the "not found" error the repositories raise
    projects_repo.py  save and load projects
    messages_repo.py  save and load messages
    runs_repo.py      save and load runs, enforcing the lifecycle rules

LEARNING NOTE: what is a "repository" (repo) here?
    Not a git repository. In backend code a repository is a small module that
    hides the SQL for one kind of record. The rest of the app calls
    `create_project(...)` and never writes SQL itself. Swapping SQLite for
    another database would only change the files in this folder.

Learn more: LEARNING_GUIDE.md topic 35.
"""
