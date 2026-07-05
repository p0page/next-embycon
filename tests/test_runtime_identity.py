from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin.video.nextembycon"))
sys.path.insert(0, str(ROOT))

MISSING_MODULE = object()
MODULES_TO_RESTORE = (
    "xbmc",
    "xbmcaddon",
    "xbmcgui",
    "xbmcvfs",
    "xbmcplugin",
    "resources.lib.skin_cloner",
    "resources.lib.clientinfo",
    "resources.lib.kodi_utils",
    "resources.lib.simple_logging",
    "resources.lib.jsonrpc",
    "scripts.parse_timing_log",
)


class FakeAddon:
    def getSetting(self, key: str) -> str:
        return ""

    def getAddonInfo(self, key: str) -> str:
        return {"version": "test-version"}.get(key, "")


class FakeHomeWindow:
    props: dict[str, str] = {}

    def getProperty(self, key: str) -> str:
        return self.props.get(key, "")

    def setProperty(self, key: str, value: str) -> None:
        self.props[key] = value

    def clearProperty(self, key: str) -> None:
        self.props.pop(key, None)


class FakeVfsFile:
    def __init__(self, path: str, mode: str = "r") -> None:
        self.path = Path(path)
        self.mode = mode
        if "w" in mode or not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        if "r" in mode and not self.path.exists():
            self.path.write_text("", encoding="utf-8")
        self.handle = self.path.open(mode, encoding="utf-8")

    def read(self) -> str:
        return self.handle.read()

    def write(self, value: str) -> None:
        self.handle.write(value)

    def close(self) -> None:
        self.handle.close()


class FakeProgressDialog:
    def create(self, *args, **kwargs) -> None:
        pass

    def update(self, *args, **kwargs) -> None:
        pass

    def close(self) -> None:
        pass


class RuntimeIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_modules = {
            module_name: sys.modules.get(module_name, MISSING_MODULE)
            for module_name in MODULES_TO_RESTORE
        }
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.xbmc_root = self.root / "xbmc"
        self.temp = self.root / "temp"
        self.guid_paths: list[str] = []
        FakeHomeWindow.props = {}
        self.jsonrpc_calls: list[dict[str, object]] = []
        self._install_kodi_stubs()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        for module_name, module in self.saved_modules.items():
            if module is MISSING_MODULE:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = module

    def _install_kodi_stubs(self) -> None:
        xbmc = types.ModuleType("xbmc")
        xbmc.LOGINFO = 1
        xbmc.LOGERROR = 4
        xbmc.log = lambda *args, **kwargs: None
        xbmc.executebuiltin = lambda *args, **kwargs: None
        xbmc.executeJSONRPC = lambda *args, **kwargs: '{"result": {}}'
        xbmc.getInfoLabel = lambda label: "21.0" if label == "System.BuildVersion" else ""
        sys.modules["xbmc"] = xbmc

        xbmcaddon = types.ModuleType("xbmcaddon")
        xbmcaddon.Addon = lambda: FakeAddon()
        sys.modules["xbmcaddon"] = xbmcaddon

        xbmcgui = types.ModuleType("xbmcgui")
        xbmcgui.Window = lambda window_id: FakeHomeWindow()
        xbmcgui.Dialog = lambda: types.SimpleNamespace(ok=lambda *a, **k: None)
        xbmcgui.DialogProgress = FakeProgressDialog
        xbmcgui.ListItem = lambda *a, **k: types.SimpleNamespace(setArt=lambda art: None)
        sys.modules["xbmcgui"] = xbmcgui

        xbmcplugin = types.ModuleType("xbmcplugin")
        xbmcplugin.addDirectoryItem = lambda *args, **kwargs: None
        sys.modules["xbmcplugin"] = xbmcplugin

        xbmcvfs = types.ModuleType("xbmcvfs")

        def translate_path(path: str) -> str:
            if path == "special://home":
                return str(self.home)
            if path == "special://xbmc":
                return str(self.xbmc_root)
            if path.startswith("special://temp/"):
                translated = str(self.temp / path.rsplit("/", 1)[1])
                self.guid_paths.append(translated)
                return translated
            return path

        def listdir(path: str) -> tuple[list[str], list[str]]:
            directories: list[str] = []
            files: list[str] = []
            for child in Path(path).iterdir():
                if child.is_dir():
                    directories.append(child.name)
                else:
                    files.append(child.name)
            return directories, files

        def copy(source: str, destination: str) -> bool:
            src = Path(source)
            dest = Path(destination)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                shutil.copy2(src, dest)
            return True

        xbmcvfs.translatePath = translate_path
        xbmcvfs.exists = lambda path: Path(path).exists()
        xbmcvfs.listdir = listdir
        xbmcvfs.copy = copy
        xbmcvfs.File = FakeVfsFile
        sys.modules["xbmcvfs"] = xbmcvfs

    def _reload_module(self, module_name: str):
        if module_name == "resources.lib.clientinfo":
            sys.modules.pop("resources.lib.kodi_utils", None)
        sys.modules.pop(module_name, None)
        return importlib.import_module(module_name)

    def test_check_skin_installed_uses_independent_skin_addon_id(self) -> None:
        skin_cloner = self._reload_module("resources.lib.skin_cloner")

        class FakeJsonRpc:
            def __init__(self, method: str) -> None:
                self.method = method

            def execute(inner_self, params: dict[str, object]) -> dict[str, object]:
                self.jsonrpc_calls.append({"method": inner_self.method, "params": params})
                return {"result": {}}

        skin_cloner.JsonRpc = FakeJsonRpc
        skin_cloner.clone_default_skin = lambda: None

        skin_cloner.check_skin_installed()

        self.assertEqual(
            self.jsonrpc_calls[0]["params"]["addonid"],
            "skin.estuary_nextembycon",
        )

    def test_clone_skin_creates_independent_skin_addon(self) -> None:
        skin_cloner = self._reload_module("resources.lib.skin_cloner")

        kodi_skin_source = self.xbmc_root / "addons" / "skin.estuary"
        kodi_skin_source.mkdir(parents=True)
        (kodi_skin_source / "addon.xml").write_text(
            '<addon id="skin.estuary" name="Estuary" version="1.0" />',
            encoding="utf-8",
        )
        (kodi_skin_source / "xml").mkdir()
        (kodi_skin_source / "xml" / "Home.xml").write_text(
            "<window />",
            encoding="utf-8",
        )

        custom_skin_source = (
            self.home
            / "addons"
            / "plugin.video.nextembycon"
            / "resources"
            / "skins"
            / "skin.estuary"
            / "21"
            / "xml"
        )
        custom_skin_source.mkdir(parents=True)
        (custom_skin_source / "Home.xml").write_text(
            "<window>next</window>",
            encoding="utf-8",
        )

        class FakeJsonRpc:
            def __init__(self, method: str) -> None:
                self.method = method

            def execute(inner_self, params: dict[str, object]) -> dict[str, object]:
                self.jsonrpc_calls.append({"method": inner_self.method, "params": params})
                return {"result": {}}

        skin_cloner.JsonRpc = FakeJsonRpc

        self.assertTrue(skin_cloner.clone_skin())

        addon_xml = (
            self.home
            / "addons"
            / "skin.estuary_nextembycon"
            / "addon.xml"
        ).read_text(encoding="utf-8")
        self.assertIn('id="skin.estuary_nextembycon"', addon_xml)
        self.assertIn('name="Estuary Next EmbyCon"', addon_xml)
        self.assertEqual(
            self.jsonrpc_calls[-1]["params"]["addonid"],
            "skin.estuary_nextembycon",
        )

    def test_client_device_id_uses_next_embycon_device_guid_file(self) -> None:
        clientinfo = self._reload_module("resources.lib.clientinfo")

        device_id = clientinfo.ClientInformation().get_device_id()

        self.assertTrue(device_id)
        self.assertTrue(self.guid_paths)
        self.assertTrue(self.guid_paths[0].endswith("nextembycon_device_guid"))

    def test_client_information_returns_next_embycon_client_name(self) -> None:
        clientinfo = self._reload_module("resources.lib.clientinfo")

        self.assertEqual(
            clientinfo.ClientInformation().get_client(),
            "Kodi Next EmbyCon",
        )

    def test_timing_parser_accepts_next_and_legacy_prefixes(self) -> None:
        parse_timing_log = self._reload_module("scripts.parse_timing_log")
        template = (
            "2026-07-05 12:00:00.000 T:123 info <general>: "
            "{prefix}load_home|1.5|2.5|extra"
        )

        self.assertEqual(
            parse_timing_log.parse_timing_line(
                template.format(
                    prefix="Next EmbyCon.resources.lib.tracking|INFO|timing_data|"
                )
            )["function"],
            "load_home",
        )
        self.assertEqual(
            parse_timing_log.parse_timing_line(
                template.format(
                    prefix="EmbyCon.resources.lib.tracking|INFO|timing_data|"
                )
            )["function"],
            "load_home",
        )


if __name__ == "__main__":
    unittest.main()
