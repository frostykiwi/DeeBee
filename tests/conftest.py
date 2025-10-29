import sys
import types
from pathlib import Path

# Ensure the project root is importable when running pytest without installation.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if "requests" not in sys.modules:
    stub = types.ModuleType("requests")

    class _Session:  # pragma: no cover - test helper
        def get(self, *args, **kwargs):  # noqa: D401 - simple stub
            raise RuntimeError("Stub Session cannot perform HTTP requests.")

    stub.Session = _Session
    sys.modules["requests"] = stub


if "rich" not in sys.modules:
    rich_stub = types.ModuleType("rich")

    console_module = types.ModuleType("rich.console")

    class _Console:  # pragma: no cover - test helper
        def print(self, *args, **kwargs):
            pass

        def input(self, prompt: str = "") -> str:
            raise RuntimeError("Console input is not supported in tests.")

    console_module.Console = _Console
    sys.modules["rich.console"] = console_module

    table_module = types.ModuleType("rich.table")

    class _Table:  # pragma: no cover - test helper
        def __init__(self, *args, **kwargs):
            pass

        def add_column(self, *args, **kwargs):
            pass

        def add_row(self, *args, **kwargs):
            pass

    table_module.Table = _Table
    sys.modules["rich.table"] = table_module

    rich_stub.console = console_module
    rich_stub.table = table_module
    sys.modules["rich"] = rich_stub
