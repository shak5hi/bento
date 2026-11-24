"""Auto-fix generators and the branch guard (no GitHub calls)."""

import json

import httpx
import pytest

import fixes
from gh import FixError, Repo


def test_branch_names_are_namespaced():
    assert fixes.branch_for("vuln:npm:@babel/traverse") == "bento/fix-vuln-npm-babel-traverse"
    assert fixes.branch_for("no-ci").startswith("bento/")


async def test_refuses_to_write_outside_bento_branches():
    repo = Repo("o/r", 1, httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    for branch in ("main", "master", "refs/heads/main", "feature/x"):
        with pytest.raises(FixError, match="bento/"):
            await repo.commit_to_new_branch(branch, "sha", "msg", {"a": "b"})


@pytest.mark.parametrize(
    ("files", "lang"),
    [(["package.json"], "node"), (["requirements.txt"], "python"), (["pyproject.toml"], "python"),
     (["go.mod"], "go"), (["Cargo.toml"], "rust"), (["pom.xml"], "java"), (["index.html"], "other")],
)
def test_detect_language(files, lang):
    assert fixes.detect_language(files) == lang


def test_node_ci_workflow_uses_lockfile_and_scripts():
    pkg = json.dumps({"scripts": {"test": "vitest", "build": "vite build", "lint": "eslint ."}})
    fix = fixes.fix_no_ci(["package.json", "package-lock.json"], pkg)
    wf = fix.changes[".github/workflows/ci.yml"]
    assert "npm ci" in wf and "npm run test" in wf and "npm run build" in wf and "npm run lint" in wf


def test_default_npm_test_script_is_skipped():
    pkg = json.dumps({"scripts": {"test": 'echo "Error: no test specified" && exit 1'}})
    wf = fixes.fix_no_ci(["package.json"], pkg).changes[".github/workflows/ci.yml"]
    assert "npm install" in wf and "run test" not in wf


def test_existing_ci_file_is_not_overwritten():
    fix = fixes.fix_no_ci(["requirements.txt", ".github/workflows/ci.yml"], None)
    assert list(fix.changes) == [".github/workflows/bento-ci.yml"]


def test_python_workflow_runs_pytest_only_with_tests():
    assert "pytest" in fixes.fix_no_ci(["requirements.txt", "tests/test_a.py"], None).changes[".github/workflows/ci.yml"]
    assert "compileall" in fixes.fix_no_ci(["requirements.txt", "app.py"], None).changes[".github/workflows/ci.yml"]


def test_readme_uses_repo_metadata():
    fix = fixes.fix_no_readme(["package.json"], {"name": "demo", "description": "Does things", "homepage": "https://demo.dev"})
    text = fix.changes["README.md"]
    assert text.startswith("# demo\n") and "Does things" in text and "https://demo.dev" in text and "npm install" in text


def test_env_fix_deletes_files_and_updates_gitignore():
    fix = fixes.fix_env_file([".env", "api/.env.local", ".env.example", "a.py"], "node_modules\n.env\n")
    assert fix.changes[".env"] is None and fix.changes["api/.env.local"] is None
    assert ".env.example" not in fix.changes
    gitignore = fix.changes[".gitignore"]
    assert gitignore.startswith("node_modules\n.env\n") and gitignore.count("\n.env\n") == 1 and ".env.*" in gitignore
    assert "Rotate" in fix.body


def test_env_fix_when_already_gone():
    with pytest.raises(FixError):
        fixes.fix_env_file(["README.md"], None)


def test_bump_package_json_keeps_formatting_and_prefix():
    text = '{\n    "dependencies": {\n        "lodash": "^4.17.15",\n        "lodash-es": "^4.17.15"\n    }\n}\n'
    out, transitive = fixes.bump_package_json(text, "lodash", "4.17.21")
    assert out == text.replace('"lodash": "^4.17.15"', '"lodash": "^4.17.21"') and transitive is False


def test_transitive_dependency_gets_an_npm_override():
    text = '{\n    "name": "app",\n    "dependencies": {\n        "express": "^4"\n    }\n}\n'
    out, transitive = fixes.bump_package_json(text, "browserslist", "4.28.2")
    assert transitive is True
    assert json.loads(out)["overrides"] == {"browserslist": "^4.28.2"}
    assert json.loads(out)["dependencies"] == {"express": "^4"}
    assert out.endswith("}\n") and '\n    "overrides": {' in out  # keeps the file's 4-space indent


def test_existing_overrides_are_kept():
    text = '{"dependencies": {}, "overrides": {"semver": "^7.5.2"}}'
    out, _ = fixes.bump_package_json(text, "qs", "6.10.3")
    assert json.loads(out)["overrides"] == {"semver": "^7.5.2", "qs": "^6.10.3"}


def test_odd_overrides_field_is_left_to_a_human():
    with pytest.raises(FixError, match="overrides"):
        fixes.bump_package_json('{"overrides": "nope"}', "qs", "6.10.3")


def test_bump_requirements_keeps_extras_and_comments():
    text = "Flask==1.0\r\nrequests[socks]==2.19.0  # http\nrequests-oauthlib==1.0\n"
    out, changed = fixes.bump_requirements(text, "Requests", "2.32.0")
    assert changed
    assert out == "Flask==1.0\r\nrequests[socks]==2.32.0  # http\nrequests-oauthlib==1.0\n"


async def test_fixed_version_picks_the_lowest_release_fixing_everything():
    osv = {"vulns": [
        {"id": "A", "affected": [{"package": {"ecosystem": "npm", "name": "lodash"},
                                  "ranges": [{"events": [{"introduced": "0"}, {"fixed": "4.17.19"}]}]}]},
        {"id": "B", "affected": [{"package": {"ecosystem": "npm", "name": "lodash"},
                                  "ranges": [{"events": [{"introduced": "0"}, {"fixed": "4.17.21"}]},
                                             {"events": [{"introduced": "5.0.0"}, {"fixed": "5.0.1"}]}]}]},
        {"id": "C", "affected": [{"package": {"ecosystem": "npm", "name": "lodash"}, "ranges": [{"events": [{"introduced": "0"}]}]}]},
    ]}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=osv))) as http:
        fixed, unfixed = await fixes.fixed_version("npm", "lodash", "4.17.15", http)
    assert fixed == "4.17.21" and unfixed == ["C"]
