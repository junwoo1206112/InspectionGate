import json
import subprocess

import pytest

from scripts import image_scan


def test_daemon_unavailable_writes_explicit_not_measured_report(tmp_path, monkeypatch):
    monkeypatch.setattr(image_scan.shutil, "which", lambda name: "docker.exe" if name == "docker" else None)
    monkeypatch.setattr(image_scan, "_safe_process", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "not connected"))
    report = image_scan.run("inspectiongate:test", tmp_path / "run")
    saved = json.loads((tmp_path / "run" / image_scan.REPORT_NAME).read_text())
    assert report["scan_status"] == saved["scan_status"] == "not_measured"
    assert saved["reason"] == "docker_daemon_unavailable"
    assert saved["findings"] is None and saved["policy_verdict"] == "not_evaluated"


def test_image_scan_never_uses_install_pull_or_database_download(tmp_path, monkeypatch):
    commands = []
    def fake(command, **kwargs):
        commands.append(command)
        if command[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(command, 0, "29.0", "")
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 0, '[{"Id":"sha256:abc","RepoDigests":[],"Os":"linux","Architecture":"amd64"}]', "")
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, "trivy 1.0", "")
        return subprocess.CompletedProcess(command, 0, '{"Results": []}', "")
    monkeypatch.setattr(image_scan.shutil, "which", lambda name: "tool.exe")
    monkeypatch.setattr(image_scan, "_safe_process", fake)
    report = image_scan.run("inspectiongate:test", tmp_path / "run")
    assert report["scan_status"] == "measured"
    assert all("pull" not in command and "install" not in command and "download-db-only" not in command for command in commands)
    scan_command = next(command for command in commands if command[:2] == ["trivy", "image"])
    assert ["--image-src", "docker"] == scan_command[2:4]
    assert "--skip-db-update" in scan_command


def test_existing_output_is_refused(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    with pytest.raises(FileExistsError):
        image_scan.run("inspectiongate:test", out)
