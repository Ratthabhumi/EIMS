import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent, FileDeletedEvent
from watchdog.observers import Observer

from app.constants import SUPPORTED_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)


class _ImageHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[Path], None]) -> None:
        super().__init__()
        self._callback = callback
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def _norm(self, path: Path) -> str:
        try:
            return os.path.normcase(os.path.abspath(str(path)))
        except Exception:
            return str(path).lower()

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory:
            self._dispatch(Path(event.src_path).resolve())

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            self._dispatch(Path(event.dest_path).resolve())

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if not event.is_directory:
            self.forget(Path(event.src_path).resolve())

    def forget(self, path: Path) -> None:
        with self._lock:
            self._seen.discard(self._norm(path))

    def _dispatch(self, path: Path) -> None:
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            return
        norm = self._norm(path)
        with self._lock:
            if norm in self._seen:
                return
            self._seen.add(norm)
        logger.info("New image: %s", path.name)
        self._callback(path)


class WatchService:
    def __init__(self, watch_folder: Path, callback: Callable[[Path], None]) -> None:
        self._folder = watch_folder.resolve()
        self._handler = _ImageHandler(callback)
        self._observer: Optional[Observer] = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def forget(self, path: Path) -> None:
        """Forget an image path so it can be re-detected if moved back to Sticker/."""
        self._handler.forget(path)

    def start(self) -> None:
        self._folder.mkdir(parents=True, exist_ok=True)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self._folder), recursive=False)
        self._observer.start()

        self._stop.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="FolderPoller"
        )
        self._poll_thread.start()
        logger.info("Watching folder: %s", self._folder)

    def stop(self) -> None:
        self._stop.set()
        if self._observer:
            self._observer.stop()
            self._observer.join()
        if self._poll_thread:
            self._poll_thread.join(timeout=2)

    def scan_existing(self) -> list[Path]:
        if not self._folder.exists():
            return []
        return [
            p.resolve()
            for p in self._folder.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]

    def _poll_loop(self) -> None:
        """Periodic fallback scan every 2 seconds in case watchdog misses OS file events."""
        while not self._stop.is_set():
            try:
                for img in self.scan_existing():
                    self._handler._dispatch(img)
            except Exception as exc:
                logger.debug("Polling loop error: %s", exc)
            self._stop.wait(timeout=2.0)
