#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

source_file="data/raw/continuity/HISTORICO_SECC_ELECT_PEF_1994-PEF2024_Corte_diciembre2025.accdb"
output_file="data/raw/continuity/official-section-history.csv"
table="HISTORICO_SECC_ELECT_PEF1994-PEF2024_CORTE_diciembre2025"

if [[ ! -s "$source_file" ]]; then
  echo "missing official Access source: $source_file" >&2
  exit 1
fi
mkdir -p "$(dirname "$output_file")"

sg docker -c "docker run --rm -v '$repo_root:/work' -w /work debian:bookworm-slim bash -lc 'apt-get update -qq && apt-get install -y -qq mdbtools ca-certificates >/dev/null && mdb-export $source_file $table > $output_file'"
sha256sum "$source_file" "$output_file"
