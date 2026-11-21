"""Build the local upload folder for Wili. Run: python art/tools/package_release.py"""
from pathlib import Path
import hashlib
import os
import shutil
import struct
import tempfile
import zipfile

PROJECT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT.parent / "wili"
ARCHIVE = PROJECT / "art/.work/release/wili.zip"
ROOT_FILES = ("modinfo.lua", "modmain.lua", "modicon.xml", "modicon.tex")
RUNTIME_TYPES = {
    "anim": {".zip"},
    "bigportraits": {".xml", ".tex"},
    "images": {".xml", ".tex"},
    "scripts": {".lua"},
    "sound": {".fev", ".fsb"},
}


def runtime_paths():
    result = list(ROOT_FILES)
    for folder, suffixes in RUNTIME_TYPES.items():
        for path in sorted((PROJECT / folder).rglob("*")):
            if path.is_file() and path.suffix.lower() in suffixes:
                result.append(path.relative_to(PROJECT).as_posix())
    return result


def path_hash(name):
    value = 0
    for byte in name.lower().encode("utf-8"):
        value = (value * 65599 + byte) & 0xffffffff
    return value


def make_manifest(names):
    # Keep the relative order of still-present entries in Klei's MNFS v1 index.
    previous = (PROJECT / "mod.manifest").read_bytes()
    magic, version, count = struct.unpack_from("<4sII", previous)
    if magic != b"MNFS" or version != 1 or len(previous) != 12 + count * 4:
        raise ValueError("Unsupported mod.manifest")
    ids = {path_hash(name) for name in names}
    if len(ids) != len(names):
        raise ValueError("Path hash collision")
    ordered = dict.fromkeys(h for (h,) in struct.iter_unpack("<I", previous[12:]) if h in ids)
    ordered.update((path_hash(name), None) for name in sorted(names))
    return struct.pack("<4sII", magic, version, len(ordered)) + struct.pack(f"<{len(ordered)}I", *ordered)


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


def replace_file(source, target):
    if target.is_file() and digest(target) == digest(source):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp:
        pending = Path(temp.name)
    try:
        shutil.copyfile(source, pending)
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)


def main():
    if PROJECT == OUTPUT or PROJECT.name.lower() != "wili-dev":
        raise SystemExit("Run this tool from the wili-dev checkout.")
    data_files = runtime_paths()
    names = sorted(data_files + ["mod.manifest"])
    if OUTPUT.is_symlink() or OUTPUT.is_junction() or OUTPUT.resolve().parent != PROJECT.parent:
        raise SystemExit("Unexpected release folder.")
    for item in OUTPUT.rglob("*"):
        if item.is_symlink() or item.is_junction():
            raise SystemExit(f"Unexpected link in release: {item}")
        if item.is_file() and item.relative_to(OUTPUT).as_posix() not in names:
            raise SystemExit(f"Move this extra file out of the release folder first: {item}")
        if item.is_dir() and not any(name.startswith(item.relative_to(OUTPUT).as_posix() + "/") for name in names):
            raise SystemExit(f"Move this extra directory out of the release folder first: {item}")
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ARCHIVE.parent) as staging:
        index = Path(staging) / "mod.manifest"
        index.write_bytes(make_manifest(names))
        archive = Path(staging) / "wili.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for name in names:
                z.write(index if name == "mod.manifest" else PROJECT / name, name)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() or sorted(z.namelist()) != names:
                raise ValueError("Invalid release archive")
            for name in names:
                source = index if name == "mod.manifest" else PROJECT / name
                if z.read(name) != source.read_bytes():
                    raise ValueError(f"File changed while archiving: {name}")
        for name in names:
            source = index if name == "mod.manifest" else PROJECT / name
            replace_file(source, OUTPUT / name)
            if digest(source) != digest(OUTPUT / name):
                raise ValueError(f"Release file verification failed: {name}")
        replace_file(index, PROJECT / "mod.manifest")
        os.replace(archive, ARCHIVE)
    print(f"Verified {len(names)} runtime files in {OUTPUT}")
    print(ARCHIVE)


if __name__ == "__main__":
    main()
