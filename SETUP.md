# Setup — Do This Once

I can't create the repo on GitHub for you (no access to your account/credentials).
Here is the exact sequence to run yourself. Should take under 5 minutes.

## 1. Create the repo on GitHub

Go to https://github.com/new and create:
- Owner: **alirezakkt**
- Repository name: `nds-bot` (or whatever you prefer — update commands below if different)
- Visibility: **Public** — anyone can see it, fork it, and open PRs.
  Branch protection + required reviews (step 4) mean nothing merges without
  your approval regardless of who opens the PR.
- Do NOT initialize with a README/gitignore/license — this package already
  has a README.

## 2. Push this package

From the folder you unzipped this into:

```bash
cd nds_project_starter
git init
git add .
git commit -m "chore: initial spec, roadmap, and contribution guidelines"
git branch -M main
git remote add origin https://github.com/alirezakkt/nds-bot.git
git push -u origin main
```

## 3. Create the `develop` branch

This is the branch contributors will actually target with PRs (see
`CONTRIBUTING.md`).

```bash
git checkout -b develop
git push -u origin develop
```

## 4. Protect both branches

On GitHub: **Settings → Branches → Add branch protection rule**

For both `main` and `develop`:
- ✅ Require a pull request before merging
- ✅ Require approvals (1) — this is what forces every PR through you,
  including PRs from forks by people who aren't collaborators
- ✅ Require status checks to pass before merging (once CI is green at
  least once, select the `lint-and-test` check)
- ✅ Do not allow bypassing the above settings (applies rule to you too —
  recommended so you never accidentally push straight to main)

Because the repo is public, external contributors can fork and open PRs
without needing "Write" access at all — branch protection is what keeps you
in control, not who has been invited.

## 5. Turn on the CI workflow

`.github/workflows/ci.yml` is already included, and will run automatically
on PRs — **including PRs from forks** (GitHub Actions runs CI on
fork-originated PRs by default for public repos, with some permission
restrictions on secrets, which don't matter here since this workflow
doesn't use any). It expects a `requirements.txt`/`requirements-dev.txt`
and a `tests/` folder — these don't exist yet, so the very first PR (M0,
repo scaffolding) should add them. Until then, CI will simply report "no
tests collected," which is fine.

## 6. Create a Project Board

**Projects tab → New project → Board**. Columns: `Backlog`, `Ready`,
`In Progress`, `In Review`, `Done`. Go through `docs/ROADMAP.md` and create
one GitHub Issue per checklist item (use the "Module Task" issue template),
add each to the board in `Backlog`, and move the M0 items into `Ready`
first — don't open the whole roadmap at once, or contributors won't know
where to start.

Public projects/boards are visible to everyone by default, which is fine
here — it doubles as a public roadmap announcement.

## 7. Announce it

Since the repo is public, there's no invite step — anyone with a GitHub
account can fork and contribute. Post the repo link wherever your students
are (Telegram, Discord, etc.) along with one line: *"Read README.md first,
then CONTRIBUTING.md — issues tagged `good-first-issue` are the place to
start."*

If you later want a smaller trusted group to have **Write** access (so they
can push branches directly to the main repo instead of forking, and get
issues assigned to them instead of self-claiming), you can still add
specific people as Collaborators — `Settings → Collaborators → Add people`.
This is optional and orthogonal to the public/fork model; most contributors
don't need it.

## 8. Point them at the entry doc

`README.md` tells contributors to read the spec, then `CONTRIBUTING.md`
(which now includes the fork-based workflow), then check the Project Board.
You shouldn't need to explain the workflow individually; that's what these
docs are for.

---

Once this is done, your ongoing job is: review PRs against the checklist
in `CONTRIBUTING.md`, keep `docs/NDS_SPEC.md` as the single source of
truth, and move milestone items from `Backlog` to `Ready` as earlier
milestones complete.
