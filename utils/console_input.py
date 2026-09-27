"""Console input that cannot hold asyncio's executor open during shutdown."""
import asyncio
import threading


async def async_input(prompt=""):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def deliver(value, error):
        if not future.done():
            if error is None:
                future.set_result(value)
            else:
                future.set_exception(error)

    def read():
        try:
            value, error = input(prompt), None
        except Exception as exc:
            value, error = None, exc
        try:
            loop.call_soon_threadsafe(deliver, value, error)
        except RuntimeError:
            pass  # The application closed while input was pending.

    threading.Thread(target=read, name="console-input", daemon=True).start()
    return await future
