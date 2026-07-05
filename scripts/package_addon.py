from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def read_addon_attributes(addon_dir: Path) -> dict[str, str]:
    addon_xml = (addon_dir / "addon.xml").read_text(encoding="utf-8")
    addon_match = re.search(r"<addon\s+([^>]*)>", addon_xml, re.S)
    if addon_match is None:
        raise ValueError("addon.xml is missing the addon tag")

    attributes: dict[str, str] = {}
    for name, value in re.findall(r"(?:^|\s)([\w-]+)=\"([^\"]+)\"", addon_match.group(1)):
        attributes[name] = value
    return attributes


def build_zip(addon_dir: Path, dist_dir: Path, copy_to: Path | None = None) -> Path:
    addon_dir = addon_dir.resolve()
    dist_dir = dist_dir.resolve()
    attributes = read_addon_attributes(addon_dir)
    addon_id = attributes["id"]
    version = attributes["version"]

    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / f"{addon_id}-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zip_file:
        for file_path in sorted(addon_dir.rglob("*")):
            if file_path.is_dir() or "__pycache__" in file_path.parts:
                continue
            arcname = Path(addon_id) / file_path.relative_to(addon_dir)
            zip_file.write(file_path, arcname.as_posix())

    if copy_to is not None:
        copy_to.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, copy_to / zip_path.name)

    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the Kodi addon zip.")
    parser.add_argument("--addon-dir", default="plugin.video.embycon")
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument("--copy-to")
    args = parser.parse_args()

    zip_path = build_zip(
        Path(args.addon_dir),
        Path(args.dist_dir),
        Path(args.copy_to) if args.copy_to else None,
    )
    print(zip_path)


if __name__ == "__main__":
    main()
