"""Tests for portable-mode path overrides in config/settings.py."""

import importlib

import config.settings as settings


def _reload(monkeypatch, reports=None, logs=None):
    for name in ("EIMS_REPORTS_DIR", "EIMS_LOGS_DIR"):
        monkeypatch.delenv(name, raising=False)
    if reports is not None:
        monkeypatch.setenv("EIMS_REPORTS_DIR", reports)
    if logs is not None:
        monkeypatch.setenv("EIMS_LOGS_DIR", logs)
    return importlib.reload(settings)


def test_default_paths_are_package_relative(monkeypatch):
    mod = _reload(monkeypatch)
    assert mod.REPORTS_DIR == mod.BASE_DIR / "reports"
    assert mod.LOGS_DIR == mod.BASE_DIR / "logs"


def test_env_overrides_redirect_and_create(monkeypatch, tmp_path):
    reports = tmp_path / "custom_reports"
    logs = tmp_path / "custom_logs"
    mod = _reload(monkeypatch, reports=str(reports), logs=str(logs))
    assert mod.REPORTS_DIR == reports
    assert mod.LOGS_DIR == logs
    assert reports.is_dir()
    assert logs.is_dir()


def test_blank_env_falls_back_to_default(monkeypatch):
    mod = _reload(monkeypatch, reports="   ", logs="")
    assert mod.REPORTS_DIR == mod.BASE_DIR / "reports"
    assert mod.LOGS_DIR == mod.BASE_DIR / "logs"


def teardown_module(module):
    importlib.reload(settings)
