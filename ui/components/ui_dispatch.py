"""Queue component updates without calling Tk from worker threads."""

import logging
from queue import Empty, SimpleQueue
import tkinter as tk


class UIUpdateDispatcher:
    def _init_ui_dispatcher(self):
        self._ui_updates = SimpleQueue()
        self._ui_closed = False
        self._ui_poll_id = self.after(50, self._drain_ui_updates)

    def schedule_ui_update(self, update_func):
        if not self._ui_closed:
            self._ui_updates.put(update_func)

    def _drain_ui_updates(self):
        if self._ui_closed:
            return
        for _ in range(100):
            try:
                callback = self._ui_updates.get_nowait()
            except Empty:
                break
            try:
                callback()
            except Exception:
                logging.exception('Component display update failed')
        if not self._ui_closed:
            self._ui_poll_id = self.after(50, self._drain_ui_updates)

    def destroy(self):
        self._ui_closed = True
        for name in ('_ui_poll_id', '_auto_refresh_id'):
            callback_id = getattr(self, name, None)
            if callback_id is not None:
                try:
                    self.after_cancel(callback_id)
                except tk.TclError:
                    pass
        super().destroy()
