# Next EmbyCon Addon Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the fork from a renamed EmbyCon package into an independent Kodi addon identity that can coexist with upstream EmbyCon.

**Architecture:** The addon identity is currently hard-coded as `plugin.video.embycon` in metadata, settings, plugin URLs, skin XML, helper scripts, tests, and home-window property names. The implementation migrates these references to `plugin.video.nextembycon`, renames the addon folder and zip root, and resets the fork version to `0.1.0` while keeping the Python package layout under `resources.lib` unchanged.

**Tech Stack:** Kodi Python addon metadata, PowerShell packaging, Python `unittest`, repository-local shell checks using `rg`, `compileall`, and `scripts/check_strings.py`.

---

### Task 1: Add Identity Regression Tests

**Files:**
- Modify: `C:\Users\yqzzx\Projects\next-embycon\tests\test_addon_metadata.py`

- [ ] **Step 1: Write the failing addon identity test**

Replace the existing metadata test class with checks for the complete fork identity:

```python
class AddonMetadataTests(unittest.TestCase):
    def test_next_embycon_metadata_uses_independent_addon_id(self) -> None:
        self.assertEqual(_addon_attribute("id"), "plugin.video.nextembycon")
        self.assertEqual(_addon_attribute("name"), "Next EmbyCon")
        self.assertEqual(_addon_attribute("version"), "0.1.0")
```

- [ ] **Step 2: Run the metadata test and verify it fails**

Run:

```powershell
python -m unittest tests.test_addon_metadata
```

Expected: failure showing current id is `plugin.video.embycon` or current version is `1.12.11`.

- [ ] **Step 3: Keep this test red until Task 2 updates the addon folder**

Do not loosen the assertion to accept both ids. The purpose is to force a true independent addon identity.

### Task 2: Rename Addon Folder And Core Metadata

**Files:**
- Move: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.embycon` to `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\addon.xml`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\settings.xml`

- [ ] **Step 1: Rename the addon root directory with git**

Run:

```powershell
git mv plugin.video.embycon plugin.video.nextembycon
```

Expected: `git status --short` shows a rename or delete/add pair for the addon directory.

- [ ] **Step 2: Update addon.xml metadata**

Change the opening addon tag to:

```xml
<addon  id="plugin.video.nextembycon" 
        name="Next EmbyCon"
        version="0.1.0"
        provider-name="Ben">
```

Also update the context menu label in the same file:

```xml
<label>Next EmbyCon Actions</label>
```

- [ ] **Step 3: Update settings section id and built-in script actions**

In `resources/settings.xml`, change:

```xml
<section id="plugin.video.embycon">
```

to:

```xml
<section id="plugin.video.nextembycon">
```

Replace settings action data values such as:

```xml
<data>RunScript(plugin.video.embycon,0,?mode=DETECT_SERVER_USER)</data>
```

with:

```xml
<data>RunScript(plugin.video.nextembycon,0,?mode=DETECT_SERVER_USER)</data>
```

- [ ] **Step 4: Run the metadata test and verify it passes**

Run:

```powershell
python -m unittest tests.test_addon_metadata
```

Expected: `Ran 1 test` and `OK`.

### Task 3: Migrate Python Plugin URLs And Addon Asset Paths

**Files:**
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\functions.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\menu_functions.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\item_functions.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\play_utils.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\downloadutils.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\image_server.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\kodi_utils.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\context_monitor.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\custom_nodes.py`

- [ ] **Step 1: Replace plugin URL and RunScript references in Python**

Run a targeted search:

```powershell
rg -n "plugin://plugin\\.video\\.embycon|RunScript\\(plugin\\.video\\.embycon|special://home/addons/plugin\\.video\\.embycon|plugin\\.video\\.embycon-" plugin.video.nextembycon\resources\lib
```

Replace runtime references with the new id:

```text
plugin://plugin.video.nextembycon
RunScript(plugin.video.nextembycon
special://home/addons/plugin.video.nextembycon
plugin.video.nextembycon-
```

- [ ] **Step 2: Update the HomeWindow property prefix**

In `resources/lib/kodi_utils.py`, change:

```python
self.id_string = "plugin.video.embycon-%s"
```

to:

```python
self.id_string = "plugin.video.nextembycon-%s"
```

- [ ] **Step 3: Run the Python reference search again**

Run:

```powershell
rg -n "plugin://plugin\\.video\\.embycon|RunScript\\(plugin\\.video\\.embycon|special://home/addons/plugin\\.video\\.embycon|plugin\\.video\\.embycon-" plugin.video.nextembycon\resources\lib
```

Expected: no matches.

### Task 4: Migrate Skin XML And Skin Cloner References

**Files:**
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\skins\skin.estuary\17\xml\*.xml`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\skins\skin.estuary\18\xml\*.xml`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\skins\skin.estuary\19\xml\*.xml`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\skins\skin.estuary\21\xml\*.xml`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\skins\skin.estuary\copy_home.txt`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\plugin.video.nextembycon\resources\lib\skin_cloner.py`

- [ ] **Step 1: Replace plugin URLs and window properties in skin XML**

Run:

```powershell
rg -n "plugin\\.video\\.embycon|EmbyCon Play|EmbyCon Backgrounds" plugin.video.nextembycon\resources\skins
```

Replace runtime ids:

```text
plugin.video.embycon -> plugin.video.nextembycon
```

For visible labels and comments, use:

```text
Next EmbyCon Play
Next EmbyCon Backgrounds
```

- [ ] **Step 2: Update skin cloner addon path**

In `resources/lib/skin_cloner.py`, replace:

```python
embycon_path = os.path.join(kodi_home_path, "addons", "plugin.video.embycon")
```

with:

```python
embycon_path = os.path.join(kodi_home_path, "addons", "plugin.video.nextembycon")
```

- [ ] **Step 3: Verify skin references**

Run:

```powershell
rg -n "plugin\\.video\\.embycon" plugin.video.nextembycon\resources\skins plugin.video.nextembycon\resources\lib\skin_cloner.py
```

Expected: no matches, except historical text in comments if intentionally retained with an explanatory comment.

### Task 5: Update Repository Tooling And Tests

**Files:**
- Modify: `C:\Users\yqzzx\Projects\next-embycon\ruff.toml`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\scripts\check_strings.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\scripts\copy_embycon.ps1`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\scripts\process_addon.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\tests\test_playback_url.py`
- Modify: `C:\Users\yqzzx\Projects\next-embycon\tests\test_addon_metadata.py`

- [ ] **Step 1: Update test import path**

In `tests/test_playback_url.py`, change:

```python
sys.path.insert(0, str(ROOT / "plugin.video.embycon"))
```

to:

```python
sys.path.insert(0, str(ROOT / "plugin.video.nextembycon"))
```

- [ ] **Step 2: Update plugin URL expectations in tests**

Replace test URLs:

```text
plugin://plugin.video.embycon/
```

with:

```text
plugin://plugin.video.nextembycon/
```

- [ ] **Step 3: Update tooling paths**

Update hard-coded addon path strings in scripts and config:

```text
plugin.video.embycon -> plugin.video.nextembycon
```

This must include `ruff.toml`, `scripts/check_strings.py`, `scripts/copy_embycon.ps1`, and `scripts/process_addon.py`.

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m unittest discover tests
```

Expected: all tests pass.

### Task 6: Repository-Wide Identity Audit

**Files:**
- Inspect: all files under `C:\Users\yqzzx\Projects\next-embycon`

- [ ] **Step 1: Search for old addon id**

Run:

```powershell
rg -n "plugin\\.video\\.embycon" . --glob "!dist/**" --glob "!*.zip"
```

Expected matches after migration:

```text
README.md historical upstream references are acceptable only if they explicitly say this project was forked from EmbyCon.
docs/superpowers/plans/2026-07-05-next-embycon-addon-identity.md is acceptable because it documents the migration.
```

All runtime code, tests, settings, skin XML, scripts, and addon metadata must use `plugin.video.nextembycon`.

- [ ] **Step 2: Search for old visible product name**

Run:

```powershell
rg -n "EmbyCon" plugin.video.nextembycon tests scripts README.md --glob "!resources/language/**"
```

Expected: no user-facing runtime labels should say plain `EmbyCon` unless they are upstream attribution, protocol strings, or explanatory README text. Replace visible fork labels with `Next EmbyCon`.

- [ ] **Step 3: Run static syntax and string checks**

Run:

```powershell
python -m compileall plugin.video.nextembycon tests
python scripts\check_strings.py
git diff --check
```

Expected: `compileall` exit 0, string references valid with missing definitions 0, `git diff --check` exit 0.

### Task 7: Package Independent Addon Zip

**Files:**
- Create: `C:\Users\yqzzx\Projects\next-embycon\dist\plugin.video.nextembycon-0.1.0.zip`
- Copy: `F:\Movie\plugin.video.nextembycon-0.1.0.zip`

- [ ] **Step 1: Package from the renamed addon directory**

Use the existing PowerShell packaging pattern, but set:

```powershell
$addonDir = Join-Path $workspace 'plugin.video.nextembycon'
$zipName = "plugin.video.nextembycon-$version.zip"
```

The zip root must be `plugin.video.nextembycon/`, not `plugin.video.embycon/`.

- [ ] **Step 2: Verify zip contents**

Run:

```powershell
@'
from pathlib import Path
from zipfile import ZipFile
import re
zip_path = Path('dist/plugin.video.nextembycon-0.1.0.zip')
with ZipFile(zip_path) as zf:
    names = zf.namelist()
    assert all(name.startswith('plugin.video.nextembycon/') for name in names)
    assert not any('__pycache__/' in name or name.endswith('__pycache__') for name in names)
    addon_xml = zf.read('plugin.video.nextembycon/addon.xml').decode('utf-8', errors='replace')
    attrs = re.search(r'<addon\s+([^>]*)>', addon_xml, re.S).group(1)
    def attr(name):
        return re.search(r'(?:^|\s)%s="([^"]+)"' % name, attrs).group(1)
    assert attr('id') == 'plugin.video.nextembycon'
    assert attr('name') == 'Next EmbyCon'
    assert attr('version') == '0.1.0'
print('zip identity ok')
'@ | python -
```

Expected: `zip identity ok`.

- [ ] **Step 3: Verify copied zip hash**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'dist\plugin.video.nextembycon-0.1.0.zip','F:\Movie\plugin.video.nextembycon-0.1.0.zip' | Format-List Path,Hash
```

Expected: both hashes are identical.

### Task 8: Final Smoke Checklist

**Files:**
- Inspect: `C:\Users\yqzzx\Projects\next-embycon\dist\plugin.video.nextembycon-0.1.0.zip`

- [ ] **Step 1: Confirm install identity**

Report these facts from verification output:

```text
addon id: plugin.video.nextembycon
name: Next EmbyCon
version: 0.1.0
zip root: plugin.video.nextembycon/
```

- [ ] **Step 2: Confirm coexistence limitation**

Because this is a new addon id, it can coexist with upstream `plugin.video.embycon`, but user settings and Kodi addon data will start fresh. This is expected and should be called out in the release note.

- [ ] **Step 3: Commit as one identity migration commit**

Run:

```powershell
git add -A
git commit -m "Rename addon identity to Next EmbyCon"
```

Expected: one commit containing the identity migration and tests.
