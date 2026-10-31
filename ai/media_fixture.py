#!/usr/bin/env python3
"""Synthetic transport-stream -> MP4 diagnostic. NOT product recording E2E."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def command(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=45, check=False)

def probe(path):
    result = command(['ffprobe', '-v', 'error', '-count_packets', '-show_entries',
                      'stream=codec_type,codec_name,nb_read_packets', '-of', 'json', str(path)])
    if result.returncode:
        raise ValueError('FFPROBE_FAILED')
    streams = json.loads(result.stdout).get('streams', [])
    types = {x.get('codec_type') for x in streams if int(x.get('nb_read_packets') or 0) > 0}
    if not {'video', 'audio'}.issubset(types):
        raise ValueError('MISSING_AUDIO_OR_VIDEO_PACKETS')
    return [{'type': x.get('codec_type'), 'codec': x.get('codec_name'),
             'packets': int(x.get('nb_read_packets') or 0)} for x in streams]

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as src:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def inspect():
    report = {'schema': 'synthetic-media-fixture/v1', 'status': 'FAIL',
              'product_recording_e2e': 'NOT_RUN', 'release_readiness': 'NO_GO',
              'scope': 'short_local_synthetic_av_fixture_only'}
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        report['error_type'] = 'TOOL_MISSING'
        return report
    try:
        with tempfile.TemporaryDirectory(prefix='av-fixture-') as root:
            ts, mp4 = Path(root) / 'sample.ts', Path(root) / 'sample.mp4'
            generated = command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
               '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=12',
               '-f', 'lavfi', '-i', 'sine=frequency=660:sample_rate=48000',
               '-t', '2', '-c:v', 'mpeg2video', '-c:a', 'mp2', '-f', 'mpegts', '-y', str(ts)])
            if generated.returncode: raise ValueError('SYNTHETIC_TS_GENERATION_FAILED')
            ts_streams = probe(ts)
            converted = command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-i', str(ts), '-c:v', 'mpeg4', '-c:a', 'aac', '-y', str(mp4)])
            if converted.returncode: raise ValueError('MP4_CONVERSION_FAILED')
            mp4_streams = probe(mp4)
            for asset in (ts, mp4):
                decoded = command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-xerror', '-i', str(asset), '-f', 'null', '-'])
                if decoded.returncode: raise ValueError('FULL_DECODE_FAILED')
            report.update({'status': 'PASS', 'transport_stream': {'sha256': sha256(ts),
                            'bytes': ts.stat().st_size, 'streams': ts_streams},
                           'mp4': {'sha256': sha256(mp4), 'bytes': mp4.stat().st_size,
                                   'streams': mp4_streams}, 'full_decode': 'PASS'})
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        report['error_type'] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    result = inspect()
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(payload, encoding='utf-8')
    print(payload)
    return 0 if result['status'] == 'PASS' else 1

if __name__ == '__main__':
    sys.exit(main())
