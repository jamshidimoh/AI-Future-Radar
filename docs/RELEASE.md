# Release and Package Guide

## Release boundary

`main` is the production-complete line. The repository reached `Production Complete / CLOSED` after the final deterministic and operational closure checks recorded in `docs/PRODUCTION_CLOSURE_STATUS.md`.

New functionality belongs to an independent Maintenance/Evolution track. A release from this repository must not reopen the closed production acceptance boundary unless a frozen invariant or production contract has actually broken.

## Container package

The canonical distributable package is the OCI container published to GitHub Container Registry (GHCR):

`ghcr.io/jamshidimoh/ai-future-radar`

The package workflow is `.github/workflows/publish-container.yml` and publishes semantic version tags matching `v*.*.*`, or by an explicit manual workflow dispatch with an existing release tag.

The image contains the application source and Python dependencies. The normal GitHub Actions production workflow remains the authoritative stateful publication path because it persists production state back to the repository. Container use therefore requires an external persistent `data/` volume when stateful execution is desired.

## Current published release

The latest GitHub Release currently recorded for the repository is `V1.0.1.On.Publish` (`AI Future Radar V1.0.1`). It is a published, non-draft, non-prerelease release targeting `main`.

Use the corresponding semantic image tag only when the GHCR package contains that tag; otherwise use `latest` or the immutable image digest retained by the publish workflow. The repository does not currently expose a GitHub Release named `v1.0.0`, so documentation must not present `v1.0.0` as the published reference release.

## Local container check

Before running a release image locally, build or pull the exact published tag you intend to validate. For the current release, the repository release identifier is `V1.0.1.On.Publish`; the container workflow derives image tags from semantic `v*.*.*` refs.

Example local build:

```bash
docker build --build-arg VERSION=V1.0.1.On.Publish -t ghcr.io/jamshidimoh/ai-future-radar:V1.0.1.On.Publish .
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" ghcr.io/jamshidimoh/ai-future-radar:V1.0.1.On.Publish
```

Do not place credentials in the image, Dockerfile, or repository. Use GitHub Actions secrets for CI/CD and an external secret mechanism for deployed containers.

## Registry visibility

The first GHCR publication may require setting the package visibility to public in the package settings. When a package is published by the repository workflow using `GITHUB_TOKEN`, GitHub can automatically link it to this repository. The Dockerfile also carries the OCI source label required for repository/package linkage guidance.

## Release checklist

1. `main` remains `CLOSED` in `docs/PRODUCTION_CLOSURE_STATUS.md`.
2. No obsolete acceptance/evolution PR is treated as part of the production release.
3. The release tag is created on the intended `main` commit.
4. `Publish AI Future Radar Container` completes successfully.
5. The GHCR package contains the semantic version tag and, for a tag-triggered stable release, `latest`.
6. The image digest from the workflow is retained as the immutable release reference.
