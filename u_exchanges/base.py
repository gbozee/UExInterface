import asyncio
import typing


async def loop_helper(callback):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, callback)
    return await future


class BaseExchange:
    def __init__(self, api_key: str, api_secret: str, **kwargs) -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    async def get_client(self) -> typing.Any:
        return await loop_helper(lambda: self.client)

    async def client_helper(self, function_name, *args, **kwargs):
        client = await self.get_client()
        return await loop_helper(
            lambda: getattr(client, function_name)(*args, **kwargs)
        )

