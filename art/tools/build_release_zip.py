"""Build a clean Steam Workshop / GitHub Release zip and SHA256SUMS.txt.

Usage:
    python art/tools/build_release_zip.py --tag v1.2.6 --out-dir dist

Uses package_release.py's exact runtime allow-list and MNFS v1 manifest index so
the archive contains only the files required by Don't Starve Together / Steam Workshop.
"""
from pathlib import Path
import argparse
import hashlib
import re
import sys
import zipfile

TOOLS = Path(__file__).resolve().parent
PROJECT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))
import package_release as pr  # noqa: E402

EXPECTED_TOP_LEVEL = {
    "anim",
    "bigportraits",
    "images",
    "scripts",
    "sound",
    "mod.manifest",
    "modicon.tex",
    "modicon.xml",
    "modinfo.lua",
    "modmain.lua",
}


def read_modinfo_version() -> str:
    text = (PROJECT / "modinfo.lua").read_text(encoding="utf-8")
    match = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version = \"...\" in modinfo.lua")
    return match.group(1)


def extract_changelog(version: str) -> str:
    readme = (PROJECT / "README.md").read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^###\s+{re.escape(version)}\b[^\n]*\n(.*?)(?=^###\s+|^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(readme)
    if match:
        body = match.group(1).strip()
        if body:
            return body
    return f"Wili {version} 正式版。"


def build_release(tag: str, out_dir: Path, allow_version_mismatch: bool = False) -> dict:
    version = tag[1:] if tag.startswith("v") else tag
    modinfo_version = read_modinfo_version()
    if not allow_version_mismatch and modinfo_version != version:
        raise ValueError(
            f"Tag version ({version}) does not match modinfo.lua version ({modinfo_version}). "
            "Update modinfo.lua before tagging."
        )

    data_files = pr.runtime_paths()
    names = sorted(data_files + ["mod.manifest"])
    top_level = {name.split("/", 1)[0] for name in names}
    if top_level != EXPECTED_TOP_LEVEL:
        raise ValueError(
            f"Unexpected top-level runtime entries: got {sorted(top_level)}, "
            f"expected {sorted(EXPECTED_TOP_LEVEL)}"
        )

    manifest_bytes = pr.make_manifest(names)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"wili-{version}.zip"
    zip_path = out_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            payload = manifest_bytes if name == "mod.manifest" else (PROJECT / name).read_bytes()
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED)

    # Verify archive integrity and byte-for-byte contents
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None or sorted(archive.namelist()) != names:
            raise ValueError("Archive integrity verification failed")
        for name in names:
            expected = manifest_bytes if name == "mod.manifest" else (PROJECT / name).read_bytes()
            if archive.read(name) != expected:
                raise ValueError(f"Archived content mismatch: {name}")

    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sums_path = out_dir / "SHA256SUMS.txt"
    sums_path.write_text(f"{sha256}  {zip_name}\n", encoding="utf-8")

    changelog = extract_changelog(version)
    notes = (
        f"Wili {version} 正式版\n\n"
        f"{changelog}\n\n"
        f"下载 `{zip_name}`（仅包含 Steam 创意工坊与游戏运行所需的 {len(names)} 个文件），"
        "解压后即可直接放入 Mod 目录或上传至 Steam 创意工坊。`SHA256SUMS.txt` 提供校验值。\n"
    )
    notes_path = out_dir / "RELEASE_NOTES.md"
    notes_path.write_text(notes, encoding="utf-8")

    print(f"Built {zip_path} ({zip_path.stat().st_size:,} bytes, {len(names)} files)")
    print(f"SHA256: {sha256}")
    return {
        "version": version,
        "zip_path": str(zip_path),
        "sums_path": str(sums_path),
        "notes_path": str(notes_path),
        "sha256": sha256,
        "file_count": len(names),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Release tag such as v1.2.7")
    parser.add_argument("--out-dir", type=Path, default=PROJECT / "art/.work/release")
    parser.add_argument("--allow-version-mismatch", action="store_true")
    args = parser.parse_args()
    build_release(args.tag, args.out_dir, allow_version_mismatch=args.allow_version_mismatch)


if __name__ == "__main__":
    main()
