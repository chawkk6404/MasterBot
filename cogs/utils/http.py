import requests
import aiohttp
import asyncio


class AsyncHTTPClient:
    def __init__(self, base_url, *, connector: aiohttp.BaseConnector = None, headers=None):
        self.base = base_url
        self._connector = connector
        self.session = aiohttp.ClientSession(connector=self._connector, headers=headers)

    async def create(self):
        if not self.session.closed:
            await self.session.close()
        self.session = aiohttp.ClientSession(connector=self._connector)

    async def request(self, route, json=True, **params):
        async with self.session.get(self.base + route, params=params) as resp:
            if json:
                return await resp.json()
            return await resp.text()

    def __del__(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.session.close())


class RequestsHTTPClient:
    def __init__(self, base_url):
        self.base = base_url
        self.session = requests.Session()

    def request(self, route, json=True, **params):
        resp = self.session.get(self.base + route, params=params)
        if json:
            return resp.json()
        return resp.text

    def __del__(self):
        self.session.close()
