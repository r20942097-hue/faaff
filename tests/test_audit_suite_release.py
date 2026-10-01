import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

import pytest

from tools.audit_suite_release import Candidate, audit_candidate, load_candidates, main, write_report


def candidate_for(path: Path, **kwargs) -> Candidate:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return Candidate("test", "1", path.name, digest, **kwargs)


def make_zip(path: Path, entries: list[tuple[str, bytes]]) -> None:
    with ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)


def test_safe_archive_passes(tmp_path: Path) -> None:
    archive = tmp_path / "safe.zip"
    make_zip(archive, [("root/readme.txt", b"ok")])
    result = audit_candidate(tmp_path, candidate_for(archive))
    assert result.status == "PASS"
    assert result.file_count == 1
    assert result.extracted_size == 2
    assert result.archive_size == archive.stat().st_size


@pytest.mark.parametrize(
    "name",
    ["../escape", "/absolute", "C:/drive", "dir\\file", "a//b", "NUL.txt", "file. "],
)
def test_unsafe_paths_fail(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "unsafe.zip"
    make_zip(archive, [(name, b"bad")])
    result = audit_candidate(tmp_path, candidate_for(archive))
    assert result.status == "FAIL"
    assert any("path" in finding for finding in result.findings)


def test_duplicate_and_unexpected_executable_fail(tmp_path: Path) -> None:
    archive = tmp_path / "duplicate.zip"
    with pytest.warns(UserWarning, match="Duplicate name"):
        make_zip(archive, [("run.ps1", b"one"), ("run.ps1", b"two")])
    result = audit_candidate(tmp_path, candidate_for(archive))
    assert result.status == "FAIL"
    assert any("duplicate" in finding for finding in result.findings)
    assert any("unexpected executable" in finding for finding in result.findings)


def test_allowlisted_executable_passes(tmp_path: Path) -> None:
    archive = tmp_path / "allowed.zip"
    make_zip(archive, [("launch.bat", b"echo safe")])
    result = audit_candidate(
        tmp_path, candidate_for(archive, executable_allowlist=("launch.bat",))
    )
    assert result.status == "PASS"


def test_symlink_and_size_limits_fail(tmp_path: Path) -> None:
    archive = tmp_path / "limits.zip"
    with ZipFile(archive, "w") as bundle:
        link = ZipInfo("link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        bundle.writestr(link, "target")
        bundle.writestr("large.bin", b"12345")
    result = audit_candidate(tmp_path, candidate_for(archive), member_limit=4, total_limit=8)
    assert result.status == "FAIL"
    assert any("symbolic link" in finding for finding in result.findings)
    assert any("member size" in finding for finding in result.findings)
    assert any("total extracted" in finding for finding in result.findings)


def test_unexpected_unix_permissions_fail(tmp_path: Path) -> None:
    archive = tmp_path / "permissions.zip"
    with ZipFile(archive, "w") as bundle:
        executable = ZipInfo("tool")
        executable.create_system = 3
        executable.external_attr = 0o100755 << 16
        bundle.writestr(executable, "safe fixture")
        privileged = ZipInfo("data.txt")
        privileged.create_system = 3
        privileged.external_attr = 0o104644 << 16
        bundle.writestr(privileged, "safe fixture")
    result = audit_candidate(tmp_path, candidate_for(archive))
    assert result.status == "FAIL"
    assert any("executable permission" in finding for finding in result.findings)
    assert any("special permission" in finding for finding in result.findings)


def test_portable_collisions_entry_limit_and_compression_ratio_fail(tmp_path: Path) -> None:
    archive = tmp_path / "portable.zip"
    make_zip(archive, [("Readme.txt", b"a" * 100), ("README.TXT", b"b" * 100)])
    result = audit_candidate(
        tmp_path,
        candidate_for(archive),
        entry_limit=1,
        compression_ratio_limit=0,
    )
    assert result.status == "FAIL"
    assert any("entry count" in finding for finding in result.findings)
    assert any("portable path collision" in finding for finding in result.findings)
    assert any("compression ratio" in finding for finding in result.findings)


def test_metadata_failure_does_not_decompress_archive(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    make_zip(archive, [("../escape", b"payload")])
    with patch("tools.audit_suite_release._verify_crc_bounded") as crc_check:
        result = audit_candidate(tmp_path, candidate_for(archive))
    assert result.status == "FAIL"
    crc_check.assert_not_called()


def test_crc_corruption_is_reported_with_bounded_streaming(tmp_path: Path) -> None:
    archive = tmp_path / "corrupt.zip"
    payload = b"unique_payload_for_crc"
    make_zip(archive, [("payload.txt", payload)])
    raw = archive.read_bytes()
    offset = raw.index(payload)
    archive.write_bytes(raw[:offset] + bytes([raw[offset] ^ 1]) + raw[offset + 1:])
    result = audit_candidate(tmp_path, candidate_for(archive))
    assert result.status == "FAIL"
    assert any("CRC/content validation error" in finding for finding in result.findings)


def test_archive_file_boundary_checks(tmp_path: Path) -> None:
    archive = tmp_path / "large.zip"
    make_zip(archive, [("payload.txt", b"payload")])
    result = audit_candidate(tmp_path, candidate_for(archive), archive_limit=1)
    assert result.status == "FAIL"
    assert result.findings == ["archive size limit exceeded"]

    link = tmp_path / "link.zip"
    link.symlink_to(archive)
    linked = Candidate(
        "test", "1", link.name, hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    result = audit_candidate(tmp_path, linked)
    assert result.status == "FAIL"
    assert "non-symlink" in result.findings[0]


def test_missing_archive_is_not_run_and_report_is_deterministic(tmp_path: Path) -> None:
    item = Candidate("missing", "1", "missing.zip", "0" * 64)
    result = audit_candidate(tmp_path, item)
    assert result.status == "NOT RUN"
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    write_report([result], first)
    write_report([result], second)
    assert first.read_bytes() == second.read_bytes()


def test_report_write_is_atomic_and_creates_parent(tmp_path: Path) -> None:
    output = tmp_path / "new" / "report.json"
    missing = audit_candidate(
        tmp_path, Candidate("missing", "1", "missing.zip", "0" * 64)
    )
    write_report([missing], output)
    report = json.loads(output.read_text())
    assert report["overall_status"] == "NOT RUN"
    assert list(output.parent.iterdir()) == [output]


def test_sha_mismatch_fails_before_zip_processing(tmp_path: Path) -> None:
    archive = tmp_path / "candidate.zip"
    archive.write_bytes(b"not a zip")
    item = Candidate("test", "1", archive.name, "0" * 64)
    result = audit_candidate(tmp_path, item)
    assert result.status == "FAIL"
    assert result.findings == ["SHA-256 mismatch"]


def test_inventory_rejects_invalid_digest(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": 1, "candidates": [{
        "product": "x", "version": "1", "filename": "x.zip", "sha256": "bad"
    }]}))
    with pytest.raises(ValueError, match="invalid SHA-256"):
        load_candidates(inventory)


@pytest.mark.parametrize("filename", ["../x.zip", "folder/x.zip", "NUL.zip", "x.txt"])
def test_inventory_rejects_unsafe_candidate_filename(tmp_path: Path, filename: str) -> None:
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": 1, "candidates": [{
        "product": "x", "version": "1", "filename": filename, "sha256": "0" * 64
    }]}))
    with pytest.raises(ValueError, match="candidate filename"):
        load_candidates(inventory)


def test_inventory_rejects_portable_duplicate_and_unsafe_allowlist(tmp_path: Path) -> None:
    base = {"product": "x", "version": "1", "sha256": "0" * 64}
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": 1, "candidates": [
        {**base, "filename": "A.zip"}, {**base, "filename": "a.ZIP"}
    ]}))
    with pytest.raises(ValueError, match="duplicate candidate filename"):
        load_candidates(inventory)
    inventory.write_text(json.dumps({"schema_version": 1, "candidates": [
        {**base, "filename": "a.zip", "executable_allowlist": ["../run.cmd"]}
    ]}))
    with pytest.raises(ValueError, match="unsafe executable_allowlist"):
        load_candidates(inventory)


def test_cli_is_fail_closed_for_not_run(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": 1, "candidates": [{
        "product": "x", "version": "1", "filename": "x.zip", "sha256": "0" * 64
    }]}))
    output = tmp_path / "report.json"
    args = ["--inventory", str(inventory), "--artifact-dir", str(tmp_path), "--output", str(output)]
    assert main(args) == 2
    assert main([*args, "--allow-not-run"]) == 0
    report = json.loads(output.read_text())
    assert report["overall_status"] == "NOT RUN"
    assert report["summary"] == {"PASS": 0, "FAIL": 0, "NOT RUN": 1}
