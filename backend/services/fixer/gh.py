"""Thin GitHub REST helpers for the fixer, always acting as the Bento app installation.

Safety rule enforced here, not just by convention: the only ref Bento ever creates or moves is a
`bento/...` branch. Nothing in this module can write to the default branch.
"""

import base64

import httpx

from bento_core import github

API = github.API
BRANCH_PREFIX = "bento/"


class FixError(Exception):
    """A fix that can't be made; the message is shown to the user."""


class Repo:
    def __init__(self, full_name: str, installation_id: int, http: httpx.AsyncClient):
        self.full_name, self.installation_id, self.http = full_name, installation_id, http

    async def _req(self, method: str, path: str, ok=(200, 201), **kw):
        headers = await github.as_installation(self.installation_id, self.http)
        res = await self.http.request(method, f"{API}/repos/{self.full_name}{path}", headers=headers, timeout=20, **kw)
        if res.status_code not in ok:
            msg = ""
            try:
                msg = res.json().get("message", "")
            except ValueError:
                pass
            raise FixError(f"GitHub {method} {path.split('?')[0]} failed ({res.status_code}{': ' + msg if msg else ''})")
        return res

    async def info(self) -> dict:
        return (await self._req("GET", "")).json()

    async def head(self, branch: str) -> str:
        return (await self._req("GET", f"/git/ref/heads/{branch}")).json()["object"]["sha"]

    async def tree(self, sha: str) -> list[str]:
        data = (await self._req("GET", f"/git/trees/{sha}?recursive=1")).json()
        return [e["path"] for e in data.get("tree", []) if e.get("type") == "blob"]

    async def read(self, path: str, ref: str) -> str | None:
        """Text of a file at ref, or None if it doesn't exist. Never used on secret files."""
        res = await self._req("GET", f"/contents/{path}?ref={ref}", ok=(200, 404))
        if res.status_code == 404:
            return None
        data = res.json()
        if isinstance(data, list) or data.get("type") != "file":
            return None
        if data.get("encoding") == "base64" and data.get("content"):
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        # files over 1 MB come back without content: fetch the blob instead
        blob = (await self._req("GET", f"/git/blobs/{data['sha']}")).json()
        return base64.b64decode(blob["content"]).decode("utf-8", errors="replace")

    async def branch_exists(self, branch: str) -> bool:
        res = await self._req("GET", f"/git/ref/heads/{branch}", ok=(200, 404))
        return res.status_code == 200

    async def commit_to_new_branch(self, branch: str, base_sha: str, message: str, changes: dict[str, str | None]) -> str:
        """One commit on a new `bento/` branch. changes maps path -> new text, or None to delete."""
        if not branch.startswith(BRANCH_PREFIX):
            raise FixError("refusing to write outside a bento/ branch")
        base_tree = (await self._req("GET", f"/git/commits/{base_sha}")).json()["tree"]["sha"]
        entries = []
        for path, text in changes.items():
            if text is None:
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            else:
                entries.append({"path": path, "mode": "100644", "type": "blob", "content": text})
        tree = (await self._req("POST", "/git/trees", json={"base_tree": base_tree, "tree": entries})).json()["sha"]
        commit = (await self._req(
            "POST", "/git/commits", json={"message": message, "tree": tree, "parents": [base_sha]}
        )).json()["sha"]
        # create (never update) the ref: an existing branch makes this fail instead of being overwritten
        await self._req("POST", "/git/refs", json={"ref": f"refs/heads/{branch}", "sha": commit})
        return commit

    async def open_pr(self, branch: str, base: str, title: str, body: str) -> dict:
        return (await self._req(
            "POST", "/pulls", json={"title": title, "head": branch, "base": base, "body": body, "maintainer_can_modify": True}
        )).json()

    async def pr_for_branch(self, branch: str) -> dict | None:
        owner = self.full_name.split("/")[0]
        prs = (await self._req("GET", f"/pulls?state=open&head={owner}:{branch}")).json()
        return prs[0] if prs else None
