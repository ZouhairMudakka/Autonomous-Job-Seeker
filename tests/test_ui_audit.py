"""UI lifecycle regressions; mocks avoid real browser or account actions."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest

import main
from ui.cli import CLI
from utils.console_input import async_input


@pytest.fixture
def controller(tmp_path):
    return SimpleNamespace(
        settings={"system": {"data_dir": str(tmp_path)}, "telemetry": {"enabled": False}},
        logs_manager=SimpleNamespace(**{name: AsyncMock() for name in ("info", "error", "warning", "debug")}),
        telemetry=Mock(), start_session=AsyncMock(), end_session=AsyncMock(),
        pause_session=AsyncMock(), resume_session=AsyncMock(), run_linkedin_flow=AsyncMock(),
        tracker_agent=SimpleNamespace(get_activities=AsyncMock(return_value=pd.DataFrame())),
        linkedin_agent=SimpleNamespace(min_delay=0.1, max_delay=0.2),
        cv_parser=SimpleNamespace(parse_cv=AsyncMock(return_value={"raw_text": "Example CV"})),
    )


async def test_cli_awaits_commands_on_owning_loop_and_handles_eof(controller, monkeypatch):
    loop = asyncio.get_running_loop()
    async def pause():
        assert asyncio.get_running_loop() is loop
    controller.pause_session.side_effect = pause
    cli = CLI(controller)
    assert await cli.execute_line("pause") is False
    controller.pause_session.assert_awaited_once()
    await cli.execute_line("status")
    controller.tracker_agent.get_activities.assert_awaited_once()
    monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError))
    await cli.start()
    controller.end_session.assert_awaited_once()


async def test_cli_search_remains_controllable_and_stop_cancels(controller):
    started, cancelled = asyncio.Event(), asyncio.Event()
    async def search(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    controller.run_linkedin_flow.side_effect = search
    cli = CLI(controller)
    await cli.execute_line('search "Engineer" "Remote"')
    await asyncio.wait_for(started.wait(), 1)
    await cli.execute_line('search "Other" "Remote"')
    assert controller.run_linkedin_flow.await_count == 1
    await cli.execute_line("pause")
    await cli.execute_line("stop")
    assert cancelled.is_set()
    assert cli._search_task.done()


async def test_mode_menu_eof_does_not_spin(controller, monkeypatch):
    monkeypatch.setattr(main, "read_input", AsyncMock(side_effect=EOFError))
    await main.run_selected_mode(controller, controller.logs_manager)
    controller.start_session.assert_not_called()


async def test_automatic_mode_uses_configured_search(controller, monkeypatch):
    controller.settings.update(job_title="Engineer", location="Dubai")
    prompt = AsyncMock(side_effect=AssertionError("Unexpected prompt"))
    monkeypatch.setattr(main, "read_input", prompt)
    await main.run_automatic_mode(controller, controller.logs_manager)
    controller.run_linkedin_flow.assert_awaited_once_with("Engineer", "Dubai")


async def test_partial_browser_failure_cleans_driver_and_logs(controller, monkeypatch):
    logs = controller.logs_manager
    logs.initialize, logs.shutdown = AsyncMock(), AsyncMock()
    setup = SimpleNamespace(initialize=AsyncMock(side_effect=RuntimeError("launch failed")), cleanup=AsyncMock())
    monkeypatch.setattr(main, "load_settings", lambda: controller.settings)
    monkeypatch.setattr(main, "LogsManager", Mock(return_value=logs))
    monkeypatch.setattr(main, "BrowserSetup", Mock(return_value=setup))
    with pytest.raises(RuntimeError, match="launch failed"):
        await main.async_main()
    setup.cleanup.assert_awaited_once_with(None, None)
    logs.shutdown.assert_awaited_once()


async def test_pending_console_input_cancellation_does_not_wait_for_enter(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def blocking_input(prompt):
        entered.set()
        release.wait(5)
        return "later"
    monkeypatch.setattr("builtins.input", blocking_input)
    task = asyncio.create_task(async_input("prompt"))
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.2)
        assert any(thread.name == "console-input" and thread.daemon
                   for thread in threading.enumerate())
    finally:
        release.set()


@pytest.mark.parametrize("replace_selection", [False, True])
async def test_delayed_cv_parse_cannot_restore_removed_or_replaced_selection(controller, tmp_path, replace_selection):
    from ui.minimal_gui import MinimalGUI
    gui = MinimalGUI.__new__(MinimalGUI)
    gui.controller = controller
    gui._cv_generation = 0
    gui.shutdown_requested = False
    gui.cv_status_var = Mock()
    gui.cv_preview_text = Mock()
    gui.log_activity = Mock()
    first, second = tmp_path / "first.txt", tmp_path / "second.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    entered, finish = asyncio.Event(), asyncio.Event()
    async def parse(path):
        if path == first:
            entered.set()
            await finish.wait()
        return {"raw_text": path.stem}
    controller.cv_parser.parse_cv.side_effect = parse
    pending = asyncio.create_task(gui.parse_cv_content(first))
    await entered.wait()
    if replace_selection:
        await gui.parse_cv_content(second)
    else:
        gui.remove_cv_file()
    finish.set()
    await pending
    if replace_selection:
        assert controller.settings["parsed_cv_data"] == {"raw_text": "second"}
    else:
        assert "parsed_cv_data" not in controller.settings


@pytest.mark.gui
async def test_gui_initialization_search_cv_and_close_share_one_loop(controller, tmp_path):
    from ui.minimal_gui import MinimalGUI
    gui = MinimalGUI(controller)
    gui.window.withdraw()
    loop = asyncio.get_running_loop()
    assert gui.async_loop is loop
    gui.job_title_var.set("Engineer")
    gui.location_var.set("Dubai")
    gui.start_automation_command()
    await gui._automation_task
    controller.run_linkedin_flow.assert_awaited_once_with("Engineer", "Dubai")
    cv = tmp_path / "cv.txt"
    cv.write_text("Example CV", encoding="utf-8")
    await gui.parse_cv_content(cv)
    assert controller.settings["parsed_cv_data"]["raw_text"] == "Example CV"
    assert "Example CV" in gui.cv_preview_text.get("1.0", "end")
    gui.on_closing()
    await gui.run_app()
    assert loop.is_running()
    assert all(task.done() for task in gui._tasks)


@pytest.mark.gui
async def test_gui_stop_cancels_running_work_and_cleans_up(controller):
    from ui.minimal_gui import MinimalGUI
    gui = MinimalGUI(controller)
    gui.window.withdraw()
    started = asyncio.Event()
    cancelled = asyncio.Event()
    async def search(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    controller.run_linkedin_flow.side_effect = search
    gui.job_title_var.set("Engineer")
    gui.location_var.set("Dubai")
    gui.start_automation_command()
    await asyncio.wait_for(started.wait(), 1)
    await gui.stop_automation()
    assert cancelled.is_set()
    assert not gui.state["is_running"]
    gui.on_closing()
    await gui.run_app()
