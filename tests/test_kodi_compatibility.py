from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "plugin.video.embycon"
ADDON_XML = ADDON_DIR / "addon.xml"
PACKAGE_SCRIPT = ROOT / "scripts" / "package_addon.py"
VALID_KODI_ADDON_IDENTIFIER_CHARACTERS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    ".-_@!$"
)


def load_package_addon_module():
    spec = importlib.util.spec_from_file_location("package_addon", PACKAGE_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_addon_xml(path: Path = ADDON_XML) -> ET.Element:
    return ET.fromstring(path.read_bytes())


class KodiCompatibilityTests(unittest.TestCase):
    def test_addon_xml_matches_kodi_identity_and_entrypoint_requirements(self) -> None:
        root = parse_addon_xml()
        addon_id = root.attrib["id"]

        self.assertEqual(root.tag, "addon")
        self.assertEqual(addon_id, ADDON_DIR.name)
        self.assertFalse(set(addon_id) - set(VALID_KODI_ADDON_IDENTIFIER_CHARACTERS))
        self.assertTrue(root.attrib.get("version"))
        self.assertTrue(root.attrib.get("provider-name"))

        plugin_extension = root.find("./extension[@point='xbmc.python.pluginsource']")
        self.assertIsNotNone(plugin_extension)
        assert plugin_extension is not None
        self.assertEqual(plugin_extension.attrib["library"], "default.py")
        self.assertTrue((ADDON_DIR / plugin_extension.attrib["library"]).is_file())

        service_extension = root.find("./extension[@point='xbmc.service']")
        self.assertIsNotNone(service_extension)
        assert service_extension is not None
        self.assertEqual(service_extension.attrib["library"], "service.py")
        self.assertTrue((ADDON_DIR / service_extension.attrib["library"]).is_file())

        context_items = root.findall("./extension[@point='kodi.context.item']//item")
        self.assertGreater(len(context_items), 0)
        for item in context_items:
            library = item.attrib.get("library")
            self.assertTrue(library, "context menu item is missing library")
            assert library is not None
            self.assertTrue((ADDON_DIR / library).is_file(), library)

    def test_addon_xml_metadata_does_not_contain_replacement_characters(self) -> None:
        root = parse_addon_xml()
        for element in root.iter():
            text = element.text or ""
            self.assertNotIn("\ufffd", text, element.tag)

    def test_packaged_zip_matches_kodi_install_archive_shape(self) -> None:
        package_addon = load_package_addon_module()

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = package_addon.build_zip(ADDON_DIR, Path(temp_dir))

            with ZipFile(zip_path) as zip_file:
                infos = zip_file.infolist()
                names = zip_file.namelist()
                roots = {name.split("/", 1)[0] for name in names if name}

                self.assertEqual(roots, {ADDON_DIR.name})
                self.assertFalse(any(info.is_dir() for info in infos))
                self.assertIn(f"{ADDON_DIR.name}/addon.xml", names)
                self.assertFalse(any(name.startswith("../") for name in names))
                self.assertFalse(any("__pycache__" in Path(name).parts for name in names))

                addon_xml = ET.fromstring(
                    zip_file.read(f"{ADDON_DIR.name}/addon.xml")
                )

        self.assertEqual(addon_xml.attrib["id"], ADDON_DIR.name)
        self.assertTrue(
            re.match(
                rf"^{re.escape(ADDON_DIR.name)}-\d+\.\d+\.\d+\.zip$",
                zip_path.name,
            ),
            zip_path.name,
        )
