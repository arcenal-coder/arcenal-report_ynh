"""Optional interoperability check using the official Python MCP 1.x client.

Install the client in a disposable tools directory, not in application runtime.
All data and credentials here are synthetic and disappear with the fixture.
"""
import asyncio
import tempfile
import threading
from pathlib import Path
from wsgiref.simple_server import make_server

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

import app
import database
import integration_service


async def check(url, token, mission_uuid):
    async with streamablehttp_client(url, headers={'Authorization': 'Bearer ' + token}) as (read, write, _):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 5
            result = await session.call_tool('report_list_missions', {})
            assert not result.isError
            assert mission_uuid in result.content[0].text
            await session.send_ping()
            print(f'MCP SDK interoperability OK: {initialized.protocolVersion}, {len(tools.tools)} read-only tools, initialize/list/call/ping.')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        app.DATABASE_PATH = str(Path(directory) / 'sdk.sqlite3')
        database.initialise(app.DATABASE_PATH)
        mission_uuid = database.list_missions(app.DATABASE_PATH)[0]['uuid']
        credential = integration_service.create_credential(app.DATABASE_PATH, {
            'label': 'Disposable SDK test', 'missions': [mission_uuid],
            'scopes': list(integration_service.SCOPES), 'confirmed': True,
        }, 'test')
        server = make_server('127.0.0.1', 0, app.application)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            asyncio.run(check(f'http://127.0.0.1:{server.server_port}/mcp', credential['token'], mission_uuid))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
