"""
Basic Tkinter functionality test.
Verifies that Tkinter windows can be created and displayed properly.
"""

import tkinter as tk
import threading
import pytest

def test_tkinter_basic_window():
    """Test basic Tkinter window creation and functionality."""
    print("[TEST] Starting Tkinter test...")
    print("[TEST] Current thread:", threading.current_thread().name)
    print("[TEST] Is main thread:", threading.current_thread() is threading.main_thread())

    root = tk.Tk()
    root.title("Test Window")
    root.geometry("300x200")

    print("[TEST] Window created")
    print("[TEST] Screen dimensions:", root.winfo_screenwidth(), "x", root.winfo_screenheight())

    # Calculate center position
    window_width = 300
    window_height = 200
    x_position = (root.winfo_screenwidth() - window_width) // 2
    y_position = (root.winfo_screenheight() - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")

    print(f"[TEST] Window positioned at: {x_position}, {y_position}")

    # Verify window properties
    assert root.winfo_exists(), "Window should exist"
    assert root.title() == "Test Window", "Window title should match"
    assert root.winfo_width() > 0, "Window width should be positive"
    assert root.winfo_height() > 0, "Window height should be positive"

    # Clean up
    root.destroy()
    print("[TEST] Window destroyed")
    print("[TEST] Test completed successfully") 