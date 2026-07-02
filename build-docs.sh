#!/bin/bash
# Copie le front vers docs/ pour GitHub Pages (Deploy from a branch → /docs)
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p docs/avatars
cp index.html docs/
cp public/config.js docs/config.js
cp public/drc-client.js docs/drc-client.js
cp avatars/*.png docs/avatars/ 2>/dev/null || true
echo 'davidramenecrepe.fr' > docs/CNAME
touch docs/.nojekyll
echo "✅ docs/ prêt pour GitHub Pages"
