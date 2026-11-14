# seo-tracker

Outil en ligne de commande qui relève chaque jour le positionnement d'un site sur une liste de mots clés, à partir de l'API Google Search Console, et enregistre les résultats dans un fichier CSV local.

Pas de scraping de Google, pas de service payant, pas de base de données : un script Python, une clé d'accès en lecture seule et un fichier CSV.

## Sommaire

- [Fonctionnement](#fonctionnement)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Lancement automatique (macOS)](#lancement-automatique-macos)
- [Format des données](#format-des-données)
- [Limites à connaître](#limites-à-connaître)
- [Sécurité](#sécurité)
- [Structure du projet](#structure-du-projet)
- [Feuille de route](#feuille-de-route)

## Fonctionnement

Le script interroge l'API Search Console pour une journée donnée, filtre les requêtes qui correspondent à la liste de mots clés, puis ajoute dans `data/positions.csv` une ligne par mot clé et par page. Quand plusieurs pages du site sont apparues sur le même mot clé, elles sont toutes conservées.

Search Console publie ses données avec 2 à 3 jours de retard. Par défaut, le script récupère donc les données de **J-3**.

## Prérequis

- Un site vérifié dans [Google Search Console](https://search.google.com/search-console)
- Un compte Google Cloud (gratuit, aucune facturation n'est nécessaire pour cet usage)
- [uv](https://docs.astral.sh/uv/) pour gérer Python et les dépendances (la version de Python requise est indiquée dans `pyproject.toml`, uv l'installe automatiquement si besoin)

## Installation

```bash
git clone <url-du-depot>
cd seo-tracker
uv sync
```

## Configuration

La configuration tient en trois éléments : une propriété Search Console, une clé d'accès et une liste de mots clés.

### 1. Vérifier le site dans Search Console

Si ce n'est pas déjà fait :

1. Aller sur [Search Console](https://search.google.com/search-console) et cliquer sur **Ajouter une propriété**.
2. Choisir le type **Domaine** et saisir le domaine (par exemple `example.com`, sans `https://` ni `www`).
3. Ajouter chez le registrar l'enregistrement DNS de type TXT fourni par Google, puis cliquer sur **Valider**.

Les premières données apparaissent dans Search Console au bout de 2 à 3 jours. Plus tôt le site est vérifié, plus l'historique sera long.

### 2. Créer un compte de service Google Cloud

Le script s'authentifie avec un compte de service, sans connexion manuelle.

1. Sur [Google Cloud Console](https://console.cloud.google.com), créer un projet (par exemple `seo-tracker`).
2. Dans **API et services**, puis **Bibliothèque**, activer **Google Search Console API**.
3. Dans **IAM et administration**, puis **Comptes de service**, créer un compte de service (par exemple `gsc-reader`). Aucun rôle n'est nécessaire.
4. Ouvrir le compte créé, onglet **Clés**, puis **Ajouter une clé**, **Créer une clé**, format **JSON**.
5. Placer le fichier téléchargé dans le dossier `secrets/` du projet sous le nom `service-account.json`.
6. Noter l'adresse mail du compte de service (`gsc-reader@<projet>.iam.gserviceaccount.com`).

### 3. Donner accès au compte de service

Dans Search Console, aller dans **Paramètres**, puis **Utilisateurs et autorisations**, et ajouter l'adresse mail du compte de service avec l'autorisation **Restreint** (lecture seule, suffisante).

### 4. Renseigner la propriété

Dans `src/seo_tracker/config.py`, modifier la constante `SITE` :

```python
SITE = "sc-domain:example.com"
```

Le format dépend du type de propriété :

| Type de propriété | Valeur de `SITE` |
| --- | --- |
| Domaine (vérification DNS) | `sc-domain:example.com` |
| Préfixe d'URL | `https://example.com/` (avec le slash final) |

### 5. Lister les mots clés

Créer un fichier `keywords.txt` dans le dossier `inputs/` du projet, un mot clé par ligne, tel qu'il est tapé dans Google. Les lignes qui commencent par `#` sont ignorées.

```text
# Mes mots clés
mot clé numéro un
mot clé numéro deux
```

La comparaison est insensible à la casse mais **exacte** : "photographe paris" ne remonte pas "photographe paris pas cher".

### 6. Ajuster les réglages (facultatif)

Tous les réglages de l'application sont rassemblés dans `src/seo_tracker/config.py`, chacun avec un commentaire et sa valeur par défaut : emplacement des fichiers, délai de publication des données, jours de rattrapage, seuils de `--discover`, seuils et couleurs du rapport. Seule la constante `SITE` doit obligatoirement être adaptée.

## Utilisation

Vérifier que l'accès fonctionne :

```bash
uv run seo-tracker --test
```

Si tout est correct, la propriété s'affiche avec son niveau d'accès :

```text
sc-domain:example.com (siteRestrictedUser)
```

Si la liste est vide, le compte de service n'a pas été ajouté correctement dans Search Console (étape 3).

Relever les données de J-3 :

```bash
uv run seo-tracker
```

Relever une date précise :

```bash
uv run seo-tracker --date 2026-11-05
```

Si une date est déjà présente dans le CSV, le script n'y touche pas et ne crée donc jamais de doublons.

Mettre à jour une date déjà enregistrée :

```bash
uv run seo-tracker --date 2026-11-05 --update
```

Les lignes de cette date sont remplacées par les données actuelles de Search Console, les autres dates ne sont pas modifiées. C'est utile quand le script a tourné avant que Google ait publié les données du jour (les lignes à 0 sont alors remplacées par les vraies valeurs).

Relever J-3 et rattraper les jours manquants :

```bash
uv run seo-tracker --catch-up
```

En plus de J-3, le script vérifie les 3 jours précédents et relève ceux qui ne sont pas encore dans le CSV. Un jour enregistré sans aucune impression (Google n'avait pas encore publié ses données) est relevé à nouveau. Les jours déjà complets ne sont pas touchés. Le nombre de jours vérifiés se règle avec `--catch-up N` (par exemple `--catch-up 7`) ou par la constante `CATCH_UP_DAYS` de `config.py`. Une ligne `Résumé` termine l'affichage, elle est reprise dans la notification du lancement automatique.

`--catch-up` se combine avec `--date` (fin de la fenêtre) et avec `--update` (tous les jours de la fenêtre sont remplacés).

### Repérer de nouveaux mots clés à suivre

```bash
uv run seo-tracker --discover
```

Cette commande interroge Search Console sur les 28 derniers jours (jusqu'à J-3) et affiche les requêtes sur lesquelles le site apparaît et qui ne sont pas présentes dans `keywords.txt`. Ne sont retenues que celles proches de la page 1, là où un peu de travail sur la page peut faire gagner des places. Rien n'est enregistré : c'est une aide à la décision d'ajouter ou non les mots clés pertinents dans `keywords.txt`.

Exemple de sortie :

```text
Période : du 2026-10-06 au 2026-11-02 (28 jours)
312 requêtes remontées par Google, 2 candidates (position 5 à 20, au moins 5 impressions, hors mots clés déjà suivis)

Position   Impr.  Clics  Requête
    12.4      80      1  mot clé candidat un
    19.5      25      0  mot clé candidat deux
```

Les colonnes sont la position moyenne sur la période, le nombre d'impressions, le nombre de clics et la requête. Les résultats sont triés par impressions décroissantes.

Pour changer la période analysée :

```bash
uv run seo-tracker --discover --days 60
```

Les seuils se règlent dans `src/seo_tracker/config.py` :

| Constante | Rôle | Valeur par défaut |
| --- | --- | --- |
| `DISCOVER_DAYS` | Période analysée, en jours | 28 |
| `DISCOVER_MIN_POSITION` | Position minimale retenue | 5 |
| `DISCOVER_MAX_POSITION` | Position maximale retenue | 20 |
| `DISCOVER_MIN_IMPRESSIONS` | Impressions minimales sur la période | 5 |
| `DISCOVER_LIMIT` | Nombre maximal de lignes affichées | 30 |

La comparaison avec `keywords.txt` est exacte (insensible à la casse) : une variante plus longue d'un mot clé déjà suivi apparaît donc comme une requête distincte.

### Générer un rapport visuel

```bash
uv run seo-tracker --report
```

Cette commande lit `data/positions.csv` et génère `data/report.html`, qui s'ouvre dans n'importe quel navigateur (sur macOS : `open data/report.html`). Elle ne contacte pas Google et ne nécessite ni clé ni connexion.

Le rapport contient :

- **Situation actuelle** : un tableau avec, pour chaque mot clé, la position moyenne des 7 derniers jours (pondérée par les impressions, en retenant chaque jour la page la mieux classée), son évolution (places gagnées ou perdues par rapport à la moyenne des 7 jours précédents), les impressions et clics cumulés de toutes les pages, le nombre de pages positionnées sur ces 7 jours, la page la mieux classée et la date du dernier relevé. Une position en gris signale moins de 10 impressions sur ces 7 jours, donc une valeur peu fiable. Une évolution en gris signale moins de 10 impressions sur l'une des deux périodes comparées. Le nombre de pages passe en orange dès que plusieurs pages se partagent le mot clé, ce qui peut signaler une cannibalisation : le survol affiche le détail (position moyenne et impressions de chaque page sur les 7 jours). Pour éviter les faux positifs, une page n'est comptée qu'à partir de 5 impressions sur la période (la page la plus vue compte toujours) ; les autres sont listées comme "marginales" dans l'infobulle.
- **Position par mot clé** : une courbe par mot clé dans le temps (celle de la page la mieux classée), avec l'axe inversé (la position 1 en haut) et la page 1 en surbrillance. Un sélecteur **Jour, Semaine, Mois** change la granularité : en vue Semaine ou Mois, la position est la moyenne des positions quotidiennes pondérée par les impressions (un jour à 80 impressions pèse plus qu'un jour à 2), ce qui lisse le bruit et fait ressortir la tendance. La vue Semaine s'affiche par défaut à partir de 14 jours de données, la vue Jour avant. Un point pâle correspond à moins de 10 impressions sur la période, donc à une position peu fiable. Un trou dans une courbe signifie qu'il n'y a pas eu d'impression sur la période. Un clic sur un mot clé dans la légende l'affiche ou le masque.
- **Impressions et clics** : les totaux quotidiens sur l'ensemble des mots clés suivis.

Le fichier est autonome (la bibliothèque de graphiques y est embarquée, il pèse environ 5 Mo) et il est entièrement régénéré à chaque exécution. Les seuils du tableau se règlent dans `src/seo_tracker/config.py` (`LOW_IMPRESSIONS`, `TREND_DAYS`, `WEEK_DEFAULT_MIN_DAYS`, `CANNIBAL_MIN_IMPRESSIONS`).

## Lancement automatique (macOS)

Le script `scripts/run-daily.sh` enchaîne le relevé (J-3 et rattrapage des jours manquants, avec `--catch-up`) puis la génération du rapport. Avec launchd, le planificateur de macOS, il peut tourner chaque jour sans intervention.

### Prérequis

- Le projet fonctionne à la main : `uv sync`, puis `uv run seo-tracker --test` affiche la propriété.
- Le Mac reste allumé et une session utilisateur reste ouverte : un agent launchd ne s'exécute que pendant une session. Si le Mac est en veille à l'heure prévue, le relevé se lance au réveil, mais le plus simple est de désactiver la mise en veille automatique dans les réglages d'énergie.

### Installation

1. Créer le fichier `~/Library/LaunchAgents/com.example.seo-tracker.plist` avec le contenu suivant. Remplacer `/CHEMIN/VERS/seo-tracker` par le chemin absolu du dossier du projet et `UTILISATEUR` par le nom d'utilisateur macOS (launchd ne comprend ni `~` ni les variables) :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.seo-tracker</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/CHEMIN/VERS/seo-tracker/scripts/run-daily.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/CHEMIN/VERS/seo-tracker</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>30</integer>
  </dict>

  <key>StandardOutPath</key>
  <string>/Users/UTILISATEUR/Library/Logs/seo-tracker.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/UTILISATEUR/Library/Logs/seo-tracker.log</string>
</dict>
</plist>
```

2. Charger l'agent :

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.example.seo-tracker.plist
```

3. Tester tout de suite, sans attendre l'heure prévue :

```bash
launchctl kickstart -k gui/$(id -u)/com.example.seo-tracker
tail -f ~/Library/Logs/seo-tracker.log
```

Le journal doit afficher `Début du relevé`, une ligne par jour traité, la ligne `Résumé`, la ligne `Rapport généré`, puis `Terminé`. Une notification macOS confirme la réussite.

### Fonctionnement

- **Horaire** : 8h30 chaque jour, modifiable dans le bloc `StartCalendarInterval` du fichier plist. L'heure a peu d'importance, car le script lit les données de J-3, déjà publiées par Google.
- **Journal** : `~/Library/Logs/seo-tracker.log`. Il grossit de quelques lignes par jour.
- **Réussite** : une notification macOS résume le relevé, par exemple "2026-11-10 relevé, 1 jour rattrapé (2026-11-09)". Si Google n'a encore publié aucune donnée pour un jour, la notification le signale.
- **Échec** : une notification macOS s'affiche et le code d'erreur est écrit dans le journal.
- **Notifications** : elles passent par `osascript`. Si rien ne s'affiche, vérifier dans Réglages Système, Notifications, que l'application "Éditeur de script" (Script Editor) est autorisée.
- **Jour manqué** : une panne courte (Mac éteint, réseau coupé) est rattrapée automatiquement au lancement suivant, dans la limite des 3 jours précédents. Au-delà, les données restent disponibles chez Google pendant environ 16 mois et se récupèrent avec `uv run seo-tracker --catch-up 10` ou `uv run seo-tracker --date AAAA-MM-JJ`.
- **État de l'agent** : `launchctl print gui/$(id -u)/com.example.seo-tracker`
- **Modifier le fichier plist** : décharger l'agent avec `launchctl bootout gui/$(id -u)/com.example.seo-tracker`, puis le recharger avec la commande de l'étape 2.
- **Désinstaller** : `bootout`, puis supprimer le fichier plist.

## Format des données

Les résultats sont ajoutés à `data/positions.csv` (le dossier est créé automatiquement). Une ligne correspond à un couple mot clé et page pour une date. Quand plusieurs pages du site apparaissent sur le même mot clé, chacune a sa ligne, la mieux classée en premier.

| Colonne | Description |
| --- | --- |
| `date` | Jour concerné (format AAAA-MM-JJ) |
| `keyword` | Mot clé suivi |
| `page` | URL de la page concernée |
| `position` | Position moyenne de cette page dans les résultats Google ce jour-là |
| `clicks` | Nombre de clics sur cette page pour ce mot clé |
| `impressions` | Nombre d'affichages de cette page dans les résultats |
| `ctr` | Taux de clic (clics divisés par impressions) |

Exemple :

```csv
date,keyword,page,position,clicks,impressions,ctr
2026-11-05,mot clé numéro un,https://example.com/ma-page/,8.4,2,57,0.0351
2026-11-05,mot clé numéro un,https://example.com/autre-page/,14.2,0,12,0.0
2026-11-05,mot clé numéro deux,,,0,0,
```

Quand un mot clé n'a eu aucune impression un jour donné, une ligne vide (sans page ni position) est tout de même écrite, pour garder un historique continu.

## Limites à connaître

- **Position moyenne.** Search Console fournit une moyenne sur la journée, pas un classement en direct. Le résultat varie d'une personne à l'autre (localisation, historique, appareil), la moyenne est donc plus représentative qu'une mesure ponctuelle, mais elle peut différer de ce que l'on voit en tapant la requête soi-même.
- **Délai de 2 à 3 jours** sur les données.
- **Impressions nécessaires.** Google ne remonte une requête que si le site a été affiché au moins une fois. Un mot clé sur lequel le site n'apparaît pas du tout n'a pas de position.
- **Correspondance exacte** avec les requêtes réellement tapées par les internautes.
- **Plusieurs pages par mot clé.** Si plusieurs pages du site se positionnent sur la même requête, chacune a sa ligne dans le CSV. Dans le rapport, la position affichée est celle de la page la mieux classée, et les clics et impressions sont additionnés sur toutes les pages.

## Sécurité

Le fichier `service-account.json` donne accès aux données Search Console et ne doit jamais être publié.
Si la clé a été exposée par erreur, il est nécessaire de la supprimer dans la Google Cloud Console (onglet **Clés** du compte de service) et d'en générer une nouvelle.

Avant le premier commit, ajouter ces lignes au .gitignore du projet :

```gitignore
secrets/
inputs/
data/
.venv/
```

## Structure du projet

```text
seo-tracker/
  pyproject.toml
  inputs/
    keywords.txt              (à créer, voir Configuration)
  secrets/
    service-account.json      (à ajouter, voir Configuration)
  scripts/
    run-daily.sh              (relevé puis rapport, utilisé par launchd)
  data/
    positions.csv             (créé automatiquement avec le premier run)
    report.html               (créé automatiquement avec la commande --report)
  src/
    seo_tracker/
      __init__.py
      config.py                 (tous les réglages, voir Configuration)
      gsc_tracker.py
      report.py
```

## Feuille de route

- Solution de stockage plus adaptée à l'exploration que le CSV
