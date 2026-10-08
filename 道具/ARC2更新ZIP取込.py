#!/usr/bin/env python3
"""ARC2 one-file update importer. Read-only by default; never deletes existing files.

Usage:
  python 道具/ARC2更新ZIP取込.py --zip /path/to/ARC2-update-99-140-onefile-20261008.zip
  python 道具/ARC2更新ZIP取込.py --zip /path/to/ARC2-update-99-140-onefile-20261008.zip --apply --push

The ZIP's source/ files are the only files imported into the runtime tree.
External official-input/, logical-evidence/ and evidence/ are NOT installed.
"""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ZIP_ENTRIES = {
    'dependency-audit.json', 'README_日本語.txt', 'manifest.json',
    'verify_update.py', 'unpack_verify.py', 'payload.tar.xz',
}

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def safe_path(raw):
    path = PurePosixPath(raw)
    if (not path.parts or path.is_absolute() or '..' in path.parts
            or '\\' in raw or ':' in raw or any(x in ('', '.') for x in path.parts)):
        raise ValueError(f'Unsafe archive path: {raw!r}')
    return path


def git(root, *args, capture=True):
    r = subprocess.run(['git', '-C', str(root), *args], check=True,
                       text=True, capture_output=capture)
    return r.stdout.strip() if capture else ''


def extract_verified_source(archive, staging):
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist()) != ZIP_ENTRIES or len(z.infolist()) != len(ZIP_ENTRIES):
            raise ValueError('Unexpected ZIP entries')
        manifest = json.loads(z.read('manifest.json'))
        files = manifest['files']
        paths = set()
        objects = set()
        source_by_object = {}
        for record in files:
            p = safe_path(record['path'])
            ob = safe_path(record['object'])
            if record['path'] in paths:
                raise ValueError('Duplicate path in manifest')
            paths.add(record['path'])
            if ob.parts != ('objects', record['sha256']):
                raise ValueError(f'Bad object mapping: {p}')
            objects.add(record['object'])
            if p.parts[0] == 'source':
                if len(p.parts) < 2:
                    raise ValueError('Empty source path')
                source_by_object.setdefault(record['object'], []).append(record)
        # Decompress to a seekable *temporary* TAR. Random access avoids the
        # multi-minute skip penalty observed with 1GB streaming tar.xz reads.
        tar_path = staging / 'payload.tar'
        with z.open('payload.tar.xz') as source, lzma.LZMAFile(source) as decompressed:
            with tar_path.open('wb') as out:
                shutil.copyfileobj(decompressed, out, 1024 * 1024)
    source_dir = staging / 'source'
    source_dir.mkdir()
    seen = set()
    with tarfile.open(tar_path, 'r:') as tar:
        for entry in tar:
            if not entry.isfile() or entry.name not in objects or entry.name in seen:
                raise ValueError(f'Unexpected/duplicate TAR entry: {entry.name}')
            safe_path(entry.name)
            h = hashlib.sha256()
            rows = source_by_object.get(entry.name, [])
            target = None
            if rows:
                target = source_dir / entry.name.removeprefix('objects/')
                target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(entry) as inp:
                with target.open('wb') if target is not None else open(os.devnull, 'wb') as out:
                    for chunk in iter(lambda: inp.read(1024 * 1024), b''):
                        h.update(chunk)
                        if target is not None:
                            out.write(chunk)
            if h.hexdigest() != entry.name.split('/')[-1]:
                raise ValueError(f'TAR object SHA256 mismatch: {entry.name}')
            seen.add(entry.name)
        if seen != objects:
            raise ValueError(f'Missing TAR objects: {len(objects - seen)}')
    result = []
    for rows in source_by_object.values():
        obj_file = source_dir / rows[0]['sha256']
        for rec in rows:
            if obj_file.stat().st_size != rec['bytes']:
                raise ValueError(f'Size mismatch: {rec["path"]}')
            result.append((rec['path'][7:], obj_file, rec['mode']))
    return manifest, result


def audit_target(root, source):
    counts = {'identical': 0, 'replace-tracked': 0, 'new': 0, 'untracked-conflict': 0,
              'symlink-conflict': 0}
    examples = {x: [] for x in counts}
    tracked = set(git(root, 'ls-files', '-z').split('\0'))
    for relative, src, _ in source:
        dest = root / relative
        parents = [root / Path(*Path(relative).parts[:n])
                   for n in range(1, len(Path(relative).parts))]
        if dest.is_symlink() or any(p.is_symlink() for p in parents):
            key = 'symlink-conflict'
        elif dest.is_file() and digest(dest) == src.name:
            key = 'identical'
        elif dest.exists() and (relative not in tracked or not dest.is_file()):
            key = 'untracked-conflict'
        elif relative in tracked:
            key = 'replace-tracked'
        else:
            key = 'new'
        counts[key] += 1
        if len(examples[key]) < 12:
            examples[key].append(relative)
    return {'counts': counts, 'examples': examples}


def install(root, source):
    for relative, src, mode in source:
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file() or digest(dest) != src.name:
            with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
                scratch = Path(tmp.name)
            try:
                shutil.copyfile(src, scratch)
                os.chmod(scratch, mode)
                os.replace(scratch, dest)
            finally:
                scratch.unlink(missing_ok=True)
        os.chmod(dest, mode)
    paths = [rel for rel, _, _ in source]
    for i in range(0, len(paths), 50):
        git(root, 'add', '-f', '--', *paths[i:i + 50])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', dest='archive', required=True, type=Path)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--apply', action='store_true', help='Import, commit on integration branch and fast-forward main')
    parser.add_argument('--push', action='store_true', help='With --apply only, push main to origin')
    a = parser.parse_args()
    if a.push and not a.apply:
        parser.error('--push requires --apply')
    root = a.repo.resolve()
    if git(root, 'rev-parse', '--show-toplevel') != str(root):
        parser.error('--repo must be repository root')
    archive = a.archive.resolve()
    if not archive.is_file():
        parser.error('ZIP not found')
    zip_sha = digest(archive)
    with tempfile.TemporaryDirectory(prefix='arc2-package-audit-') as temp:
        manifest, source = extract_verified_source(archive, Path(temp))
        audit = audit_target(root, source)
        output = {
            'zip_sha256': zip_sha,
            'provenance_commit': manifest['accepted_commit_provenance'],
            'source_files_verified': len(source),
            'total_archive_entries_verified': len(manifest['files']),
            'changes': audit,
            'logical_evidence_imported': False,
            'official_input_imported': False,
            'existing_paths_deleted': False,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
        if not a.apply:
            print('READ-ONLY: no files modified.')
            return
        counts = audit['counts']
        if counts['untracked-conflict'] or counts['symlink-conflict']:
            raise SystemExit('Conflict detected; import rejected without changes.')
        if git(root, 'branch', '--show-current') != 'main':
            raise SystemExit('Switch to main before --apply.')
        if git(root, 'status', '--porcelain', '--untracked-files=all'):
            raise SystemExit('Working directory must be clean before --apply.')
        if not (counts['replace-tracked'] or counts['new']):
            print('No changes to commit; existing contents already match.')
            return
        head = git(root, 'rev-parse', 'HEAD')
        existing_branches = git(root, 'branch', '--list')
        backup = 'backup/arc2-before-99-140-' + head[:12]
        branch = 'import/arc2-99-140-' + head[:12]
        if branch in existing_branches or backup in existing_branches:
            raise SystemExit('Import/backup branch already exists; inspect before rerun.')
        git(root, 'branch', backup, head)
        git(root, 'switch', '-c', branch)
        install(root, source)
        git(root, 'commit', '-m', 'arc2: import verified candidate177 99/140 source from onefile ZIP')
        git(root, 'switch', 'main')
        git(root, 'merge', '--ff-only', branch)
        print('LOCAL MAIN UPDATED:', git(root, 'rev-parse', 'HEAD'))
        print('Backup branch:', backup)
        if a.push:
            git(root, 'push', 'origin', 'main')
            print('REMOTE MAIN UPDATED')
        else:
            print('No remote push requested; use --push to opt in.')

if __name__ == '__main__':
    main()
