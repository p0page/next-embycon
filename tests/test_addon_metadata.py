from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDON_XML = ROOT / "plugin.video.nextembycon" / "addon.xml"


def _addon_attribute(name: str) -> str:
    addon_xml = ADDON_XML.read_text(encoding="utf-8")
    addon_match = re.search(r"<addon\s+([^>]*)>", addon_xml, re.S)
    assert addon_match is not None, "addon.xml is missing the addon tag"
    match = re.search(r"(?:^|\s)%s=\"([^\"]+)\"" % name, addon_match.group(1))
    assert match is not None, "addon.xml is missing %s" % name
    return match.group(1)


class AddonMetadataTests(unittest.TestCase):
    def test_next_embycon_metadata_uses_independent_addon_id(self) -> None:
        self.assertEqual(_addon_attribute("id"), "plugin.video.nextembycon")
        self.assertEqual(_addon_attribute("name"), "Next EmbyCon")
        self.assertEqual(_addon_attribute("version"), "0.2.0")
