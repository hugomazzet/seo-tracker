# seo-tracker

Outil en ligne de commande qui relève chaque jour le positionnement d'un site sur une liste de mots clés, à partir de l'API Google Search Console, et enregistre les résultats dans un fichier CSV local.

Pas de scraping de Google, pas de service payant, pas de base de données : un script Python, une clé d'accès en lecture seule et un fichier CSV.

## Sommaire

- [Fonctionnement](#fonctionnement)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
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

Dans `src/seo_tracker/gsc_tracker.py`, modifier la constante `SITE` :

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

Les seuils se règlent par les constantes en haut de `src/seo_tracker/gsc_tracker.py` :

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

- **Situation actuelle** : un tableau avec, pour chaque mot clé, la dernière position connue (celle de la page la mieux classée), son évolution par rapport à au moins 7 jours plus tôt (en places gagnées ou perdues), les impressions et clics cumulés de toutes les pages, le nombre de pages positionnées au dernier relevé, la page la mieux classée et la date du dernier relevé. Une position en gris signale moins de 10 impressions ce jour-là, donc une valeur peu fiable. Le nombre de pages passe en orange dès que plusieurs pages se partagent le mot clé, ce qui peut signaler une cannibalisation : le survol affiche le détail (page, position, impressions).
- **Position par mot clé** : une courbe par mot clé dans le temps (celle de la page la mieux classée), avec l'axe inversé (la position 1 en haut) et la page 1 en surbrillance. Un trou dans une courbe signifie qu'il n'y a pas eu d'impression ce jour-là. Un clic sur un mot clé dans la légende l'affiche ou le masque.
- **Impressions et clics** : les totaux quotidiens sur l'ensemble des mots clés suivis.

Le fichier est autonome (la bibliothèque de graphiques y est embarquée, il pèse environ 5 Mo) et il est entièrement régénéré à chaque exécution. Les seuils du tableau se règlent par les constantes en haut de `src/seo_tracker/report.py` (`LOW_IMPRESSIONS`, `TREND_DAYS`).

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
  data/
    positions.csv             (créé automatiquement avec le premier run)
    report.html               (créé automatiquement avec la commande --report)
  src/
    seo_tracker/
      __init__.py
      gsc_tracker.py
      report.py
```

## Feuille de route

- Lancement automatique quotidien (launchd sur macOS)
- Lissage des positions sur 7 jours, pondéré par les impressions, dans le rapport
- Génération automatique du rapport après chaque relevé quotidien
- Solution de stockage plus adaptée à l'exploration que le CSV
