"""The `bento` CLI, run in-process against temporary folders (offline unless a test mocks the network)."""

import json
import subprocess

import pytest

from bento_cli import main as cli

FAKE_GH = "ghp_" + "Zx9" * 12


def run(capsys, *args):
    code = cli.main(list(args))
    out = capsys.readouterr().out
    return code, out


@pytest.fixture
def clean_repo(tmp_path):
    (tmp_path / "README.md").write_text("# demo\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    return tmp_path


@pytest.fixture
def leaky_repo(tmp_path):
    (tmp_path / "app.py").write_text(f'TOKEN = "{FAKE_GH}"\n')
    return tmp_path


def test_clean_folder_passes(capsys, clean_repo):
    code, out = run(capsys, "scan", str(clean_repo), "--offline")
    assert code == 0
    assert "Nothing to fix" in out and "PASS" in out


def test_critical_finding_fails_by_default(capsys, leaky_repo):
    code, out = run(capsys, "scan", str(leaky_repo), "--offline")
    assert code == 1
    assert "CRITICAL" in out and "FAIL" in out
    assert FAKE_GH not in out


@pytest.mark.parametrize(("fail_on", "code"), [("critical", 1), ("high", 1), ("low", 1), ("never", 0)])
def test_fail_on_threshold(capsys, leaky_repo, fail_on, code):
    assert run(capsys, "scan", str(leaky_repo), "--offline", "--fail-on", fail_on)[0] == code


def test_low_findings_only_fail_at_low(capsys, tmp_path):
    (tmp_path / "x.txt").write_text("hi\n")  # no README -> low
    assert run(capsys, "scan", str(tmp_path), "--offline")[0] == 0
    assert run(capsys, "scan", str(tmp_path), "--offline", "--fail-on", "low")[0] == 1


def test_json_report(capsys, leaky_repo):
    code, out = run(capsys, "scan", str(leaky_repo), "--offline", "--json")
    report = json.loads(out)
    assert code == 1
    assert report["failed"] is True and report["failOn"] == "high" and report["offline"] is True
    assert report["summary"]["critical"] == 1
    assert {"key", "severity", "title", "detail", "effortMinutes"} <= set(report["findings"][0])
    assert FAKE_GH not in out


def test_missing_folder_is_a_usage_error(capsys, tmp_path):
    assert cli.main(["scan", str(tmp_path / "nope")]) == 2


def test_bad_option_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main(["scan", str(tmp_path), "--fail-on", "sometimes"])
    assert exc.value.code == 2


def test_git_ignored_files_are_not_scanned(capsys, tmp_path):
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".env\nsecrets/\n")
    (tmp_path / ".env").write_text("LOCAL=1\n")
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "app.py").write_text(f'T = "{FAKE_GH}"\n')
    (tmp_path / "new.py").write_text("print('untracked but not ignored')\n")
    files = cli.tracked_files(tmp_path)
    assert sorted(files) == [".gitignore", "new.py"]
    report = json.loads(run(capsys, "scan", str(tmp_path), "--offline", "--json")[1])
    assert "secrets-env-file" not in {f["key"] for f in report["findings"]}


def test_non_git_folder_falls_back_to_walking(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "b.js").write_text("")
    assert cli.tracked_files(tmp_path) is None
    assert cli.list_files(tmp_path) == ["a.py"]
