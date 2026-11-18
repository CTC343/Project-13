"""Read audit rows saved in the same transaction as the result receipts."""

from contextlib import closing
import json

from task_state import DATABASE, connect


def read_rounds():
    if not DATABASE.exists():
        return []
    with closing(connect()) as db:
        return [json.loads(row[0]) for row in db.execute("SELECT audit FROM rounds ORDER BY rowid")]
