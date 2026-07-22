# Contributing

## How to Join (no invite needed)

This repo is public. You don't need to ask for access — fork it and go:

```bash
# 1. Fork via the GitHub web UI (button top-right of the repo page)

# 2. Clone YOUR fork (not the original repo)
git clone https://github.com/<your-username>/nds-bot.git
cd nds-bot

# 3. Add the original repo as "upstream" so you can pull updates later
git remote add upstream https://github.com/alirezakkt/nds-bot.git

# 4. Make sure you're branching off the latest develop
git fetch upstream
git checkout -b feature/12-node-detector upstream/develop
```

Work on your branch, commit, then:

```bash
git push origin feature/12-node-detector
```

Then open a PR **from your fork's branch into `alirezakkt/nds-bot`'s
`develop` branch** — GitHub shows a "Compare & pull request" button after
you push; use that, or open one manually from the "Pull requests" tab.

You do **not** need Write access to the main repo to do any of this.
Everything above works from a fork alone.

## Branch Strategy

```
main        ← protected. Only the Owner merges here. Always deployable/stable.
develop     ← protected. Integration branch. PRs target this, not main.
feature/*   ← one branch per issue, on YOUR fork. e.g. feature/12-node-detector
fix/*       ← bug fixes, on YOUR fork. e.g. fix/nsi-off-by-one
```

Rules:
- Nobody pushes directly to `main` or `develop` on the upstream repo — not
  even the Owner. Everything goes through a PR from a branch (yours, on
  your fork).
- Branch names include the issue number: `feature/12-node-detector`.
- Rebase your feature branch on `upstream/develop` before opening a PR:
  ```bash
  git fetch upstream
  git rebase upstream/develop
  ```
- `develop` → `main` promotion happens at milestone boundaries, decided by
  the Owner, usually accompanied by a tagged release.

## Claiming Work

1. Look at the [Project Board](../../projects) — issues in "Ready" are
   unclaimed.
2. Comment "claiming this" on the issue. Since this is a public repo,
   most contributors won't have permission to self-assign — the Owner (or
   a bot) will assign it to you after your comment. Don't wait for the
   assignment before starting; the comment itself reserves it.
3. If you go quiet for >5 days without updates, the issue may be unassigned
   and reopened for others.

## Commit Messages

```
<module>: <short imperative summary>

<optional longer explanation — why, not just what>

Refs #<issue-number>
```

Example:
```
topology: implement 6-and-6 local extremum test

Window size is configurable (default 6) per spec §2. Threshold
filtering happens in a separate pass — see build_candidates().

Refs #14
```

## Pull Request Process

1. Open PR against `develop`. Use the PR template (auto-filled).
2. Fill in the **"Spec compliance"** section — for every formula your PR
   touches, state which spec section it implements and whether you
   reproduced the worked numeric example.
3. CI must pass (lint + tests) before review starts.
4. Owner reviews within ~3 business days. Expect at least one round of
   feedback — that's normal, not a rejection.
5. Squash-merge once approved. PR title becomes the squash commit message.

## Code Review Checklist (what the Owner is checking for)

- [ ] Does the implementation match the spec formula exactly, or is there
      an unexplained deviation?
- [ ] Does it reproduce the worked numeric example from the spec?
- [ ] Are engineering-choice constants (not in the spec) clearly labeled
      as such, in config, with a comment explaining the reasoning?
- [ ] Are there tests, and do they test the actual math, not just
      "does it run without crashing"?
- [ ] Is the log-scale requirement respected everywhere price displacement
      is computed (spec §1)?

## Discussion & Questions

Use GitHub Discussions for "why does the spec say X" questions — not issue
comments. Keep issue threads focused on implementation status. If a
discussion reveals the spec itself needs clarification, the Owner will
update `docs/NDS_SPEC.md` and note the change in its changelog section.
