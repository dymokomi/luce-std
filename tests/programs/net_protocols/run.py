#!/usr/bin/env python3
"""Native protocol contracts plus independent RFC handshake reference vectors."""
import base64
import hashlib
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT.parent / 'luce-base/build/luce-base'
FLAGS = [['--native', '--opt', str(level)] for level in range(4)] + [
    ['--backend=c'], ['--backend=c', '--release']]
EXPECTED = (b'ok HTTP heads, framing, every fragment size, limits and EOF\n'
            b'ok WebSocket handshake, masking, fragmented UTF-8, control frames and errors\n'
            b'ok 10000 deterministic malformed-input cases\n')


def checked(command, timeout=120):
    result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, timeout=timeout)
    assert result.returncode == 0 and not result.stderr, (command, result.returncode, result.stdout, result.stderr)
    return result.stdout


binary = ROOT / 'build/net-protocol-contracts'
rng = random.Random(6455)
keys = [base64.b64encode(bytes(rng.getrandbits(8) for _ in range(16))) for _ in range(64)]
for flags in FLAGS:
    checked([COMPILER, 'build', ROOT / 'tests/programs/net_protocols/main.lucb', *flags, '-o', binary])
    assert checked([binary]) == EXPECTED
    for key in keys:
        expected = base64.b64encode(hashlib.sha1(key + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest()) + b'\n'
        assert checked([binary, 'accept', key.decode()]) == expected
    for size in (0, 125, 126, 65535, 65536):
        payload = ('abcXYZ' * ((size + 5) // 6))[:size]
        payload_file = ROOT / 'build/net-protocol-payload.bin'
        payload_file.write_bytes(payload.encode())
        for client in (False, True):
            wire = checked([binary, 'frame-file', 'client' if client else 'server', payload_file])
            assert wire[0] == 0x82 and bool(wire[1] & 0x80) == client
            length = wire[1] & 0x7f
            at = 2
            if length == 126:
                length = int.from_bytes(wire[2:4], 'big')
                at = 4
                assert 126 <= length <= 65535
            elif length == 127:
                length = int.from_bytes(wire[2:10], 'big')
                at = 10
                assert 65536 <= length < 2**63
            assert length == size
            if client:
                mask = wire[at:at + 4]
                at += 4
                body = bytes(value ^ mask[index % 4] for index, value in enumerate(wire[at:]))
            else:
                body = wire[at:]
            assert body == payload.encode() and len(wire) == at + size
    print('PASS protocol contracts and 64 independent handshake vectors:', ' '.join(flags), flush=True)
