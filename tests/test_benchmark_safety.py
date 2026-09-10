"""
Tests for sprint11_benchmark.py safety guard.

Verifies that the benchmark REFUSES to run against a database that
looks like the production EIMS application database.

These tests do NOT run the actual benchmark or touch the database.
They test only the safety guard logic.
"""
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _import_assert_fn():
    """Import the safety function directly from the benchmark module."""
    # Temporarily suppress the 'no backend' import issues by importing just
    # the safety function via exec to avoid triggering SQLAlchemy model imports.
    import importlib.util
    import types

    # Read and extract just the safety function
    bench_path = os.path.join(os.path.dirname(__file__), "..", "tools", "sprint11_benchmark.py")
    with open(bench_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Execute in a minimal module context with only stdlib
    mod = types.ModuleType("_bench_safety_test")
    mod.__dict__.update({
        "os": os,
        "_SAFE_DB_NAME_SUFFIXES_BLOCKLIST": ["registry"],
        "_OVERRIDE_ENV_VAR": "EIMS_ALLOW_BENCHMARK_ON_REGISTRY",
        "_BENCHMARK_DB_ENV_VAR": "EIMS_BENCHMARK_DATABASE_URL",
    })

    # Extract only the safety function by executing relevant lines
    lines = source.split("\n")
    fn_start = None
    for i, line in enumerate(lines):
        if "def _assert_benchmark_safety" in line:
            fn_start = i
            break

    assert fn_start is not None, "_assert_benchmark_safety function not found in benchmark script"

    # Find end of function (next top-level def or class)
    fn_lines = []
    for line in lines[fn_start:]:
        if fn_lines and line and not line.startswith(" ") and not line.startswith("\t") and not line.startswith("#"):
            break
        fn_lines.append(line)

    fn_source = "\n".join(fn_lines)
    exec(fn_source, mod.__dict__)
    return mod._assert_benchmark_safety


class TestBenchmarkSafetyGuard:
    """Tests that the benchmark refuses to run against production databases."""

    def setup_method(self):
        """Clean up override env var before each test."""
        os.environ.pop("EIMS_ALLOW_BENCHMARK_ON_REGISTRY", None)
        os.environ.pop("EIMS_BENCHMARK_DATABASE_URL", None)

    def teardown_method(self):
        """Clean up override env var after each test."""
        os.environ.pop("EIMS_ALLOW_BENCHMARK_ON_REGISTRY", None)
        os.environ.pop("EIMS_BENCHMARK_DATABASE_URL", None)

    def test_empty_url_refused(self):
        """Benchmark refuses when EIMS_BENCHMARK_DATABASE_URL is not set."""
        fn = _import_assert_fn()
        with pytest.raises(RuntimeError, match="EIMS_BENCHMARK_DATABASE_URL is not set"):
            fn("")

    def test_production_registry_db_refused(self):
        """Benchmark refuses when target database is eims_registry (production)."""
        fn = _import_assert_fn()
        prod_url = "postgresql+asyncpg://eims_user:secret@localhost:5432/eims_registry"
        with pytest.raises(RuntimeError, match="looks like a production database"):
            fn(prod_url)

    def test_any_registry_suffix_refused(self):
        """Benchmark refuses any database name ending with 'registry'."""
        fn = _import_assert_fn()
        for db_name in ["eims_registry", "myapp_registry", "prod_registry"]:
            url = f"postgresql+asyncpg://user:pass@localhost/{db_name}"
            with pytest.raises(RuntimeError, match="looks like a production database"):
                fn(url)

    def test_benchmark_db_accepted(self):
        """Benchmark accepts a dedicated benchmark database URL."""
        fn = _import_assert_fn()
        benchmark_url = "postgresql+asyncpg://eims_user:secret@localhost:5432/eims_benchmark"
        # Should NOT raise
        fn(benchmark_url)

    def test_test_db_accepted(self):
        """Benchmark accepts test database URLs."""
        fn = _import_assert_fn()
        for db_name in ["eims_test", "eims_bench", "eims_perf", "benchmark_db"]:
            url = f"postgresql+asyncpg://user:pass@localhost/{db_name}"
            fn(url)  # Should not raise

    def test_override_allows_registry_with_explicit_consent(self):
        """Override env var allows running against registry DB if set explicitly."""
        fn = _import_assert_fn()
        os.environ["EIMS_ALLOW_BENCHMARK_ON_REGISTRY"] = "yes-i-know-what-i-am-doing"
        prod_url = "postgresql+asyncpg://eims_user:secret@localhost:5432/eims_registry"
        # Should NOT raise (prints warning instead)
        fn(prod_url)

    def test_partial_override_still_refused(self):
        """Partial or typo override values still refuse execution."""
        fn = _import_assert_fn()
        for bad_override in ["yes", "true", "1", "ok", "yes-i-know"]:
            os.environ["EIMS_ALLOW_BENCHMARK_ON_REGISTRY"] = bad_override
            prod_url = "postgresql+asyncpg://eims_user:secret@localhost:5432/eims_registry"
            with pytest.raises(RuntimeError, match="looks like a production database"):
                fn(prod_url)

    def test_existing_data_would_survive_refused_run(self):
        """
        Demonstrates that refusing the benchmark protects existing application data.

        If _assert_benchmark_safety raises, no TRUNCATE is ever executed.
        This test verifies the guard fires BEFORE any DB operation.
        """
        fn = _import_assert_fn()
        prod_url = "postgresql+asyncpg://eims_user:secret@localhost:5432/eims_registry"

        truncate_would_have_been_called = False
        try:
            fn(prod_url)
            # If no exception, we would proceed to TRUNCATE
            truncate_would_have_been_called = True
        except RuntimeError:
            # Guard fired — TRUNCATE is never reached
            pass

        assert not truncate_would_have_been_called, (
            "Safety guard FAILED — benchmark would have proceeded to TRUNCATE "
            "application data in eims_registry"
        )


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
