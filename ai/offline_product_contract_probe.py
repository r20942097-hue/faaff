"""Read-only bounded ZIP -> isolated offline RPLAY pure-module contract check.

This verifier is NOT browser E2E and MUST NOT be treated as release approval.
The only executable product bytes are three pure JS modules, started by the
Linux wrapper inside a separate network namespace with restricted filesystem
permissions. A trusted independent digest must be supplied explicitly.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile

MODULES = ('hls_window.js', 'hls_ledger.js', 'http_resume.js')
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 160 * 1024 * 1024
MAX_ENTRY_BYTES = 16 * 1024 * 1024
MAX_MEMBERS = 2048
MAX_RATIO = 1000
SHA = re.compile(r'[0-9a-f]{64}\Z')
WINDOWS_DEVICE = re.compile(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$',re.I)

# Content identities bind the diagnostic to the reviewed suite and wrapper.
# These hashes establish *suite consistency*, NOT the provenance of the ZIP.
PINNED_SUITE_SHA256 = '875ada3ea10b862b251299d6fff6efbc91e5e1235dedeb8c2e7da67ff89cbfab'
PINNED_WRAPPER_SHA256 = 'a71dba8f85418c0d8dd9cc4f4511d51ecc84dfe67d0da20697b4d5306ab76ea6'
EXPECTED_COUNT = 417
EXPECTED_SCOPE = ('RPLAY v2.67 actual pure HLS ledger/window/range JS; '
                  'synthetic metadata; restricted Node permissions; not browser/recording E2E')


def reviewed_runner_files(suite: Path, wrapper: Path) -> bool:
    """Fail closed if the diagnostic or sandbox launcher differs from the reviewed bytes."""
    if suite.is_symlink() or wrapper.is_symlink() or not suite.is_file() or not wrapper.is_file():
        return False
    try:
        if suite.stat().st_size > 32 * 1024 or wrapper.stat().st_size > 8 * 1024:
            return False
        return (hashlib.sha256(suite.read_bytes()).hexdigest() == PINNED_SUITE_SHA256
                and hashlib.sha256(wrapper.read_bytes()).hexdigest() == PINNED_WRAPPER_SHA256)
    except OSError:
        return False



def archive_bytes(path: Path, expected: str) -> bytes:
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise ValueError('INVALID_TRUSTED_DIGEST')
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != '.zip':
        raise ValueError('EXPECTED_REGULAR_ZIP')
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('ARCHIVE_EXCEEDS_SIZE_LIMIT')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('ARCHIVE_DIGEST_MISMATCH')
    return raw


def safe_name(name: str) -> bool:
    if not name or name.startswith('/') or '\\' in name or '\x00' in name:
        return False
    parts=name.rstrip('/').split('/')
    return all(part and part not in ('.','..') and not part.endswith((' ','.'))
               and not WINDOWS_DEVICE.fullmatch(part)
               and not any(ord(c)<32 or c in '<>:"|?*' for c in part)
               for part in parts)


def extract_pure_modules(raw: bytes, root: str, out: Path) -> dict:
    if (not isinstance(root, str) or not root.endswith('/') or not safe_name(root+'manifest.json')
            or root.startswith('/') or '//' in root):
        raise ValueError('INVALID_SELECTED_ROOT')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info=archive.infolist()
        if not info or len(info)>MAX_MEMBERS:
            raise ValueError('INVALID_ARCHIVE_MEMBER_COUNT')
        seen=set(); size=0; contents={}
        required={root+'manifest.json',*(root+m for m in MODULES)}
        for entry in info:
            if (not safe_name(entry.filename) or entry.flag_bits & 1 or
                    stat.S_ISLNK(entry.external_attr >> 16) or
                    (stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise ValueError('UNSAFE_ARCHIVE_MEMBER')
            key=unicodedata.normalize('NFC',entry.filename.rstrip('/')).casefold()
            if key in seen:
                raise ValueError('ARCHIVE_PATH_COLLISION')
            seen.add(key)
            if entry.file_size > MAX_ENTRY_BYTES:
                raise ValueError('ARCHIVE_ENTRY_SIZE_LIMIT')
            size+=entry.file_size
            if size > MAX_UNCOMPRESSED_BYTES:
                raise ValueError('ARCHIVE_TOTAL_SIZE_LIMIT')
            if entry.file_size and (not entry.compress_size or entry.file_size/entry.compress_size>MAX_RATIO):
                raise ValueError('ARCHIVE_COMPRESSION_RATIO_LIMIT')
            # The entire archive is CRC-scanned, not only the source files selected below.
            # ZipFile.open validates each member CRC while streaming.
            with archive.open(entry) as f:
                processed=0; target=bytearray() if entry.filename in required else None
                for chunk in iter(lambda:f.read(256*1024),b''):
                    processed+=len(chunk)
                    if processed > entry.file_size or processed > MAX_ENTRY_BYTES:
                        raise ValueError('UNBOUNDED_ARCHIVE_MEMBER')
                    if target is not None: target.extend(chunk)
                if processed != entry.file_size:
                    raise ValueError('ARCHIVE_ENTRY_SIZE_MISMATCH')
                if target is not None: contents[entry.filename]=bytes(target)
        if required != contents.keys():
            raise ValueError('REQUIRED_SOURCE_MODULE_MISSING')
        manifest=json.loads(contents[root+'manifest.json'].decode('utf-8'))
        if manifest.get('manifest_version')!=3 or manifest.get('background',{}).get('service_worker')!='background.js':
            raise ValueError('UNEXPECTED_MANIFEST_TARGET')
        for name in MODULES:
            (out/name).write_bytes(contents[root+name])
            (out/name).chmod(0o644)
        return {'zip_entries_checked':len(info),'staged_modules':len(MODULES),
                'module_sha256':{name:hashlib.sha256(contents[root+name]).hexdigest() for name in MODULES},
                'scope':'ACTUAL_PURE_MODULES_SYNTHETIC_METADATA_ONLY'}


def run_isolated(staging: Path, suite: Path, wrapper: Path) -> dict:
    for tool in ('unshare','setpriv','node','bash','ip'):
        if not shutil.which(tool):
            return {'status':'BLOCKED','reason':'ISOLATION_TOOL_UNAVAILABLE_'+tool.upper()}
    if sys.platform!='linux' or not Path('/proc/self/ns/net').exists():
        return {'status':'BLOCKED','reason':'LINUX_NETNS_REQUIRED'}
    if not reviewed_runner_files(suite, wrapper):
        return {'status':'BLOCKED','reason':'REVIEWED_SUITE_OR_WRAPPER_HASH_MISMATCH'}
    env={key:os.environ[key] for key in ('PATH','HOME','LANG') if key in os.environ}
    env.update(GPT1_MODULE_DIR=str(staging), GPT1_TEST_SUITE=str(suite),
               GPT1_PARENT_NETNS=os.readlink('/proc/self/ns/net'))
    cmd=['unshare','--user','--net','--map-users','0:0:3','--map-groups','0:0:3',
         'bash',str(wrapper)]
    try:
        proc=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=30,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return {'status':'BLOCKED','reason':'ISOLATION_PROCESS_UNAVAILABLE_OR_TIMEOUT'}
    if proc.returncode!=0:
        return {'status':'BLOCKED','reason':'ISOLATED_RUNNER_NONZERO','exit_code':proc.returncode}
    try:
        lines=proc.stdout.splitlines()
        if len(lines)!=2 or lines[0]!='GPT1_ISOLATION_PROVEN_BY_WRAPPER':
            return {'status':'BLOCKED','reason':'ISOLATION_WRAPPER_RECEIPT_MISSING'}
        result=json.loads(lines[1])
        if (('network_isolated' in result and result['network_isolated'] is not True) or
                ('filesystem_permission_model' in result and
                 result['filesystem_permission_model'] != 'NODE_PERMISSION')):
            return {'status':'BLOCKED','reason':'CONFLICTING_ISOLATION_CLAIM'}
        result['network_isolated']=True
        result['filesystem_permission_model']='NODE_PERMISSION'
    except (json.JSONDecodeError,TypeError):
        return {'status':'BLOCKED','reason':'ISOLATED_RESULT_NOT_JSON'}
    if (result.get('status')!='PASS' or type(result.get('count')) is not int or
            result['count'] != EXPECTED_COUNT or result.get('test_scope') != EXPECTED_SCOPE or
            result.get('network_isolated') is not True or
            result.get('filesystem_permission_model') != 'NODE_PERMISSION'):
        return {'status':'BLOCKED','reason':'ISOLATED_EVIDENCE_INCOMPLETE'}
    return result


def inspect(path: Path, trusted_sha256: str, root: str, suite: Path, wrapper: Path) -> dict:
    report={'schema':'gpt1-offline-product-contract/v1','status':'BLOCKED',
            'product_browser':'NOT_RUN','real_site':'NOT_RUN','recording':'NOT_RUN',
            'mp4_output':'NOT_RUN','firefox_device':'NOT_RUN','windows_device':'NOT_RUN',
            'release_decision':'CANDIDATE_NO_GO','trusted_source_provenance':'NOT_VERIFIED',
            'test_suite_provenance':'PINNED_CONTENT_HASH_ONLY_NOT_SIGNED'}
    try:
        raw=archive_bytes(path,trusted_sha256)
        report['candidate_sha256']=hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory(prefix='gpt1-contract-') as temp:
            staged=Path(temp)/'staged'; staged.mkdir(mode=0o755)
            stage=extract_pure_modules(raw,root,staged)
            report['archive_check']=stage
            # The isolated non-root UID must be able to read the disposable fixture,
            # but original candidate bytes remain outside the sandbox process.
            Path(temp).chmod(0o755)
            tested=run_isolated(staged,suite,wrapper)
            report['isolated_contract']=tested
            if tested.get('status')!='PASS':
                report['reason']=tested.get('reason','ISOLATED_TEST_FAILED')
                return report
            report['status']='PASS_OFFLINE_CONTRACT_ONLY'
    except (OSError,ValueError,zipfile.BadZipFile,json.JSONDecodeError,UnicodeError) as err:
        report['reason']=str(err) if isinstance(err,ValueError) else type(err).__name__
    return report


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--root',default='rplay-stable-player-extension/')
    parser.add_argument('--suite',type=Path,default=Path(__file__).parent/'tests'/'product_contracts.js')
    parser.add_argument('--wrapper',type=Path,default=Path(__file__).parent/'tests'/'isolate_node.sh')
    args=parser.parse_args(argv)
    result=inspect(args.candidate,args.sha256,args.root,args.suite,args.wrapper)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS_OFFLINE_CONTRACT_ONLY' else 2

if __name__=='__main__':sys.exit(main())
