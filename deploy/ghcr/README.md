# GHCR image publishing

Documentation HQ: [README](../../README.md)

The repository publishes three immutable container images to GitHub Container
Registry (GHCR):

```text
ghcr.io/<owner>/<repository>/web:<commit-sha>
ghcr.io/<owner>/<repository>/bff:<commit-sha>
ghcr.io/<owner>/<repository>/backend:<commit-sha>
```

The backend image is used by both the API and worker applications. The image
tag is the full 40-character Git commit SHA. Do not use `latest` for Darkube
staging or production promotion.

## GitHub setup

1. Merge the workflow in `.github/workflows/publish-ghcr.yml` into `main`.
2. Confirm the repository Actions policy permits `GITHUB_TOKEN` package write
   permission.
3. Push to `main`, or start the workflow manually from GitHub Actions.
4. Open the repository's **Packages** section and set each package to private.
5. Download the `ghcr-release-manifest-<commit-sha>` workflow artifact and
   use its digests as the authoritative release identity.

The workflow uses only the built-in `GITHUB_TOKEN`; no personal access token is
stored in repository secrets.

## Keyless signing policy

Every published image digest is signed with Cosign using GitHub Actions OIDC.
No private key and no signing secret is stored in GitHub. The policy is recorded
in [`cosign-policy.json`](cosign-policy.json).

The signature must have:

- OIDC issuer `https://token.actions.githubusercontent.com`.
- Certificate identity for this repository's `publish-ghcr.yml` workflow on
  the protected `main` or `master` branch.
- The exact digest recorded in `release-manifest.json`.

The publication workflow needs `id-token: write` only to obtain the short-lived
OIDC identity. It signs by digest immediately after each GHCR push.

## Production verification

Before production promotion, run **Verify GHCR release signatures** from GitHub
Actions. Provide:

1. `release_sha`: the full commit SHA in the release manifest.
2. `manifest_run_id`: the Actions run ID that produced the manifest artifact.

The verification workflow downloads the manifest, requires exactly `web`, `bff`,
and `backend`, and runs `cosign verify` against every manifest digest. It fails
closed for a missing signature, wrong digest, wrong repository identity, wrong
workflow, or non-GitHub issuer. Only after this workflow succeeds should the
manifest be used for production deployment.

## Production promotion

After Darkube staging has passed, run **Promote verified release to production**
from GitHub Actions. Provide:

1. `release_sha`: the exact commit SHA under test.
2. `manifest_run_id`: the run that produced the GHCR release manifest.
3. `staging_run_id`: the run that produced `darkube-deployment-verification`.

The workflow requires the staging verification artifact and the GHCR signature
checks to pass before entering the protected `production` environment. After
the required approval, it uploads `production-promotion.json`, which contains
the exact digest-pinned image values for the Darkube production console.
Darkube remains a manual provider-console action; record the deployed digests
and retain the promotion artifact with the release evidence.

Do not replace this with tag-only verification. A commit-SHA tag identifies the
release conventionally; the digest plus keyless certificate proves the exact
published artifact and its build provenance.

## Darkube setup

Create a private registry connection in Darkube for `ghcr.io` with a
read-only package credential. Store the credential in Darkube, not in this
repository or application environment variables. Configure these image refs:

| Application | Image |
| --- | --- |
| Web | `ghcr.io/<owner>/<repository>/web:<commit-sha>` |
| BFF | `ghcr.io/<owner>/<repository>/bff:<commit-sha>` |
| API | `ghcr.io/<owner>/<repository>/backend:<commit-sha>` |
| Worker | `ghcr.io/<owner>/<repository>/backend:<commit-sha>` |

For every release, select the same commit SHA for all four applications. The
API and worker use different commands but must use the same backend image.

## Promotion rule

Build once in GitHub Actions, validate in staging, and promote the same image
tag and digest to production. If verification fails, redeploy the previous
known-good release manifest. Never rebuild from a moving branch during
rollback.

## Production rollback workflow

Run **Roll back production release** from GitHub Actions when production must
return to a previous known-good release. This workflow does not call Darkube.
It verifies the selected manifest and all three GHCR image signatures before
requesting approval in the protected `production` environment.

Provide:

1. `previous_release_sha`: the full 40-character commit SHA in the known-good
   release manifest.
2. `manifest_run_id`: the Actions run ID that uploaded
   `ghcr-release-manifest-<previous_release_sha>`.
3. `incident_reference`: an optional incident or ticket identifier.

After approval, download the `production-rollback-<sha>` artifact. It contains
`production-rollback.json` with the exact image digests for web, BFF, and the
shared backend image. In Darkube, update web and BFF to their recorded images,
and update both API and worker to the recorded backend image. Deploy manually,
run the production smoke checklist, and retain the artifact with the incident
evidence. If validation or signature verification fails, stop and select
another previously verified manifest.
