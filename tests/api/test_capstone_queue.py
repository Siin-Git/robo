import asyncio
import sqlite3

import httpx
import pytest

from src.api.middleware.capstone_queue import CapstoneRequestQueue


def test_thirteen_transactions_queue_without_blocking_health(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_PROFILE', 'local')
    monkeypatch.setenv('CAPSTONE_DEMO', '1')
    monkeypatch.setenv('DATABASE_BACKEND', 'sqlite')
    database = tmp_path / 'queue.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE completed (id INTEGER PRIMARY KEY)')

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def app(scope, receive, send):
            if scope['path'].startswith('/api/v1/'):
                # Without admission control, the other 12 transactions fail
                # immediately while the first slow transaction holds the DB.
                with sqlite3.connect(database, timeout=0) as db:
                    db.execute('BEGIN IMMEDIATE')
                    entered.set()
                    await release.wait()
                    await asyncio.sleep(0.005)
                    db.execute('INSERT INTO completed DEFAULT VALUES')
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'OK'})

        queue = CapstoneRequestQueue(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=queue), base_url='http://test') as client:
            calls = [asyncio.create_task(client.get('/api/v1/test')) for _ in range(13)]
            await entered.wait()
            health = await asyncio.wait_for(client.get('/health'), timeout=1)
            assert health.status_code == 200
            release.set()
            responses = await asyncio.wait_for(asyncio.gather(*calls), timeout=3)
            assert all(r.status_code == 200 for r in responses)

    asyncio.run(scenario())
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM completed').fetchone()[0] == 13


def test_cancelled_request_releases_queue(monkeypatch):
    monkeypatch.setenv('APP_PROFILE', 'local')
    monkeypatch.setenv('CAPSTONE_DEMO', '1')
    monkeypatch.setenv('DATABASE_BACKEND', 'sqlite')

    async def scenario():
        entered = asyncio.Event()

        async def app(scope, receive, send):
            if scope['path'].endswith('/cancel'):
                entered.set()
                await asyncio.Event().wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'OK'})

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=CapstoneRequestQueue(app)), base_url='http://test') as c:
            first = asyncio.create_task(c.get('/api/v1/cancel'))
            await entered.wait()
            second = asyncio.create_task(c.get('/api/v1/next'))
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            assert (await asyncio.wait_for(second, timeout=1)).status_code == 200

    asyncio.run(scenario())


@pytest.mark.parametrize('profile,backend', [('live', 'sqlite'), ('local', 'postgres')])
def test_other_profiles_remain_concurrent(monkeypatch, profile, backend):
    monkeypatch.setenv('APP_PROFILE', profile)
    monkeypatch.setenv('CAPSTONE_DEMO', '1')
    monkeypatch.setenv('DATABASE_BACKEND', backend)

    async def scenario():
        both_entered = asyncio.Event()
        count = 0

        async def app(scope, receive, send):
            nonlocal count
            count += 1
            if count == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), timeout=1)
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'OK'})

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=CapstoneRequestQueue(app)), base_url='http://test') as c:
            results = await asyncio.gather(c.get('/api/v1/one'), c.get('/api/v1/two'))
            assert all(r.status_code == 200 for r in results)

    asyncio.run(scenario())
