"""Configuration de seo-tracker : tous les réglages de l'application sont ici.

Chaque réglage est précédé d'un commentaire et de sa valeur par défaut. Seule
la constante SITE est à adapter obligatoirement, le reste fonctionne tel quel.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Site et fichiers
# ---------------------------------------------------------------------------

# Propriété Search Console à interroger.
#   Propriété de type Domaine : "sc-domain:example.com"
#   Propriété de type Préfixe d'URL : "https://example.com/" (avec le slash final)
# Défaut : "sc-domain:example.com" (à remplacer par le site à suivre)
SITE = "sc-domain:hugomazet.com"

# Racine du projet : deux niveaux au-dessus de ce fichier (src/seo_tracker/config.py)
BASE_DIR = Path(__file__).resolve().parents[2]

# Clé du compte de service Google (ne jamais la publier)
# Défaut : secrets/service-account.json
KEY_FILE = BASE_DIR / "secrets" / "service-account.json"

# Liste des mots clés à suivre, un par ligne
# Défaut : inputs/keywords.txt
KEYWORDS_FILE = BASE_DIR / "inputs" / "keywords.txt"

# Fichier CSV où s'accumulent les relevés
# Défaut : data/positions.csv
OUTPUT_FILE = BASE_DIR / "data" / "positions.csv"

# Rapport HTML généré par --report
# Défaut : data/report.html
REPORT_FILE = BASE_DIR / "data" / "report.html"

# ---------------------------------------------------------------------------
# Relevé quotidien
# ---------------------------------------------------------------------------

# Search Console publie ses données avec 2 à 3 jours de retard : le relevé par
# défaut porte sur le jour J moins ce nombre de jours.
# Défaut : 3
DELAY_DAYS = 3

# Nombre de jours précédents vérifiés par --catch-up (et par le lancement
# automatique) : ceux qui manquent dans le CSV sont relevés.
# Défaut : 3
CATCH_UP_DAYS = 3

# ---------------------------------------------------------------------------
# Recherche de nouveaux mots clés (--discover)
# ---------------------------------------------------------------------------

# Période analysée, en jours (jusqu'à J-3). Modifiable ponctuellement avec --days.
# Défaut : 28
DISCOVER_DAYS = 28

# Position moyenne minimale retenue : en dessous, le mot clé est déjà bien classé.
# Défaut : 5
DISCOVER_MIN_POSITION = 5

# Position moyenne maximale retenue : au-delà, le mot clé est trop loin de la page 1.
# Défaut : 20
DISCOVER_MAX_POSITION = 20

# Impressions minimales sur la période pour qu'une requête soit proposée.
# Défaut : 5
DISCOVER_MIN_IMPRESSIONS = 5

# Nombre maximal de requêtes affichées.
# Défaut : 30
DISCOVER_LIMIT = 30

# ---------------------------------------------------------------------------
# Rapport HTML (--report)
# ---------------------------------------------------------------------------

# En dessous de ce nombre d'impressions sur une période, la position moyenne est
# jugée peu fiable (affichée en gris dans le tableau, point pâle sur la courbe).
# Défaut : 10
LOW_IMPRESSIONS = 10

# Durée en jours de chacune des deux périodes comparées dans le tableau : la
# position moyenne affichée porte sur ces derniers jours, l'évolution la compare
# aux mêmes jours précédents.
# Défaut : 7
TREND_DAYS = 7

# Cannibalisation : une page compte comme "en concurrence" sur un mot clé à partir
# de ce nombre d'impressions sur la période (la page la plus vue compte toujours).
# Défaut : 5
CANNIBAL_MIN_IMPRESSIONS = 5

# Dernière position de la page 1 de Google, délimite la zone verte du graphique.
# Défaut : 10
PAGE_ONE_LAST = 10

# À partir de ce nombre de jours relevés, la courbe s'ouvre en vue Semaine plutôt
# qu'en vue Jour.
# Défaut : 14
WEEK_DEFAULT_MIN_DAYS = 14

# Couleurs des courbes, attribuées aux mots clés dans l'ordre (puis on recommence
# au début s'il y a plus de mots clés que de couleurs).
# Défaut : palette Plotly ci-dessous
COLORS = [
    "#636efa", "#ef553b", "#00cc96", "#ab63fa", "#ffa15a",
    "#19d3f3", "#ff6692", "#b6e880", "#ff97ff", "#fecb52",
]
