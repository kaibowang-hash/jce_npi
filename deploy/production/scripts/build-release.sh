#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"
if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "A production image must be built from a clean exact checkout." >&2
  exit 2
fi
release_sha="$(git rev-parse HEAD)"
if [[ ! "${release_sha}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "The release SHA is invalid." >&2
  exit 2
fi

docker build \
  --file deploy/production/Containerfile \
  --target backend \
  --build-arg "RELEASE_SHA=${release_sha}" \
  --tag "launchflow-npi:${release_sha}" \
  .
docker build \
  --file deploy/production/Containerfile \
  --target spa \
  --build-arg "RELEASE_SHA=${release_sha}" \
  --build-arg "VITE_DEPLOYMENT_ENV=production" \
  --tag "launchflow-npi-spa:${release_sha}" \
  .

backend_revision="$(docker image inspect "launchflow-npi:${release_sha}" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
spa_revision="$(docker image inspect "launchflow-npi-spa:${release_sha}" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
if [[ "${backend_revision}" != "${release_sha}" || "${spa_revision}" != "${release_sha}" ]]; then
  echo "The built image release labels do not match the exact checkout." >&2
  exit 1
fi
echo "Built LaunchFlow production images for exact SHA ${release_sha}."
