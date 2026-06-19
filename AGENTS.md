# Agent Instructions

## Deployment Workflow

For each deployment, update the repository metadata before publishing:

1. Bump the project version in `pyproject.toml`.
2. Add the deployment changes to `CHANGELOG.md`.
3. Commit the version and changelog updates.
4. Push the commit to GitHub.
5. Tag the release commit as `v<version>` (for example `v1.2.0`) and push the
   tag: `git tag -a v<version> -m "Release <version>"` then
   `git push origin v<version>`.
6. Create the GitHub release from that tag so it appears on the Releases page,
   using the `CHANGELOG.md` entry as the release notes:
   `gh release create v<version> --title "Release <version>" --notes "..."`.

GitHub Releases are built from tags, so a commit alone does not publish a
release — steps 5 and 6 are required for the version to be visible.

## Commit Authorship

Commit as `anttonalberdi` only — do not add Claude (or any other assistant)
as a co-author in commit messages.

