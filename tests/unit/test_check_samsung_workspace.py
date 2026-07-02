# SPDX-License-Identifier: AGPL-3.0-or-later
# Commercial license available
# © Concepts 1996–2026 Miroslav Šotek. All rights reserved.
# © Code 2020–2026 Miroslav Šotek. All rights reserved.
# ORCID: 0009-0009-3560-0851
# Contact: www.anulum.li | protoscience@anulum.li
# SCPN-MIF-CORE — Samsung workspace guard tests.
"""Tests for the Samsung GOTM workspace locality guard."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from tools import check_samsung_workspace
from tools.check_samsung_workspace import (
    MountInfo,
    WorkspacePolicy,
    collect_workspace_errors,
    main,
)


def _write_executable(path: Path, text: str = "#!/bin/sh\nexit 0\n") -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _make_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, patch_mount: bool = True
) -> tuple[Path, WorkspacePolicy]:
    gotm_root = tmp_path / "media" / "anulum" / "GOTM" / "aaa_God_of_the_Math_Collection"
    repo = gotm_root / "03_CODE" / "SCPN-MIF-CORE"
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()

    policy = WorkspacePolicy(
        expected_repo_root=repo,
        gotm_root=gotm_root,
        expected_mount=gotm_root.parent,
        forbidden_roots=(),
    )

    if patch_mount:

        def fake_mount_info(path: Path) -> MountInfo:
            del path
            return MountInfo(target=gotm_root.parent, fstype="ext4", source="/dev/test")

        monkeypatch.setattr(check_samsung_workspace, "_mount_info", fake_mount_info)
    return repo, policy


def _make_complete_venv(repo: Path) -> Path:
    venv = repo / ".venv"
    bin_dir = venv / "bin"
    bin_dir.mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    for name in ("python", "pytest", "mypy", "ruff", "maturin"):
        _write_executable(bin_dir / name)
    return venv


def test_complete_linux_venv_and_pnpm_internal_links_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)
    pnpm_target = repo / "studio-web" / "node_modules" / ".pnpm" / "react@19" / "node_modules" / "react"
    pnpm_target.mkdir(parents=True)
    public_link = repo / "studio-web" / "node_modules" / "react"
    public_link.parent.mkdir(parents=True, exist_ok=True)
    public_link.symlink_to(Path(".pnpm/react@19/node_modules/react"))

    assert collect_workspace_errors(repo, policy=policy) == []


def test_venv_root_must_not_be_a_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    target = tmp_path / "outside-venv"
    target.mkdir()
    (repo / ".venv").symlink_to(target, target_is_directory=True)

    errors = collect_workspace_errors(repo, policy=policy)

    assert any(".venv must be a real directory, not a symlink" in error for error in errors)


def test_missing_required_venv_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)

    errors = collect_workspace_errors(repo, policy=policy)

    assert ".venv is missing; create it on the Samsung GOTM checkout" in errors


def test_file_dependency_tree_root_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)
    (repo / "target").write_text("not a directory\n", encoding="utf-8")

    errors = collect_workspace_errors(repo, policy=policy)

    assert "target must be a directory" in errors


def test_optional_dependency_tree_may_be_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)

    assert collect_workspace_errors(repo, policy=policy) == []


def test_windows_layout_venv_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    scripts = repo / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    _write_executable(scripts / "python.exe")
    (repo / ".venv" / "pyvenv.cfg").write_text("home = C:/Python312\n", encoding="utf-8")

    errors = collect_workspace_errors(repo, policy=policy)

    assert any(".venv must expose a Linux bin/python interpreter" in error for error in errors)
    assert any(".venv must not use a Windows Scripts/ layout" in error for error in errors)


def test_venv_requires_pyvenv_cfg_and_executable_toolchain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    bin_dir = repo / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    _write_executable(bin_dir / "python")
    _write_executable(bin_dir / "pytest")
    (bin_dir / "mypy").write_text("#!/bin/sh\n", encoding="utf-8")
    _write_executable(bin_dir / "ruff")

    errors = collect_workspace_errors(repo, policy=policy)

    assert ".venv must contain pyvenv.cfg" in errors
    assert ".venv/bin/mypy must be executable" in errors
    assert ".venv/bin/maturin is missing from the full project toolchain" in errors


def test_venv_tools_must_execute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    venv = _make_complete_venv(repo)
    broken_pytest = venv / "bin" / "pytest"
    broken_pytest.write_text("#!/missing/python\n", encoding="utf-8")
    broken_pytest.chmod(broken_pytest.stat().st_mode | stat.S_IXUSR)

    errors = collect_workspace_errors(repo, policy=policy)

    assert any(".venv/bin/pytest must execute --version" in error for error in errors)


def test_venv_python_version_command_must_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)

    def fake_version_command(path: Path) -> str | None:
        if path.name == "python":
            return f"{path} failed"
        return None

    monkeypatch.setattr(check_samsung_workspace, "_check_version_command", fake_version_command)

    errors = collect_workspace_errors(repo, policy=policy)

    assert any(".venv/bin/python failed" in error for error in errors)


def test_venv_python_symlink_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    venv = _make_complete_venv(repo)
    (venv / "bin" / "python").unlink()
    (venv / "bin" / "python").symlink_to(Path("/usr/bin/python3"))

    errors = collect_workspace_errors(repo, policy=policy)

    assert ".venv/bin/python must be a copied interpreter, not a symlink" in errors


def test_venv_python_must_be_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    venv = _make_complete_venv(repo)
    (venv / "bin" / "python").chmod(stat.S_IRUSR | stat.S_IWUSR)

    errors = collect_workspace_errors(repo, policy=policy)

    assert ".venv/bin/python must be executable" in errors


def test_dependency_tree_root_symlink_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)
    node_modules = repo / "studio-web" / "node_modules"
    external_node_modules = tmp_path / "node_modules"
    external_node_modules.mkdir()
    node_modules.parent.mkdir(parents=True)
    node_modules.symlink_to(external_node_modules, target_is_directory=True)

    errors = collect_workspace_errors(repo, policy=policy)

    assert any("studio-web/node_modules must be a real directory, not a symlink" in error for error in errors)


def test_source_tree_symlink_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)
    external_module = tmp_path / "module.py"
    external_module.write_text("VALUE = 1\n", encoding="utf-8")
    source_package = repo / "src" / "scpn_mif_core"
    source_package.mkdir(parents=True)
    (source_package / "linked.py").symlink_to(external_module)

    errors = collect_workspace_errors(repo, policy=policy)

    assert any("repo symlink: " in error and "src/scpn_mif_core/linked.py" in error for error in errors)


def test_mount_and_repository_location_errors_are_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)
    forbidden = repo.parent
    mismatched_policy = WorkspacePolicy(
        expected_repo_root=repo / "other",
        gotm_root=repo / "not-gotm",
        expected_mount=repo / "wrong-mount",
        forbidden_roots=(forbidden,),
    )

    def wrong_mount_info(path: Path) -> MountInfo:
        del path
        return MountInfo(target=tmp_path / "other-mount", fstype="fuseblk", source="/dev/test")

    monkeypatch.setattr(check_samsung_workspace, "_mount_info", wrong_mount_info)

    errors = collect_workspace_errors(repo, policy=mismatched_policy)

    assert any("repository root must be" in error for error in errors)
    assert any("repository root is outside Samsung GOTM working tree" in error for error in errors)
    assert any("repository root is under forbidden backup/home path" in error for error in errors)
    assert any("repository must be on mount" in error for error in errors)
    assert "Samsung GOTM mount must be ext4, got fuseblk" in errors


def test_git_directory_must_exist_and_not_be_a_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)
    (repo / ".git").rmdir()

    assert any(".git directory is missing" in error for error in collect_workspace_errors(repo, policy=policy))

    git_target = tmp_path / "gitdir"
    git_target.mkdir()
    (repo / ".git").symlink_to(git_target, target_is_directory=True)

    assert any(".git must not be a symlink" in error for error in collect_workspace_errors(repo, policy=policy))


def test_path_component_symlink_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gotm_real = tmp_path / "gotm-real"
    repo = gotm_real / "03_CODE" / "SCPN-MIF-CORE"
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()
    _make_complete_venv(repo)
    gotm_link = tmp_path / "gotm-link"
    gotm_link.symlink_to(gotm_real, target_is_directory=True)
    linked_repo = gotm_link / "03_CODE" / "SCPN-MIF-CORE"
    policy = WorkspacePolicy(
        expected_repo_root=linked_repo,
        gotm_root=gotm_link,
        expected_mount=tmp_path,
        forbidden_roots=(),
    )

    def fake_mount_info(path: Path) -> MountInfo:
        del path
        return MountInfo(target=tmp_path, fstype="ext4", source="/dev/test")

    monkeypatch.setattr(check_samsung_workspace, "_mount_info", fake_mount_info)

    errors = collect_workspace_errors(linked_repo, policy=policy)

    assert any("path-component symlink:" in error and "gotm-link" in error for error in errors)


def test_collect_uses_findmnt_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch, patch_mount=False)
    _make_complete_venv(repo)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if cmd[:2] == ["findmnt", "-T"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{policy.expected_mount} ext4 /dev/test\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="tool ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert collect_workspace_errors(repo, policy=policy) == []


def test_main_reports_findmnt_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="missing mount")

    monkeypatch.delenv("MIF_ALLOW_NON_SAMSUNG", raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert main([]) == 1

    captured = capsys.readouterr()
    assert "workspace locality check failed" in captured.out
    assert "cannot determine mount" in captured.out


def test_collect_reports_nonzero_tool_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="bad tool")

    monkeypatch.setattr(subprocess, "run", fake_run)

    errors = collect_workspace_errors(repo, policy=policy)

    assert any(".venv/bin/python must execute --version: bad tool" in error for error in errors)


def test_collect_reports_tool_version_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, policy = _make_repo(tmp_path, monkeypatch)
    _make_complete_venv(repo)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        raise subprocess.TimeoutExpired(cmd, 10)

    monkeypatch.setattr(subprocess, "run", fake_run)

    errors = collect_workspace_errors(repo, policy=policy)

    assert any(".venv/bin/python must execute --version without timing out" in error for error in errors)


def test_main_honours_non_samsung_escape_hatches(monkeypatch: pytest.MonkeyPatch) -> None:
    assert main(["--allow-non-samsung"]) == 0

    monkeypatch.setenv("MIF_ALLOW_NON_SAMSUNG", "yes")
    assert main([]) == 0


def test_main_reports_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_errors() -> list[str]:
        return ["broken"]

    monkeypatch.delenv("MIF_ALLOW_NON_SAMSUNG", raising=False)
    monkeypatch.setattr(check_samsung_workspace, "collect_workspace_errors", fake_errors)

    assert main([]) == 1

    captured = capsys.readouterr()
    assert "workspace locality check failed" in captured.out
    assert "broken" in captured.out


def test_main_reports_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_errors() -> list[str]:
        return []

    def fake_mount_info(path: Path) -> MountInfo:
        del path
        return MountInfo(target=Path("/media/anulum/GOTM"), fstype="ext4", source="/dev/test")

    monkeypatch.delenv("MIF_ALLOW_NON_SAMSUNG", raising=False)
    monkeypatch.setattr(check_samsung_workspace, "collect_workspace_errors", fake_errors)
    monkeypatch.setattr(check_samsung_workspace, "_mount_info", fake_mount_info)

    assert main([]) == 0

    assert "workspace locality check passed" in capsys.readouterr().out
