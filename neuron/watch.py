"""File system watcher with live WebSocket reload for HTML visualization."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable


def watch(
    root: str | Path,
    on_change: Callable[[list[str]], None],
    debounce_ms: int = 500,
    ignore_patterns: list[str] | None = None,
):
    """Watch a directory for file changes and trigger rebuild.

    Args:
        root: Directory to watch.
        on_change: Callback with list of changed file paths.
        debounce_ms: Debounce interval in milliseconds.
        ignore_patterns: File patterns to ignore.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        raise ImportError("Install watchdog: pip install neuron-graph[watch]")

    root = Path(root).resolve()
    ignore = set(ignore_patterns or [])
    ignore.update({".neuron-out", "__pycache__", ".git", "node_modules"})

    pending: list[str] = []
    lock = threading.Lock()
    last_trigger = 0.0

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            nonlocal last_trigger
            if event.is_directory:
                return

            path = event.src_path
            rel = str(Path(path).relative_to(root))

            # Skip ignored paths
            for pattern in ignore:
                if pattern in rel:
                    return

            with lock:
                pending.append(rel)

    handler = Handler()
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    observer.start()

    print(f"Watching {root} for changes... (Ctrl+C to stop)")

    try:
        while True:
            time.sleep(debounce_ms / 1000)
            with lock:
                if pending:
                    changed = list(set(pending))
                    pending.clear()
                    now = time.time()
                    if now - last_trigger > debounce_ms / 1000:
                        last_trigger = now
                        print(f"Changed: {', '.join(changed[:5])}{'...' if len(changed) > 5 else ''}")
                        try:
                            on_change(changed)
                        except Exception as e:
                            print(f"Rebuild error: {e}")
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def start_live_server(
    html_path: str | Path,
    port: int = 8765,
) -> threading.Thread:
    """Start a WebSocket server that notifies connected browsers to reload.

    Returns the server thread (daemon).
    """
    try:
        import asyncio
        import websockets
    except ImportError:
        raise ImportError("Install websockets: pip install neuron-graph[watch]")

    clients: set = set()

    async def handler(websocket):
        clients.add(websocket)
        try:
            async for _ in websocket:
                pass
        finally:
            clients.discard(websocket)

    async def notify_reload():
        if clients:
            msg = json.dumps({"type": "reload"})
            await asyncio.gather(*(c.send(msg) for c in clients), return_exceptions=True)

    loop = None

    async def serve():
        nonlocal loop
        loop = asyncio.get_event_loop()
        async with websockets.serve(handler, "localhost", port):
            await asyncio.Future()  # Run forever

    def _run():
        asyncio.run(serve())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Return a notify function attached to the thread
    def trigger_reload():
        if loop:
            asyncio.run_coroutine_threadsafe(notify_reload(), loop)

    thread.trigger_reload = trigger_reload  # type: ignore
    return thread
