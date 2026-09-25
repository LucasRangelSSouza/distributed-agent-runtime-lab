#!/usr/bin/env sh
# Generate a LOCAL self-signed certificate for the public-demo edge.
# Output goes to deploy/public-demo/certs/, which Git ignores. This is for
# local validation only; a real deployment supplies its own certificate from
# the private infrastructure repository.
set -eu
dir="$(cd "$(dirname "$0")/.." && pwd)/deploy/public-demo/certs"
mkdir -p "$dir"
if [ -f "$dir/tls.crt" ] && [ "${1:-}" != "--force" ]; then
  echo "certificate already exists in $dir (pass --force to replace)"
  exit 0
fi
cd "$dir"
# MSYS_NO_PATHCONV keeps Git Bash on Windows from rewriting "/CN=..." as a
# path; relative output names stay valid for a native openssl binary.
MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  -keyout tls.key -out tls.crt 2>/dev/null
# The unprivileged nginx user (uid 101) must read the key through the
# read-only bind mount. Acceptable for a throwaway local key only.
chmod 644 tls.crt tls.key
openssl x509 -in tls.crt -noout -subject -enddate
