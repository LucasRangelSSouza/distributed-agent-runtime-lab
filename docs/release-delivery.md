# Release delivery contract

The repository validates source changes in CI and publishes a container only from a new Git tag that starts with `v`. A tag is a release boundary: do not move or reuse it.

## What the release workflow does

The `Release container` workflow builds the root Dockerfile, pushes the tagged image and its commit-SHA tag to GitHub Container Registry, requests an SBOM and BuildKit provenance, then publishes GitHub build provenance for the resulting digest. It uses the workflow's `GITHUB_TOKEN`; no registry password belongs in the repository or its example files.

The workflow runs only after a tag push. The existing `v0.1.0` release predates this workflow, so it has no associated published container or provenance from this repository. A future tag will create those artifacts only if the workflow succeeds.

## Operator checklist

1. Confirm the target commit has a passing CI run and a clean working tree.
2. Review the Dockerfile and the release diff. The image must not include local credential files, Terraform state, or an unpinned application input.
3. Create an annotated, previously unused version tag and push it.
4. Inspect the release workflow, the image digest, the SBOM, and the provenance attestation in GitHub before referring others to the image.
5. Deploy by digest, not by a mutable tag, and run the selected local or cloud resilience evidence before claiming runtime behavior.

The workflow makes a build artifact available. It does not apply Terraform, create a cluster, distribute Kubernetes secrets, or prove a cloud deployment.
