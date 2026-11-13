#!/bin/bash
# Relevé quotidien Search Console, puis régénération du rapport.
# Lancé chaque jour par launchd (voir la section "Lancement automatique" du README),
# mais utilisable à la main : bash scripts/run-daily.sh
set -euo pipefail

# Dossier du projet : le parent du dossier scripts/
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# launchd démarre avec un PATH minimal : on cherche uv dans le PATH, puis à son
# emplacement d'installation habituel. UV=/chemin/vers/uv permet de le forcer.
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

# Sortie en UTF-8 même sans variables de langue (cas de launchd)
export PYTHONUTF8=1

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

notify_failure() {
  local code=$?
  echo "$(timestamp) ECHEC (code $code)"
  osascript -e 'display notification "Le relevé quotidien a échoué. Détails dans ~/Library/Logs/seo-tracker.log" with title "seo-tracker"' || true
  exit "$code"
}
trap notify_failure ERR

cd "$PROJECT_DIR"
echo "$(timestamp) Début du relevé"

# --update : si la date du jour existe déjà (relance, test manuel), elle est remplacée
# par les données actuelles de Google au lieu d'être ignorée
# --frozen : n'altère jamais uv.lock, les versions des dépendances restent celles testées
"$UV" run --frozen seo-tracker --update
"$UV" run --frozen seo-tracker --report

echo "$(timestamp) Terminé"
