from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "package_addon.py"
ADDON_DIR = ROOT / "plugin.video.nextembycon"


def load_package_addon_module():
    spec = importlib.util.spec_from_file_location("package_addon", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageAddonTests(unittest.TestCase):
    def test_build_zip_writes_kodi_compatible_file_only_archive(self) -> None:
        package_addon = load_package_addon_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = package_addon.build_zip(ADDON_DIR, Path(temp_dir))

            with ZipFile(zip_path) as zip_file:
                infos = zip_file.infolist()
                names = zip_file.namelist()

            self.assertTrue(zip_path.name.startswith("plugin.video.nextembycon-"))
            self.assertTrue(
                all(name.startswith("plugin.video.nextembycon/") for name in names)
            )
            self.assertFalse(any(info.is_dir() for info in infos))
            self.assertIn("plugin.video.nextembycon/addon.xml", names)
