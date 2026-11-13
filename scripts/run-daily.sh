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

# Notification macOS : le texte est passé en argument à osascript, ce qui évite
# tout problème de guillemets
notify() {
  osascript \
    -e 'on run argv' \
    -e 'display notification (item 1 of argv) with title "seo-tracker"' \
    -e 'end run' \
    "$1" || true
}

notify_failure() {
  local code=$?
  echo "$(timestamp) ECHEC (code $code)"
  notify "Le relevé quotidien a échoué. Détails dans ~/Library/Logs/seo-tracker.log"
  exit "$code"
}
trap notify_failure ERR

OUTPUT_FILE="$(mktemp)"
trap 'rm -f "$OUTPUT_FILE"' EXIT

cd "$PROJECT_DIR"
echo "$(timestamp) Début du relevé"

# --catch-up : relève J-3 et reprend les jours précédents s'ils manquent (panne, Mac éteint)
# --frozen : n'altère jamais uv.lock, les versions des dépendances restent celles testées
# tee garde la sortie dans le journal tout en la conservant pour la notification
"$UV" run --frozen seo-tracker --catch-up | tee "$OUTPUT_FILE"
"$UV" run --frozen seo-tracker --report

# Dernière ligne "Résumé : ..." du relevé, reprise dans la notification
SUMMARY="$(sed -n 's/^Résumé : //p' "$OUTPUT_FILE" | tail -n 1)"

echo "$(timestamp) Terminé"
notify "Relevé terminé. ${SUMMARY:-Voir le journal pour le détail.}"
