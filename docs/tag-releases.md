# SWCLI version-tag releases

Normal branch pushes run the Python 3.9/3.14 Windows unit tests, installed CLI
checks and Linux wheel/sdist checks. There is no pull-request trigger. Manual
`native_full=true` adds the existing full Windows SOLIDWORKS acceptance, without
publishing a Release. API development calibration remains a local VM workflow.

For future versions, a maintainer first merges the version and its
`docs/releases/v<version>.md` notes into `main`, then pushes the matching version
tag (for example `v0.1.0a17`). That tag push authorizes automatic release after
verification. It does not require a second manual workflow dispatch. The workflow
must already be present in the tagged commit; existing version tags and published
assets are not rewritten or republished.

## Trust and execution order

1. A secret-free policy job checks out upstream `main` and checks the pushed tag.
   The repository must be `YJBeetle/SWCLI`; the tag's commit must match the Actions
   SHA, be reachable from `origin/main`, and contain exactly the tagged source
   version. Version tags use canonical PEP 440 spelling. Alpha, beta, release
   candidate and development versions are GitHub prereleases; stable/post
   releases are not.
2. Unit and package jobs must succeed. The original package artifact is installed
   in the existing 120-minute native job, which keeps the same visible smoke,
   hidden full plan, strict native assertions and cleanup. The 600-second native
   and 1800-second set budgets remain unchanged.
3. The release job downloads `swcli-dist` and the current attempt's native
   evidence from the same Actions run, with artifact digest mismatch fatal.
   `scripts/ci/tag-release.py` also checks the Actions run SHA/event/attempt and
   original artifact IDs/digests through the API. No package is rebuilt.
4. Source version, wheel metadata/source resources and sdist metadata/source
   bytes must agree with the tag checkout. The native report must cover the
   exact public full plan (currently 19 sets/20 steps), with every step complete,
   successful and clean, empty process boundaries and clean daemon exits. The
   public properties gate, visible smoke, actual installed daemon version and
   visible server exit are checked separately. A private fixture/calibration
   report or selected-set diagnostic cannot replace this proof.
5. Publication rechecks the live tag target, creates a draft, uploads the exact
   original wheel/sdist plus release notes, provenance and `SHA256SUMS`, and then
   publishes. A same-name asset is reused only if its downloaded bytes match;
   there is no `--clobber`, package replacement or automatic rollback.
6. Every published asset is anonymously downloaded and compared byte for byte.
   The job retains `release-public-verification.json` with the verified hashes
   in its `swcli-release-<run>-<attempt>` artifact. The provenance uploaded before
   publication deliberately does not claim that this later public-download
   check has already succeeded.

Only the release job receives `contents: write`; other jobs keep read-only
repository access. The private Google Drive credential is used only by the
native job after the secret-free trusted-tag gate (or explicit manual full
selection). This follows GitHub's [minimum token permissions guidance](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).

## Failure and recovery

A failed native assertion stops the release path. Preserve its original evidence
and fix the first cause; do not retry native API calls, relax assertions, or
create another tag with different contents under the same version.

A publication interruption can leave a draft. The helper validates every existing
asset before uploading any missing files and can resume only when all existing
bytes match the current verified inputs. An existing published release must
already have the complete identical asset set; otherwise the job fails for
manual review. A new run/attempt can change provenance even when package bytes
match, so it is intentionally not allowed to overwrite earlier metadata silently.
An anonymous-download failure is reported as a failed public verification, even
if GitHub has already published the Release; it does not replace assets or undo
the publication.

A tag created by another workflow using `GITHUB_TOKEN` does not trigger a new
push workflow. Maintainer tag pushes work normally; automation that intentionally
creates tags needs an appropriately scoped GitHub App token. See GitHub's
[workflow triggering rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

This workflow publishes SWCLI only. It does not promote DockerSW tags, mutate
MacSW releases, or claim Wine acceptance from the Windows result.
