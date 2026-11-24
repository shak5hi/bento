"""Plain-language guides for every kind of finding: what's wrong, why it matters, how to fix it.

Written for students, by hand (not generated), so they're accurate and instant. Pickle's AI writer is
given these as its source material, so it explains real fixes instead of inventing them.
"""

from __future__ import annotations

ROTATE = "Treat it as leaked: anyone who saw the repo could have copied it."


def _secret(name: str, revoke: str) -> dict:
    return {
        "what": f"A real {name} is written directly in {{file}}.",
        "why": f"{ROTATE} Bots scan GitHub for keys like this within minutes of a push.",
        "steps": [
            revoke,
            "Delete it from {file} and read it from an environment variable instead (for example os.environ in Python "
            "or process.env in Node).",
            "Put the real value in a .env file that's listed in .gitignore, never in the code.",
            "Deleting it in a new commit doesn't remove it from git history, so always replace the key first.",
        ],
        "learn": "https://docs.github.com/en/code-security/secret-scanning/working-with-secret-scanning-and-push-protection",
    }


SECRETS = {
    "aws-access-key": _secret("AWS access key", "In the AWS console (IAM → Users → Security credentials), deactivate this key and create a new one."),
    "github-token": _secret("GitHub token", "Go to GitHub → Settings → Developer settings → Tokens, delete this token and create a new one."),
    "stripe-live-key": _secret("Stripe live secret key", "In the Stripe dashboard (Developers → API keys), roll the secret key."),
    "stripe-test-key": {
        **_secret("Stripe test key", "In the Stripe dashboard (Developers → API keys, test mode), roll the test key."),
        "why": "Test keys can't move real money, but they still give access to your Stripe test data, and it's the "
               "same habit that leaks live keys.",
    },
    "slack-token": _secret("Slack token", "In your Slack app's settings (OAuth & Permissions), revoke the token and reinstall the app."),
    "slack-webhook": _secret("Slack webhook URL", "In the Slack app settings (Incoming Webhooks), delete this webhook and add a new one."),
    "private-key": {
        "what": "A private key file is committed: {file}.",
        "why": "A private key is like a master password. Anyone with it can pretend to be your server or sign in "
               "as you, and it stays in git history even after you delete it.",
        "steps": [
            "Generate a new key pair and replace the old one wherever it's used (server, SSH, certificates).",
            "Delete {file} from the repo and add the file name (or *.key, *.pem) to .gitignore.",
            "Keep keys outside the project folder, or in your host's secret settings.",
        ],
        "learn": "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository",
    },
    "generic-secret": {
        "what": "A password or API key appears to be typed directly into {file}.",
        "why": f"{ROTATE} Hard-coded secrets also end up in every copy of the code and in git history.",
        "steps": [
            "Change the password or key in the service it belongs to.",
            "Replace it in {file} with a lookup of an environment variable.",
            "Keep the real value in a .env file listed in .gitignore, and add a .env.example with a placeholder.",
        ],
        "learn": "https://12factor.net/config",
    },
}

GUIDES = {
    "secrets-env-file": {
        "what": "A .env file (where apps keep passwords and keys) is committed to the repo.",
        "why": "Everything in it is public to anyone who can see the repo, and it stays in git history even after "
               "you delete it.",
        "steps": [
            "Change every password and key in that file.",
            "Delete the file from the repo, but keep your local copy.",
            "Add .env to .gitignore so it's never committed again.",
            "Commit a .env.example with the same variable names and fake values, so others know what to set.",
        ],
        "learn": "https://12factor.net/config",
    },
    "vuln:npm": {
        "what": "{package} has known security holes in the version you use.",
        "why": "These are published problems, so attackers know exactly what to try. Upgrading is usually all it takes.",
        "steps": [
            "Run npm install {package}@latest, or npm audit fix to upgrade everything with a safe fix.",
            "If another package pulls it in, Bento's fix button adds an npm override for you.",
            "Run your app and tests, then commit package.json and package-lock.json.",
        ],
        "learn": "https://docs.npmjs.com/cli/commands/npm-audit",
    },
    "vuln:PyPI": {
        "what": "{package} has known security holes in the version you use.",
        "why": "These are published problems, so attackers know exactly what to try. Upgrading is usually all it takes.",
        "steps": [
            "In requirements.txt, change {package} to a fixed version (Bento's fix button picks the right one).",
            "Run pip install -r requirements.txt.",
            "Run your app and tests, then commit requirements.txt.",
        ],
        "learn": "https://osv.dev",
    },
    "outdated": {
        "what": "Some libraries you use are a whole major version behind the latest release.",
        "why": "Old versions stop getting security fixes, and the longer you wait, the bigger the jump gets.",
        "steps": [
            "Upgrade one library at a time, starting with the ones furthest behind.",
            "Read its changelog for breaking changes (major versions can change how things work).",
            "Run the app and tests after each upgrade before moving to the next.",
        ],
        "learn": "https://semver.org",
    },
    "docker:secret-env": {
        "what": "A password or key is set with ENV or ARG in {file}.",
        "why": "Anything set this way is saved inside the Docker image, so everyone who can pull the image can read it.",
        "steps": [
            "Change the password or key.",
            "Remove it from {file} and pass it when the container starts (docker run -e, or environment: in compose).",
            "For values needed during the build, use a BuildKit secret mount.",
        ],
        "learn": "https://docs.docker.com/build/building/secrets/",
    },
    "docker:unpinned-base": {
        "what": "{file} builds on an image without a fixed version (like :latest).",
        "why": "The image can change under you, so a build that worked yesterday can break today for no visible reason.",
        "steps": ["Pick the version you use now and write it explicitly, for example node:22-alpine or python:3.12-slim.",
                  "Update it on purpose when you want a newer one."],
        "learn": "https://docs.docker.com/build/building/best-practices/#pin-base-image-versions",
    },
    "docker:runs-as-root": {
        "what": "The container in {file} runs as the all-powerful root user.",
        "why": "If someone breaks into your app, they get full control of the container instead of a limited account.",
        "steps": ["Add a normal user near the end of {file}, for example: RUN useradd -m app",
                  "Switch to it with: USER app",
                  "Rebuild and check the app can still read and write the folders it needs."],
        "learn": "https://docs.docker.com/build/building/best-practices/#user",
    },
    "docker:add-instead-of-copy": {
        "what": "{file} uses ADD where COPY would do.",
        "why": "ADD can also download URLs and unpack archives, which can surprise you. COPY only copies files.",
        "steps": ["Replace ADD with COPY on those lines (keep ADD only for remote URLs or archives you want unpacked)."],
        "learn": "https://docs.docker.com/build/building/best-practices/#add-or-copy",
    },
    "docker:no-healthcheck": {
        "what": "{file} has no HEALTHCHECK.",
        "why": "Without one, Docker can't tell a frozen app from a working one, so it won't restart it.",
        "steps": ["Add a line that checks a cheap page, for example: HEALTHCHECK CMD wget -qO- http://localhost:3000/ || exit 1",
                  "Use your app's real port and a page that loads quickly."],
        "learn": "https://docs.docker.com/reference/dockerfile/#healthcheck",
    },
    "no-tests": {
        "what": "The project has code but no automated tests.",
        "why": "Tests catch mistakes before your users do, and let you change code without being scared of breaking it.",
        "steps": ["Pick the most important thing your app does.",
                  "Write one small test for it (Jest/Vitest for JavaScript, pytest for Python).",
                  "Run it on every push with a CI pipeline."],
        "learn": "https://docs.pytest.org/en/stable/getting-started.html",
    },
    "no-ci": {
        "what": "Nothing builds or tests the project automatically when you push.",
        "why": "CI catches broken builds and failing tests the moment they happen, instead of when someone tries to run it.",
        "steps": ["Add a GitHub Actions workflow in .github/workflows/ that installs, builds and tests the project.",
                  "Bento can open a pull request with a ready-made workflow for you."],
        "learn": "https://docs.github.com/en/actions/get-started/quickstart",
    },
    "no-readme": {
        "what": "The repo has no README.",
        "why": "It's the first thing people see. Without one, nobody (including future you) knows what it is or how to run it.",
        "steps": ["Add README.md with: what the project does, how to install and run it, and a screenshot if it has a UI.",
                  "Bento can open a pull request with a starter README for you."],
        "learn": "https://www.makeareadme.com",
    },
    "no-lockfile": {
        "what": "package.json has no lockfile.",
        "why": "Every install can pull slightly different versions, so it may work on your laptop and break somewhere else.",
        "steps": ["Run npm install once; it creates package-lock.json.",
                  "Commit package-lock.json, and use npm ci in CI."],
        "learn": "https://docs.npmjs.com/cli/configuring-npm/package-lock-json",
    },
}


def guide_for(key: str) -> dict | None:
    """The guide for a finding key, with its file or package filled in."""
    parts = key.split(":")
    params: dict[str, str] = {}
    if parts[0] == "secret" and len(parts) >= 3:
        base, params["file"] = SECRETS.get(parts[1]), ":".join(parts[2:])
    elif parts[0] == "vuln" and len(parts) >= 3:
        base, params["package"] = GUIDES.get(f"vuln:{parts[1]}"), ":".join(parts[2:])
    elif parts[0] == "outdated":
        base = GUIDES["outdated"]
    elif parts[0] == "docker" and len(parts) >= 3:
        base, params["file"] = GUIDES.get(f"docker:{parts[1]}"), ":".join(parts[2:])
    else:
        base = GUIDES.get(key)
    if base is None:
        return None

    def fill(text: str) -> str:
        for k, v in params.items():
            text = text.replace("{" + k + "}", v)
        return text

    return {"what": fill(base["what"]), "why": fill(base["why"]), "steps": [fill(s) for s in base["steps"]],
            "learn": base["learn"]}
