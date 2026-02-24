# PR: Fix CI Rust Scorer Artifact Name Collision

## Summary

Fixes the `409 Conflict: an artifact with this name already exists on the workflow run` error when deploying to production after staging.

## Problem

When `release_and_deploy_production.yml` runs:
1. **Staging** deployment builds and uploads `rust-scorer-{tag}.zip`
2. **Production** deployment tries to build and upload `rust-scorer-{tag}.zip` again
3. Both are in the same parent workflow run → 409 Conflict error
4. Production always fails on first attempt, requires manual retry

## Solution

**Build once, reuse for both environments:**
- Staging: `build_rust_scorer: true` → Builds the artifact once
- Production: `build_rust_scorer: false` → Skips build, downloads existing artifact

### Benefits:
- ✅ No more 409 Conflict errors
- ✅ Faster production deployment (saves 5-10 min Rust build time)
- ✅ Saves GitHub Actions minutes
- ✅ Guaranteed exact same binary in staging and production
- ✅ Extended artifact retention to 7 days (from 1 day) for multi-stage deployments

## Changes

### 1. `.github/workflows/build_and_deploy_generic.yml`

Added new input parameter to control whether to build Rust scorer:

```yaml
inputs:
  # ... existing inputs ...
  build_rust_scorer:
    description: "Whether to build the Rust scorer (false to reuse existing artifact)"
    type: boolean
    required: false
    default: true
```

Made the build job conditional:

```yaml
build-rust-scorer:
  name: Build Rust scorer Lambda zip
  runs-on: ubuntu-24.04-arm
  if: ${{ inputs.build_rust_scorer }}  # <-- NEW: Only run if explicitly requested
  # ... rest of job ...
```

Extended artifact retention:

```yaml
- name: Upload artifact
  uses: actions/upload-artifact@v4
  with:
    name: rust-scorer-${{ inputs.docker_tag }}.zip
    path: ./rust-scorer/target/lambda/passport-scorer/bootstrap.zip
    retention-days: 7  # <-- CHANGED: from 1 to 7 days
```

### 2. `.github/workflows/release_and_deploy_production.yml`

Updated staging deployment to build the artifact:

```yaml
deploy-staging:
  name: Deploy to Staging
  needs: [create-draft-release, ref]
  uses: ./.github/workflows/build_and_deploy_generic.yml
  with:
    refspec: ${{ needs.ref.outputs.refspec }}
    docker_tag: ${{ needs.ref.outputs.docker_tag }}
    environment: staging
    build_rust_scorer: true  # <-- NEW: Build the artifact
  secrets: inherit
```

Updated production deployment to reuse the artifact:

```yaml
deploy-production:
  name: Deploy to Production
  needs: [ref, deploy-staging, deploy-interface-to-staging]
  uses: ./.github/workflows/build_and_deploy_generic.yml
  with:
    refspec: ${{ needs.ref.outputs.refspec }}
    docker_tag: ${{ needs.ref.outputs.docker_tag }}
    environment: production
    build_rust_scorer: false  # <-- NEW: Reuse artifact from staging
  secrets: inherit
```

## Testing

After merging:
1. Trigger a production release workflow
2. Verify staging builds the Rust scorer artifact
3. Verify production skips the build and downloads the artifact
4. Verify both deployments succeed without manual retry

## Git Branch

Branch: `fix/ci-rust-artifact-reuse`
Commit: `d3070ab0 - fix(ci): prevent rust scorer artifact name collision between environments`

## Files Changed

- `.github/workflows/build_and_deploy_generic.yml` (5 additions, 1 deletion)
- `.github/workflows/release_and_deploy_production.yml` (2 additions)

## Creating the PR

Since workflow permissions are required, another Claude session or team member with workflow permissions should:

```bash
git fetch origin fix/ci-rust-artifact-reuse
git checkout fix/ci-rust-artifact-reuse
gh pr create --title "fix(ci): prevent rust scorer artifact name collision between environments" \
  --body-file CI_RUST_ARTIFACT_REUSE_PR.md \
  --base main
```

Or manually create the PR via GitHub UI using this branch.
