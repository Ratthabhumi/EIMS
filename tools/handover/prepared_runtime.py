"""Extract a reviewed runtime without pip/npm or touching application data."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import uuid
import zipfile


def safe_path(root, name):
    rel = PurePosixPath(name)
    if not name or rel.is_absolute() or ':' in name or chr(92) in name or '..' in rel.parts:
        raise ValueError('Unsafe runtime path')
    path = root.joinpath(*rel.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Runtime path escapes its root')
    return path


def verify(root):
    root = Path(root)
    rows = json.loads((root / 'runtime-manifest.json').read_text('utf-8'))['files']
    seen = set()
    for index, row in enumerate(rows, 1):
        name = row['path']
        if name in seen:
            raise ValueError('Duplicate runtime path')
        seen.add(name)
        path = safe_path(root, name)
        if path.is_symlink() or path.is_junction() or not path.is_file():
            raise ValueError('Missing or linked runtime file')
        if path.stat().st_size != row['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Runtime integrity mismatch: ' + name)
        if index % 250 == 0 or index == len(rows):
            print(f'Runtime check {index}/{len(rows)}', flush=True)
    # Python bytecode/runtime caches are not publisher files and may be created at run time.
    required = {'Python/python.exe', 'Node/node.exe', 'Frontend/server.js', 'Frontend/.next/BUILD_ID'}
    if not required <= seen:
        raise ValueError('Incomplete prepared runtime')
    for path in root.rglob('*'):
        if path.is_symlink() or path.is_junction():
            raise ValueError('Linked runtime path')
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        cache = ('__pycache__' in path.parts and path.suffix == '.pyc') or rel.startswith('Frontend/.next/cache/')
        if rel not in seen and rel != 'runtime-manifest.json' and not cache:
            raise ValueError('Unexpected runtime file: ' + rel)


def install(archive, destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('Existing runtime will not be overwritten')
    staging = destination.with_name(destination.name + '.incoming-' + uuid.uuid4().hex)
    staging.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        files = bundle.infolist()
        seen = set()
        for index, item in enumerate(files, 1):
            path = safe_path(staging, item.filename)
            if item.filename in seen or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Duplicate or linked archive entry')
            seen.add(item.filename)
            if item.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, path.open('xb') as target:
                    import shutil
                    shutil.copyfileobj(source, target)
            if index % 250 == 0 or index == len(files):
                print(f'Preparing runtime files {index}/{len(files)}', flush=True)
    verify(staging)
    staging.rename(destination)
    print('Prepared runtime ready - no dependency installation or build required.', flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'install':
        install(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'verify':
        verify(Path(sys.argv[2]))
    else:
        raise SystemExit('Expected install or verify')
