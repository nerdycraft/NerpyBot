# Release Process

NerpyBot uses **tag-driven versioning**: pushing a `v*` tag to GitHub is the single action that kicks off a release. CI handles image building, pushing, and badge updates automatically — there's no manual publish step.

## Version Format

| Scenario             | Example version      | How it's derived                                     |
| -------------------- | -------------------- | ---------------------------------------------------- |
| Tagged release       | `1.2.3`              | Tag `v1.2.3` → strip `v`                             |
| Untagged `main` push | `1.2.3.dev4+gabcdef` | `git describe --tags --always` → PEP 440 dev version |
| No prior tag         | `abcdef` (short SHA) | `git describe` falls back to commit SHA              |

Always use `v<major>.<minor>.<patch>` for release tags (e.g. `v0.7.0`). Pre-release tags aren't currently used.

## What CI Does Automatically

For a properly formatted semver tag (e.g. `v1.2.3`), two workflows fire. Note that `docker.yml` triggers on any `v*` tag (including `v1` or future pre-release tags), while `release-badge.yml` requires the full `v*.*.*` format to trigger:

| Workflow            | Trigger       | What it does                                                                                                                      |
| ------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `docker.yml`        | `v*` tag push | Builds multi-arch (`amd64`/`arm64`) bot and web images; pushes semver + SHA tags to ghcr.io; verifies version in the pushed image |
| `release-badge.yml` | `v*.*.*` tag  | Opens a PR against `main` to update the version badge in `README.md`                                                              |

Docker image tags produced per release (both `nerpybot` and `nerpybot-web`):

- `1.2.3` — exact version
- `1.2` — minor alias
- `1` — major alias
- `<sha>` — commit SHA (7 chars)

The `latest` tag is only published on `main` branch pushes, not on tag pushes — `docker.yml` also triggers on pushes to `main`, and those runs are what keep `latest` up to date.

## Simple Release Flow (tag `main` directly)

Use this when `main` is clean and ready to ship.

1. Confirm `main` is in the desired state and all CI is green.
2. Create and push the annotated tag:

   ```bash
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```

3. Watch the `docker.yml` run in GitHub Actions — it will build, push, and verify both images.
4. Merge the auto-opened badge PR from `release-badge.yml` once it appears.
5. Create a GitHub Release from the tag (optional but recommended for changelogs).

## Release Branch Flow (when `main` has unfinished work)

Use this when `main` has commits that shouldn't go out yet (e.g. half-finished features).

1. Branch off the last good commit on `main`:

   ```bash
   git checkout -b release/1.2.3 <good-sha-or-main>
   git push origin release/1.2.3
   ```

2. Apply only the fixes/changes needed for this release (cherry-pick from `main` if needed).
3. Tag the release branch:

   ```bash
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```

4. CI builds and publishes images from the tagged commit.
5. Merge the badge PR targeting `main`.
6. Cherry-pick any release-branch fixes back to `main` that `main` doesn't already have.
7. Delete the release branch once merged back:

   ```bash
   git push origin --delete release/1.2.3
   ```

## Hotfix Flow

Use this when a critical bug needs fixing against an already-released version.

1. Branch off the release tag:

   ```bash
   git checkout -b hotfix/1.2.4 v1.2.3
   ```

2. Apply the fix, commit, then tag the patch release:

   ```bash
   git add <changed-files>
   git commit -m "fix: <hotfix summary>"
   git tag -a v1.2.4 -m "Hotfix v1.2.4"
   git push origin hotfix/1.2.4 v1.2.4
   ```

3. CI builds and publishes the patched images.
4. Cherry-pick the fix to `main`:

   ```bash
   git cherry-pick <fix-sha>
   git push origin main
   ```

5. Delete the hotfix branch.
