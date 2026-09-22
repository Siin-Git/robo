"""Queue SQLite demo requests before they compete for the write transaction."""
import asyncio

from ...db.config import get_backend
from ...local.capstone import enabled


class CapstoneRequestQueue:
    def __init__(self, app):
        self.app = app
        self._loop = None
        self._gate = None

    async def __call__(self, scope, receive, send):
        if (scope['type'] != 'http' or not scope['path'].startswith('/api/v1/')
                or not enabled() or get_backend() != 'sqlite'):
            await self.app(scope, receive, send)
            return
        # Each worker has one event loop. TestClient can restart the same app
        # on a new loop, so do not reuse a lock bound to its previous lifespan.
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop, self._gate = loop, asyncio.Lock()
        # get_db already serializes demo transactions with BEGIN IMMEDIATE.
        # Waiting here avoids consuming DB connections/worker threads and
        # exhausting SQLite's busy timeout during a simultaneous login burst.
        # The gate covers dependency cleanup/commit as well as the response.
        async with self._gate:
            await self.app(scope, receive, send)
