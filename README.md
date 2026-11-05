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

Le script interroge l'API Search Console pour une journée donnée, filtre les requêtes qui correspondent à ta liste de mots clés, puis ajoute une ligne par mot clé et par page dans `data/positions.csv`.

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

### 1. Vérifier ton site dans Search Console

Si ce n'est pas déjà fait :

1. Va sur [Search Console](https://search.google.com/search-console) et clique sur **Ajouter une propriété**.
2. Choisis le type **Domaine** et saisis ton domaine (par exemple `example.com`, sans `https://` ni `www`).
3. Ajoute chez ton registrar l'enregistrement DNS de type TXT fourni par Google, puis clique sur **Valider**.

Les premières données apparaissent dans Search Console au bout de 2 à 3 jours. Plus tôt tu vérifies ton site, plus ton historique sera long.

### 2. Créer un compte de service Google Cloud

Le script s'authentifie avec un compte de service, sans connexion manuelle.

1. Sur [Google Cloud Console](https://console.cloud.google.com), crée un projet (par exemple `seo-tracker`).
2. Dans **API et services**, puis **Bibliothèque**, active **Google Search Console API**.
3. Dans **IAM et administration**, puis **Comptes de service**, crée un compte de service (par exemple `gsc-reader`). Aucun rôle n'est nécessaire.
4. Ouvre le compte créé, onglet **Clés**, puis **Ajouter une clé**, **Créer une clé**, format **JSON**.
5. Place le fichier téléchargé à la racine du projet sous le nom `service-account.json`.
6. Note l'adresse mail du compte de service (`gsc-reader@<projet>.iam.gserviceaccount.com`).

### 3. Donner accès au compte de service

Dans Search Console, va dans **Paramètres**, puis **Utilisateurs et autorisations**, et ajoute l'adresse mail du compte de service avec l'autorisation **Restreint** (lecture seule, suffisante).

### 4. Renseigner ta propriété

Dans `src/seo_tracker/gsc_tracker.py`, modifie la constante `SITE` :

```python
SITE = "sc-domain:example.com"
```

Le format dépend du type de propriété :

| Type de propriété | Valeur de `SITE` |
| --- | --- |
| Domaine (vérification DNS) | `sc-domain:example.com` |
| Préfixe d'URL | `https://example.com/` (avec le slash final) |

### 5. Lister tes mots clés

Crée un fichier `keywords.txt` à la racine du projet, un mot clé par ligne, tel qu'il est tapé dans Google. Les lignes qui commencent par `#` sont ignorées.

```text
# Mes mots clés
mot clé numéro un
mot clé numéro deux
```

La comparaison est insensible à la casse mais **exacte** : "glace" ne remonte pas "glaces".

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

Si une date est déjà présente dans le CSV, le script n'ajoute rien : on peut le relancer sans créer de doublons.

## Format des données

Les résultats sont ajoutés à `data/positions.csv` (le dossier est créé automatiquement). Une ligne correspond à un mot clé et à une page pour une date.

| Colonne | Description |
| --- | --- |
| `date` | Jour concerné (format AAAA-MM-JJ) |
| `keyword` | Mot clé suivi |
| `page` | URL de la page positionnée sur ce mot clé |
| `position` | Position moyenne dans les résultats Google ce jour-là |
| `clicks` | Nombre de clics |
| `impressions` | Nombre d'affichages dans les résultats |
| `ctr` | Taux de clic (clics divisés par impressions) |

Exemple :

```csv
date,keyword,page,position,clicks,impressions,ctr
2026-11-05,mot clé numéro un,https://example.com/ma-page/,8.4,2,57,0.0351
2026-11-05,mot clé numéro deux,,,0,0,
```

Quand un mot clé n'a eu aucune impression un jour donné, une ligne vide (sans page ni position) est tout de même écrite, pour garder un historique continu.

## Limites à connaître

- **Position moyenne.** Search Console fournit une moyenne sur la journée, pas un classement en direct. Le résultat varie d'une personne à l'autre (localisation, historique, appareil), la moyenne est donc plus représentative qu'une mesure ponctuelle, mais elle peut différer de ce que tu vois en tapant la requête toi-même.
- **Délai de 2 à 3 jours** sur les données.
- **Impressions nécessaires.** Google ne remonte une requête que si ton site a été affiché au moins une fois. Un mot clé sur lequel tu n'apparais pas du tout n'a pas de position.
- **Correspondance exacte** avec les requêtes réellement tapées par les internautes.

## Sécurité

Le fichier `service-account.json` donne accès à tes données Search Console et ne dois jamais être publié.
Si la clé a été exposée par erreur, supprime-la dans Google Cloud Console (onglet **Clés** du compte de service) et génères-en une nouvelle.

## Structure du projet

```text
seo-tracker/
  pyproject.toml
  inputs/
    keywords.txt              (à créer, voir Configuration)
  secrets/
    service-account.json      (à ajouter, voir Configuration)
  data/
    positions.csv             (créé automatiquement)
  src/
    seo_tracker/
      __init__.py
      gsc_tracker.py
```
