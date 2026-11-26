# Bento, explained simply

This guide explains everything Bento does, in plain words. You don't need to know anything about
programming to read it. Every technical word is explained the first time it shows up, and there's a
word list at the end.

**Try it:** https://bento.104-43-56-1.sslip.io

---

## Part 1: The words you need first

Before we talk about Bento, here are the ideas it works with. Read these once and everything else will
make sense.

**Code.** The written instructions that make a website or app work. It's just text files, like a very
strict recipe the computer follows.

**Project.** One thing someone is building: a portfolio website, a college app, a hackathon idea.

**GitHub.** A website where people keep their code online. Think of it as Google Drive, but made for code.

**Repository (or "repo").** One project's folder on GitHub. If you build three apps, you have three repos.

**Commit and push.** When you change your code and save a snapshot of it, that's a *commit*. Sending
those snapshots up to GitHub is a *push*. "I pushed my code" means "I uploaded my latest changes".

**Branch.** A separate copy of the code where you can try changes without touching the main version.
Like duplicating a Google Doc to try a new idea, so the original stays safe.

**Pull request (or "PR").** A request that says: "I made some changes on my branch. Please look at
them, and if they're good, add them to the main version." Someone reviews it, and if they're happy they
press **Merge**, which copies the changes into the main code. Nothing changes until someone merges.

**Library (or "dependency" or "package").** Code written by other people that your project borrows,
so you don't have to write everything yourself. A normal website borrows dozens or hundreds of them.

**Vulnerability (a "security hole").** A known mistake in a library that bad people can use to break
in. When one is found, the library's authors release a fixed version, and everyone using it should
update.

**Secret.** A password or key that lets a program use a paid or private service, like the key to your
payment account. Secrets must never be written inside code that others can see.

**Live site.** The real website people visit, like `myportfolio.com`.

**Server.** A computer somewhere in a data centre that is always on and runs a website for everyone.

---

## Part 2: What Bento is

Most students build several things: a portfolio, a group project, a hackathon app, something for a
club. Each one can quietly break or get unsafe:

- the website goes down and nobody notices,
- a library it uses gets a security hole,
- someone accidentally puts a password inside the code,
- it's missing basic things like instructions or tests.

Checking all of that by hand, for every project, every day, is boring, so nobody does it.

**Bento does it for you.** You connect your projects once. Bento keeps watching them and tells you, in
plain words, the few things that actually matter today.

The name comes from a Japanese lunchbox (a *bento*) with separate compartments. Each of your projects
gets its own compartment, and you see all of them neatly in one place.

---

## Part 3: Using Bento, step by step

1. **Open the site** and click **Get started**.
2. **Sign in.** Either click **Continue with GitHub** (easiest), or make an account with your email and
   a password.
3. **Add your projects.** Click **New project**, then **From GitHub**. GitHub asks which repos Bento
   may look at. You choose them, and you can choose only some.
4. **Wait a minute.** Bento reads your code and checks your live site.
5. **Look at your dashboard.** Each project gets a score out of 100 and a letter grade (A to F), and
   Pickle, Bento's assistant, lists the top things to fix.
6. **Check your email.** A few minutes after your projects are checked, Bento emails you your first
   report.

---

## Part 4: Every feature, explained

### 4.1 Signing in

You can sign in two ways:

- **With GitHub.** You click one button, GitHub asks "Do you allow Bento to know who you are?", you say
  yes, and you're in. Bento never sees your GitHub password.
- **With email and password.** Your password is stored scrambled (it's *hashed*), so even Bento can't
  read it back.

After you sign in, your browser keeps a small signed note, like a wristband at an event, so you don't
have to log in on every page. It runs out after a week.

### 4.2 Connecting GitHub, and keeping it private

To read your code, Bento uses a **GitHub App**. That's an official way for a service to ask GitHub for
access. When you install it, GitHub shows you exactly what Bento can do and lets you pick which repos it
may see. You can remove access any time from your GitHub settings.

**Privacy rule:** you only ever see repos you can open yourself on GitHub. If a friend collaborates on
one of your repos, they see that one repo, never your other private ones.

### 4.3 Checking your code ("scanning")

Every time you push new code, GitHub tells Bento, and Bento reads the code again. It runs in a sealed-off
area (a *sandbox*) and **never runs your code**. It only reads it, like proof-reading a recipe without
cooking it. It looks for:

| What it looks for | In simple words |
|---|---|
| **Secrets in the code** | A password or key written inside a file (AWS, GitHub, Stripe, Slack keys, private keys), or a `.env` file (a settings file full of passwords) uploaded by mistake. Bento only notes *where* it is. It never saves the secret itself. |
| **Libraries with security holes** | Compares every library you use against a public list of known security holes ([OSV](https://osv.dev)) and says how serious each one is. |
| **Very old libraries** | Libraries several big versions behind, which get harder to update the longer you wait. |
| **Docker settings** | Docker packs an app into a box so it runs the same everywhere. Bento checks the box isn't set up unsafely, for example running with full admin powers. |
| **The basics** | Does the project have a README (instructions), tests, automatic checks (CI), and a lockfile (a list that pins exact library versions)? |

Every problem is written in everyday language, like *"A library you use has known security holes"*, with
a short guide: what it is, why it matters, and the steps to fix it. If you want the technical version,
you can still open it.

### 4.4 Watching your live site ("probing")

If your project has a website, Bento visits it **every minute**, like a friend who keeps refreshing your
page to make sure it's still up.

It learns what's normal for your site: how fast it usually loads and how often it usually fails. If
your site starts failing or gets much slower than normal **3 times in a row**, Bento opens an
**incident** (a "something's wrong right now" alert) and tells you. When the site recovers, Bento closes
the incident and tells you that too.

Bento refuses to visit private or internal addresses, so nobody can use it to poke around inside a
network.

### 4.5 The report card and score

Each project gets a report card with four subjects:

| Subject | Counts for | What it measures |
|---|---|---|
| **Security** | 35% | Secrets in code, libraries with security holes, unsafe Docker settings |
| **Website** | 30% | Is the site up, fast and not failing? |
| **Basics** | 20% | README, tests, automatic checks, lockfile |
| **Upkeep** | 15% | Are the libraries reasonably up to date? |

These combine into **one score out of 100** and a **grade from A to F**. Two fairness rules:

- **Safety first.** If Security is an F, the whole project can't score above 49. If Security is a D, it
  can't go above 69. A pretty website doesn't make up for a leaked password.
- **No free marks.** If something can't be measured (say, the project has no website), that subject is
  left out instead of counted as perfect, and Bento says so.

Every project also shows **the one fix that would raise its score the most**, and a little history of
how its score has changed and why.

Your **portfolio health** is the average across all your projects.

### 4.6 Pickle, your assistant

Pickle is the friendly helper on the dashboard. It looks at everything Bento found and picks **the 3
things you should do first**, so you're not drowning in 50 alerts.

- **Rules decide** what's most important. Fixed rules, so the order always makes sense: a site that's
  down right now beats a missing README.
- **A small AI model explains it** in friendly, simple words with steps to fix. The AI runs *on Bento's
  own computer*, not on an outside AI service, so your code never leaves Bento. If the AI isn't
  available, Pickle uses its ready-written explanations instead, so it always works.

### 4.7 "Fix it for me" (automatic fix pull requests)

For some problems, Bento can make the fix for you. Click **Fix it**, and Bento:

1. makes a new branch (a safe copy) in your repo, called `bento/fix-...`,
2. puts the fix on that branch,
3. opens a **pull request**, a note saying "here's a suggested change, please review it".

**Bento never changes your main code by itself.** You read the change and press **Merge** only if you
like it. After you merge, Bento's next check sees the problem is gone and marks it fixed.

What it can fix:

- **Library with a security hole:** updates it to the nearest safe version, even when it's a library
  borrowed by another library.
- **No automatic checks (CI):** adds a ready-made checking setup that suits your project's language.
- **No README:** writes a starter README with how to install and run the project.
- **A `.env` file uploaded by mistake:** removes it from the repo and adds it to the ignore list so it
  doesn't happen again. You should still change those passwords, because they were public.

### 4.8 Checks on pull requests

When anyone opens a pull request on a connected repo, Bento checks just that change and puts a ✅ or ❌
on it right inside GitHub. For example, if the change adds a password into the code, the PR gets a ❌ and
an explanation, **before** it gets merged.

### 4.9 Public status page and badge

- **Status page.** A public page (`/status/your-project`) that anyone can open to see if your site is
  up, like the "all systems working" pages big companies have. Only you can turn it on. It shows uptime
  and health, never your code or problems.
- **Badge.** A little label, `bento health | 94`, that you can put on your GitHub README so visitors see
  your project is looked after.

### 4.10 Emails

Bento sends three kinds of email, always to **the person's own email address** (the one they signed up
with, or their main email on GitHub):

1. **Welcome report.** As soon as a new person's projects have been checked, they get their first
   report: their score, the grade of each project, Pickle's top 3, and what Bento found. Sent once.
2. **"Your site is down" alerts.** When an incident opens, and again when it's fixed. Only one email per
   problem, not one every minute.
3. **Monday summary.** Every Monday morning: how your scores changed this week, what's new, what got
   fixed, and Pickle's top 3.

Every email has an **Unsubscribe** link that works in one click, and you can switch each type on or off
in Bento's settings. The emails are sent through a free Gmail account.

### 4.11 The `bento` command-line tool and GitHub Action

For people comfortable typing commands, the same code checks can run **on your own computer**:

```bash
pip install ./cli
bento scan .
```

It prints the problems it finds. It can also run automatically on GitHub every time code is pushed
(that's the **GitHub Action**), and fail the run if something serious is found.

### 4.12 The website itself

- **Landing page.** A 3D bento box made in Blender (a free 3D design program). As you scroll, the lid
  lifts off and the food compartments settle into place, and each compartment explains a part of Bento.
- **Login page.** The same 3D box, with its lid half open, next to the sign-in form.
- **Dashboard.** Your home inside Bento. It shows your portfolio health, what changed this week, Pickle's
  top 3, what's happening right now, your websites and the problems in your code. Click a project to see
  its full report card.

### 4.13 Tests (how we know Bento works)

Bento comes with over 340 automatic tests: small programs that check Bento behaves correctly. One makes
sure a friend can't see your private repos. Another makes sure an email goes out only once. They run
automatically on GitHub every time code changes (that's **CI**, continuous integration). If anything
breaks, the ❌ shows up before it can reach the real site. While they were being written, the tests
caught three real bugs, which were fixed.

---

## Part 5: How it's built (the kitchen)

Imagine Bento is a restaurant kitchen. Instead of one chef doing everything, there's a team, each with
one job, passing order slips to each other.

| Kitchen job | Real name | What it does |
|---|---|---|
| Front door | **Caddy** | The only door open to the internet. Makes the connection secure (the 🔒 in your browser) and sends people inside. |
| Waiter | **Frontend** (React) | The pages you see and click. |
| Head waiter | **API gateway** (FastAPI) | Takes every request, checks who you are, reads and writes the records, and hands jobs to the kitchen. |
| Order rail | **Redis Streams** | Where job slips wait in line. If a cook drops a slip (crashes), another picks it up 30 seconds later, so no job gets lost. |
| Code checker | **Scanner** | Reads your code and writes down the problems. |
| Site visitor | **Scheduler + Probers** | The scheduler decides when each site is due for a visit. The probers do the visits, several at once. |
| Pattern spotter | **Analyzer** | Learns what's normal for each site, opens incidents, and works out scores. |
| Assistant | **Advisor (Pickle)** | Picks the top 3 and explains them, with the local AI model. |
| Fixer | **Fixer** | Makes the "fix it for me" pull requests. |
| Messenger | **Notifier** | Sends notifications and emails. |
| Filing cabinets | **Postgres + TimescaleDB** | Postgres keeps the records (users, projects, problems, scores). TimescaleDB keeps the site visit results over time, for the speed and uptime charts. |
| Safe | **Backup** | Copies both filing cabinets every day and keeps the last 7 days. |

Each job runs in its own **container**. Think of it as a sealed lunchbox with exactly what that one
program needs inside. **Docker Compose** is the list that starts all 14 boxes together with one command.

To see this animated, open [`system-design.html`](system-design.html) in your browser.

### Where it runs

Bento runs on one **Microsoft Azure** server (rented with free student credits) in Southeast Asia. It's
reachable at **https://bento.104-43-56-1.sslip.io**. `sslip.io` is a free service that turns the
server's number address (`104.43.56.1`) into a name, so we didn't have to buy a domain. Caddy gets a free
security certificate for it automatically, which is why the address starts with `https`.

---

## Part 6: Safety promises

- Bento **never runs your code**. It only reads it.
- Bento **never stores secret values** it finds, only where they are.
- Bento **never changes your main code**. Fixes are suggestions you approve.
- You only see **repos you can open yourself**.
- Your code **is never sent to an outside AI service**.
- Passwords are stored scrambled, and every message from GitHub is checked to be really from GitHub
  (it's *signed*).
- Only the front door (Caddy) is open to the internet. The databases and workers can't be reached
  from outside.

---

## Part 7: What we built, in order

1. **The base:** website watching, code checking, the health score and Pickle.
2. **Connect GitHub:** sign in with GitHub, import repos (private too), check on every push.
3. **Public status page and badge.**
4. **Smarter scanning:** secrets in code, old libraries, Docker settings.
5. **Fix it for me:** automatic fix pull requests.
6. **The `bento` command-line tool and GitHub Action.**
7. **Tests and CI:** 340+ automatic tests. They found and fixed 3 real bugs.
8. **A fairer report card:** four subjects, safety caps, no free marks, "the one fix that helps most".
9. **Pull request checks:** ✅/❌ on every pull request.
10. **Emails:** incident alerts and the Monday summary, with one-click unsubscribe.
11. **Pickle got a brain:** a small AI model running on Bento's own computer, plus step-by-step guides.
12. **Plain words everywhere:** every problem rewritten so a student understands it.
13. **Going live:** put on an Azure server with HTTPS, daily backups and a free address.
14. **Privacy fix:** friends only see their own repos. Also a fix for installing from GitHub's page.
15. **Welcome report email, Gmail sending and the new login page.**

---

## Word list

| Word | Meaning |
|---|---|
| API | A way for programs to talk to each other: one asks, the other answers. |
| Branch | A safe copy of the code to try changes on. |
| CI | Automatic checks that run every time code changes. |
| Commit / push | Saving a snapshot of your code / uploading it to GitHub. |
| Container | A sealed box holding one program and everything it needs. |
| Database | An organised filing cabinet for information. |
| Dependency / library / package | Code borrowed from other people. |
| Deploy | Putting the app on a server so everyone can use it. |
| HTTPS | A secure, private connection to a website (the 🔒). |
| Incident | "Something's wrong with your site right now." |
| Merge | Accepting a pull request's changes into the main code. |
| Pull request (PR) | "Here are my changes, please review and accept them." |
| Repository (repo) | One project's folder on GitHub. |
| Sandbox | A sealed-off area where nothing can escape or cause harm. |
| Secret | A password or key that must stay private. |
| Server | An always-on computer that runs a website for everyone. |
| Vulnerability | A known security hole in some code. |
| Webhook | GitHub tapping Bento on the shoulder: "something just happened in this repo". |
