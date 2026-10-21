"""Recompile editable art into a separate output folder; never install implicitly."""
from pathlib import Path
import argparse
import json
import shutil
import zipfile
import dst_art_pipeline as codec

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'art/source'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'art/.work/rebuilt')
    parser.add_argument('--verify-runtime', action='store_true')
    args = parser.parse_args()
    output = args.out.resolve()
    if output == ROOT:
        raise ValueError('Choose a separate output folder; review before replacing runtime assets')
    manifest = json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
    checked = []
    for record in manifest['animation_builds']:
        folder = SOURCE / record['source']
        destination = output / record['archive']
        codec.pack_archive(folder/'build.json', folder/'sprites', destination)
        if args.verify_runtime:
            with zipfile.ZipFile(destination) as compiled, zipfile.ZipFile(ROOT/record['archive']) as runtime:
                assert set(compiled.namelist()) == set(runtime.namelist()), record['archive']
                for name in runtime.namelist():
                    assert compiled.read(name) == runtime.read(name), (record['archive'], name)
        checked.append(record['archive'])
    for record in manifest['ui_textures']:
        destination = output / record['target']
        codec.encode_tex(SOURCE/record['source'], destination, record['format'])
        atlas = Path(record['target']).with_suffix('.xml')
        shutil.copy2(ROOT/atlas, output/atlas)
        if args.verify_runtime:
            assert destination.read_bytes() == (ROOT/record['target']).read_bytes(), record['target']
        checked.append(record['target'])
    print(json.dumps({'output':str(output),'rebuilt_art_resources':len(checked),
        'runtime_content_identical':True if args.verify_runtime else None},indent=2))

if __name__ == '__main__':
    main()
