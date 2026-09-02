# Release and Package Guide

## Release boundary

`main` is the production-complete line. The repository reached `Production Complete / CLOSED` after the final deterministic and operational closure checks recorded in `docs/PRODUCTION_CLOSURE_STATUS.md`.

New functionality belongs to an independent Maintenance/Evolution track. A release from this repository must not reopen the closed production acceptance boundary unless a frozen invariant or production contract has actually broken.

## Container package

The canonical distributable package is the OCI container published to GitHub Container Registry (GHCR):

`ghcr.io/jamshidimoh/ai-future-radar`

The package workflow is `.github/workflows/publish-container.yml` and publishes only from semantic version tags matching `v*.*.*`, or by an explicit manual workflow dispatch with an existing release tag.

The image contains the application source and Python dependencies. The normal GitHub Actions production workflow remains the authoritative stateful publication path because it persists production state back to the repository. Container use therefore requires an external persistent `data/` volume when stateful execution is desired.

## Recommended first release

Use `v1.0.0` for the first public production package. The tag should point to the intended `main` commit containing the final release metadata and package workflow.

After the tag is pushed, the package workflow builds the image, attaches OCI metadata, publishes semantic tags, and emits SBOM/provenance attestations.

## Local container check

Before a release, verify locally with:

```bash
docker build --build-arg VERSION=v1.0.0 -t ghcr.io/jamshidimoh/ai-future-radar:v1.0.0 .
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" ghcr.io/jamshidimoh/ai-future-radar:v1.0.0
```

Do not place credentials in the image, Dockerfile, or repository. Use GitHub Actions secrets for CI/CD and an external secret mechanism for deployed containers.

## Registry visibility

The first GHCR publication may require setting the package visibility to public in the package settings. When a package is published by the repository workflow using `GITHUB_TOKEN`, GitHub can automatically link it to this repository. The Dockerfile also carries the OCI source label required for repository/package linkage guidance.

## Release checklist

1. `main` remains `CLOSED` in `docs/PRODUCTION_CLOSURE_STATUS.md`.
2. No obsolete acceptance/evolution PR is treated as part of the production release.
3. The release tag is created on the intended `main` commit.
4. `Publish AI Future Radar Container` completes successfully.
5. The GHCR package contains both the semantic version tag and `latest` for the first stable release.
6. The image digest from the workflow is retained as the immutable release reference.
