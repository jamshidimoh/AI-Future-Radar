# Release and Package Guide

## Release boundary

`main` is the production source line, but **production closure is currently pending**. A previous release's closure claim is historical; it does not replace the current `Production Closure Gate`, which requires three consecutive successful live runs on the same application-code fingerprint with confirmed Telegram delivery and mission/quality coverage. Issue #69 must remain open until that evidence passes.

The maintenance/evolution release `v1.1.0` is prepared to publish automatically only after `Production Closure Gate` succeeds. A successful code CI run or a merged PR alone does not publish the stable release.

## Container package

The canonical distributable package is the OCI container published to GitHub Container Registry (GHCR):

`ghcr.io/jamshidimoh/ai-future-radar`

The package workflow is `.github/workflows/publish-container.yml`. Existing semantic tags (`v*.*.*`) can publish their matching image, and manual dispatch can publish a specified existing tag. In addition, `v1.1.0` plus the `latest` container tag and GitHub Release are created by the workflow only after a successful `Production Closure Gate` run.

The image contains the application source and Python dependencies. The normal GitHub Actions production workflow remains the authoritative stateful publication path because it persists production state back to the repository. Container use therefore requires an external persistent `data/` volume when stateful execution is desired.

## Current published release

The latest GitHub Release currently recorded is `v1.0.2` (`AI Future Radar v1.0.2`). It is a published, non-draft, non-prerelease release. The next stable release target is `v1.1.0`, which must not be treated as published until the closure-gated release workflow creates it.

Use a semantic image tag only when GHCR actually contains it; otherwise use the published `latest` tag or an immutable image digest from the build workflow.

## Local container check

Before running a release image locally, build or pull the exact published tag you intend to validate. For the current release, use `v1.0.2`; after the next closure-gated release succeeds, use `v1.1.0`. The container workflow derives image tags from semantic `v*.*.*` refs.

Example local build:

```bash
docker build --build-arg VERSION=v1.0.2 -t ghcr.io/jamshidimoh/ai-future-radar:v1.0.2 .
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" ghcr.io/jamshidimoh/ai-future-radar:v1.0.2
```

Do not place credentials in the image, Dockerfile, or repository. Use GitHub Actions secrets for CI/CD and an external secret mechanism for deployed containers.

## Registry visibility

The first GHCR publication may require setting the package visibility to public in the package settings. When a package is published by the repository workflow using `GITHUB_TOKEN`, GitHub can automatically link it to this repository. The Dockerfile also carries the OCI source label required for repository/package linkage guidance.

## Release checklist

1. `Production Closure Gate` completes successfully after three consecutive live runs on the same application-code fingerprint; Issue #69 reflects that evidence.
2. The quality gates, confirmed Telegram delivery, diversity policy, language QA, and duplicate checks pass without weakening acceptance criteria.
3. The accepted release revision is the workflow's checkout/target commit; the `v1.1.0` tag is never retargeted.
4. `Publish AI Future Radar Container` validates and publishes the accepted source.
5. The GHCR package contains `v1.1.0` and `latest`, along with build provenance and an SBOM.
6. A GitHub Release is created with `docs/releases/v1.1.0.md`; the immutable image digest is retained as the package reference.
