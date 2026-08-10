"""
Disk Sanitization Assistant — Entry point.
"""
import os
import sys
import logging
import datetime
from pathlib import Path

# Determine actual root directory (exe location if frozen by PyInstaller, script dir if raw python)
if getattr(sys, "frozen", False):
    app_dir = Path(sys.executable).parent.resolve()
else:
    app_dir = Path(__file__).parent.resolve()

os.chdir(app_dir)
sys.path.insert(0, str(app_dir))

from app.config import AppConfig
from app.viewmodels.app_viewmodel import AppViewModel
from app.views.main_window import MainWindow


def _setup_logging(log_folder: Path) -> None:
    log_folder.mkdir(parents=True, exist_ok=True)
    log_file = log_folder / f"app_{datetime.date.today().strftime('%Y-%m-%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    config = AppConfig.load()
    _setup_logging(config.resolved_log_folder)

    logger = logging.getLogger(__name__)
    logger.info("Disk Sanitization Assistant starting up")

    viewmodel = AppViewModel(config)
    window = MainWindow(viewmodel)
    window.run()

    logger.info("Application shut down cleanly")


if __name__ == "__main__":
    main()
