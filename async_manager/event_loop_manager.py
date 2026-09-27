"""Own an asyncio event loop and clean up its work in its background thread."""

import asyncio
import threading
from concurrent.futures import Future
from typing import Coroutine, Optional


class AsyncEventLoopManager:
    def __init__(self):
        self.async_loop: Optional[asyncio.AbstractEventLoop] = None
        self.async_thread: Optional[threading.Thread] = None
        self._shutdown_requested = False
        self._ready = threading.Event()

    def start(self):
        if self.async_thread and self.async_thread.is_alive():
            if self._shutdown_requested:
                raise RuntimeError("Event loop is shutting down")
            return
        self._shutdown_requested = False
        self._ready.clear()
        self.async_loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.async_thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("Event loop failed to start")

    def stop(self):
        self._shutdown_requested = True
        loop, thread = self.async_loop, self.async_thread
        if loop and not loop.is_closed():
            loop.call_soon_threadsafe(loop.stop)
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("Event loop did not shut down within five seconds")

    def _run_event_loop(self):
        loop = self.async_loop
        asyncio.set_event_loop(loop)
        loop.call_soon(self._ready.set)
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()

    def run_coroutine(self, coro: Coroutine) -> Future:
        if not self.is_running:
            coro.close()
            raise RuntimeError("Event loop is not running")
        try:
            return asyncio.run_coroutine_threadsafe(coro, self.async_loop)
        except RuntimeError:
            coro.close()
            raise

    def call_soon(self, callback, *args):
        if not self.is_running:
            raise RuntimeError("Event loop is not running")
        self.async_loop.call_soon_threadsafe(callback, *args)

    @property
    def is_running(self) -> bool:
        return bool(
            not self._shutdown_requested
            and self.async_loop is not None
            and self.async_loop.is_running()
            and self.async_thread is not None
            and self.async_thread.is_alive()
        )
