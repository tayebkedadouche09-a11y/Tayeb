#!/usr/bin/env bash
set -euo pipefail

git submodule sync --recursive
git submodule update --init --recursive

echo "Tayeb components initialized."
echo "ERP core: components/erp-core"
echo "Commercial suite: components/commercial-suite"
echo "BIM engine: components/bim-engine"
