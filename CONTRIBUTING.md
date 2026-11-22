# Project guide

Pull requests are reviewed by Cursor Bugbot before they merge.

## What runs on every pull request

1. GitHub Actions runs the auth tests, the frontend build, and the image builds.
2. Cursor Bugbot reviews the diff. The review rules live in [`.cursor/BUGBOT.md`](.cursor/BUGBOT.md). The run settings live in [`.cursor/config/bugbot.yaml`](.cursor/config/bugbot.yaml) and are set to review every push to the pull request.
3. Bugbot posts a `Cursor Bugbot` check. After the Cursor GitHub app is enabled for this repository, require that check in branch protection so a pull request cannot merge without a review.

Bugbot loads its rules from the base branch, so a pull request cannot turn its own review off.

## If a review does not start

Comment on the pull request:

```
cursor review
```

`bugbot run` is the same command. To see which rules were included:

```
cursor review verbose=true
```

## One-time setup

In the Cursor dashboard, open Bugbot and enable `mangatohjunior/devops-interview-ai`. Personal settings must not be left on "run only when mentioned", or automatic reviews will not cover every pull request.

## Admin account

Registration never creates an admin. Before the site is public, run `backend/create_admin.py` once with `ADMIN_EMAIL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`.
