"""
Event Loop Manager Implementation
Handles the creation and management of asyncio event loops.
"""

import asyncio
import threading
from typing import Optional, Any, Coroutine
from concurrent.futures import Future

class AsyncEventLoopManager:
    def __init__(self):
        """Initialize the AsyncEventLoopManager."""
        self.async_loop: Optional[asyncio.AbstractEventLoop] = None
        self.async_thread: Optional[threading.Thread] = None
        self._shutdown_requested = False

    def start(self):
        """Start the async event loop in a background thread."""
        if self.async_thread and self.async_thread.is_alive():
            return

        self.async_loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.async_thread.start()

    def stop(self):
        """Stop the event loop and clean up resources."""
        self._shutdown_requested = True
        if self.async_loop and not self.async_loop.is_closed():
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            if self.async_thread and self.async_thread.is_alive():
                self.async_thread.join(timeout=5.0)
            self.async_loop.close()

    def _run_event_loop(self):
        """Run the event loop in the background thread."""
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_forever()

    def run_coroutine(self, coro: Coroutine) -> Future:
        """Run a coroutine in the background event loop."""
        if not self.async_loop or self.async_loop.is_closed():
            raise RuntimeError("Event loop is not running")
        return asyncio.run_coroutine_threadsafe(coro, self.async_loop)

    def call_soon(self, callback, *args):
        """Schedule a callback to run in the event loop thread."""
        if not self.async_loop or self.async_loop.is_closed():
            raise RuntimeError("Event loop is not running")
        self.async_loop.call_soon_threadsafe(callback, *args)

    @property
    def is_running(self) -> bool:
        """Check if the event loop is running."""
        return (
            self.async_loop is not None 
            and not self.async_loop.is_closed() 
            and self.async_thread is not None 
            and self.async_thread.is_alive()
        ) 