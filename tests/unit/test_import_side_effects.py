import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(code: str, cwd: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.pop("HRC_ENV", None)
    env.pop("ENV", None)
    env["HRC_AUTO_CONFIG"] = "true"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_package_import_has_no_environment_side_effects(tmp_path: Path) -> None:
    _run(
        "import sys\n"
        "import hierachain\n"
        "assert 'hierachain.api.server' not in sys.modules\n"
        "from hierachain.config import settings\n"
        "assert settings._instance is None\n",
        tmp_path,
    )
    assert not (tmp_path / ".env.HRC.example").exists()
    assert not (tmp_path / ".env").exists()


def test_server_app_is_created_lazily(tmp_path: Path) -> None:
    _run(
        "import hierachain.api.server as server\n"
        "assert server._app is None\n"
        "app = server.app\n"
        "assert app is not None\n"
        "assert server._app is app\n",
        tmp_path,
    )


def test_settings_instance_is_resolved_on_first_access(tmp_path: Path) -> None:
    _run(
        "from hierachain.config import settings\n"
        "assert settings._instance is None\n"
        "_ = settings.env\n"
        "assert settings._instance is not None\n",
        tmp_path,
    )
