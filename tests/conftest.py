from collections.abc import AsyncIterator

import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

from fixtures.server import create_app


@pytest_asyncio.fixture
async def fixture_server() -> AsyncIterator[str]:
    server = TestServer(create_app(), host="127.0.0.1")
    await server.start_server()
    try:
        yield str(server.make_url("/"))
    finally:
        await server.close()
