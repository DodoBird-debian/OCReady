import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("module", ["scripts.release_assets", "scripts.release_variants"])
def test_publishers_load_without_application_site_packages(module):
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    result = subprocess.run([sys.executable, "-S", "-m", module, "--help"],
                            cwd=Path(__file__).resolve().parents[1], env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "--artifacts" in result.stdout
