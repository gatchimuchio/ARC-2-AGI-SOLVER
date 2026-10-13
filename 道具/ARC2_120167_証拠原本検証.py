#!/usr/bin/env python3
"""ARC2 candidate224 証拠原本の復元・監査。

GitHub リポジトリのルートで、変更を伴わず原本を監査:
    python3 道具/ARC2_120167_証拠原本検証.py --verify-payload

原本アーカイブを任意のパスに復元する場合:
    python3 道具/ARC2_120167_証拠原本検証.py --verify-payload --output /tmp/ARC2-main-delta-120-167-evidence224.tar.xz

ソルバー、main、Git履歴、公式入力は変更しません。元のスコア再採点も行いません。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARTS = ROOT / '検証/外部更新受領/20261009_120167_証拠原本'


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def restore_archive(root: Path, output: Path) -> dict:
    index = json.loads((root / 'index.json').read_text(encoding='utf-8'))
    count = 0
    digest = hashlib.sha256()
    with output.open('xb') as dst:
        for number, info in enumerate(index['parts'], start=1):
            name = f'part-{number:04d}.bin'
            if info['file'] != name:
                raise ValueError(f'Part sequence invalid at {number}')
            part = root / 'parts' / name
            if part.is_symlink() or not part.is_file():
                raise ValueError(f'Part missing or symbolic link: {part}')
            data = part.read_bytes()
            if (len(data) != info['size'] or
                hashlib.sha256(data).hexdigest() != info['sha256'] or
                blob_sha(data) != info['git_blob_sha1']):
                raise ValueError(f'Part hash mismatch: {name}')
            dst.write(data)
            digest.update(data)
            count += len(data)
    if count != index['archive_size'] or digest.hexdigest() != index['archive_sha256']:
        raise ValueError('Reassembled archive hash mismatch')
    return index


def verify_payload(archive: Path) -> int:
    # Sequential TAR reading avoids decompression seek-amplification on .tar.xz.
    observed: dict[str, tuple[str,str,int]] = {}
    manifest = None
    with tarfile.open(archive, mode='r|xz') as stream:
        for member in stream:
            if not member.isfile():
                raise ValueError(f'Unexpected TAR member: {member.name}')
            src = stream.extractfile(member)
            if src is None:
                raise ValueError(f'Missing member content: {member.name}')
            if member.name == 'manifest.json':
                if manifest is not None:
                    raise ValueError('Repeated manifest.json')
                manifest = json.load(src)
                continue
            if not member.name.startswith('payload/'):
                # The package also carries README, verification and apply helper.
                # Still read non-payload members; their bytes are authenticated
                # by the full-archive SHA-256 verified before this stage.
                while src.read(1024 * 1024):
                    pass
                continue
            relative = member.name[len('payload/'):]
            if not relative or relative in observed:
                raise ValueError(f'Duplicate/invalid payload member: {member.name}')
            sha256 = hashlib.sha256()
            sha1 = hashlib.sha1(b'blob ' + str(member.size).encode('ascii') + b'\0')
            size = 0
            for piece in iter(lambda: src.read(1024 * 1024), b''):
                sha256.update(piece)
                sha1.update(piece)
                size += len(piece)
            if size != member.size:
                raise ValueError(f'Bad TAR member size: {member.name}')
            observed[relative] = (sha256.hexdigest(), sha1.hexdigest(), size)
    if manifest is None:
        raise ValueError('Package manifest absent')
    expected = manifest.get('files', [])
    if len(expected) != len(observed):
        raise ValueError(f'Unexpected payload count: expected {len(expected)}, seen {len(observed)}')
    seen = set()
    for row in expected:
        name = row['path']
        if name in seen or name not in observed:
            raise ValueError(f'Duplicate/missing manifest entry: {name}')
        sha256, sha1, size = observed[name]
        if sha256 != row['sha256'] or sha1 != row['git_blob_sha1']:
            raise ValueError(f'Payload digest mismatch: {name}')
        seen.add(name)
    return len(seen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parts-dir', type=Path, default=DEFAULT_PARTS)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify-payload', action='store_true')
    options = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='arc2-candidate224-verify-') as temp:
        output = options.output.expanduser().resolve() if options.output else Path(temp) / 'candidate224.tar.xz'
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            parser.error('Existing output file will not be overwritten')
        try:
            index = restore_archive(options.parts_dir, output)
            count = verify_payload(output) if options.verify_payload else None
        except Exception:
            output.unlink(missing_ok=True)
            raise
        print(json.dumps({
            'status': 'PASS',
            'archive_sha256': index['archive_sha256'],
            'archive_bytes': index['archive_size'],
            'parts': len(index['parts']),
            'payload_files_verified': count,
            'saved_archive': str(output) if options.output else None,
            'score_retested': False,
        }, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
