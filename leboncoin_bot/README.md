# Bot LeBonCoin — Détecteur de voitures à revendre

Scrape les annonces LeBonCoin, estime le prix marché de chaque véhicule et
identifie automatiquement les voitures sous-cotées à acheter pour revendre.

## Installation

```bash
pip install httpx
```

## Usage rapide

```bash
# Scan unique avec le profil citadines (défaut)
python -m leboncoin_bot

# Chercher des Peugeot 208 / Renault Clio entre 2000 et 8000 €
python -m leboncoin_bot --marques peugeot renault --modeles 208 clio --prix-max 8000

# Profil SUV, dans les départements 75, 92, 93, 94
python -m leboncoin_bot --profil suv --departements 75 92 93 94

# Mode surveillance continue (scan toutes les 10 minutes)
python -m leboncoin_bot --loop 600

# Avec alertes Telegram
python -m leboncoin_bot --loop 300 \
  --telegram-token BOT_TOKEN \
  --telegram-chat-id CHAT_ID

# Afficher les meilleures affaires enregistrées
python -m leboncoin_bot --deals
```

## Options

| Option | Description | Défaut |
|---|---|---|
| `--profil` | citadines / compactes / suv / premium | citadines |
| `--marques` | Marques à chercher | (profil) |
| `--modeles` | Modèles à chercher | (profil) |
| `--prix-min` | Prix minimum (€) | (profil) |
| `--prix-max` | Prix maximum (€) | (profil) |
| `--annee-min` | Année minimum | (profil) |
| `--km-max` | Kilométrage maximum | (profil) |
| `--departements` | Codes département | tous |
| `--seuil` | % sous le marché pour alerter | 20 |
| `--score-min` | Score minimum (0-100) | 60 |
| `--pages` | Pages à scraper par recherche | 5 |
| `--loop N` | Relancer le scan toutes les N secondes | - |
| `--deals` | Afficher les deals enregistrés et quitter | - |
| `--db` | Chemin base SQLite | leboncoin_cars.db |
| `-v` | Mode verbose | - |

## Algorithme de scoring

Le score (0-100) combine 4 critères pondérés :

| Critère | Poids | Détail |
|---|---|---|
| Écart au prix marché | 50% | Médiane de 35-70 annonces similaires |
| Kilométrage | 20% | Comparé à la moyenne d'âge (15 000 km/an) |
| Âge du véhicule | 15% | Décroît de 0 à 15 ans |
| Type de vendeur | 15% | Particulier > Professionnel |

Une annonce est marquée **deal** si :
- Score ≥ `--score-min` (défaut 60)
- Prix ≥ `--seuil`% sous le prix marché (défaut 20%)
- Au moins 5 annonces similaires pour estimer le marché

## Telegram

1. Crée un bot via [@BotFather](https://t.me/BotFather) → récupère le token
2. Envoie un message à ton bot puis récupère le chat_id via :
   `https://api.telegram.org/botTOKEN/getUpdates`
3. Lance le bot avec `--telegram-token` et `--telegram-chat-id`

## Structure

```
leboncoin_bot/
├── config.py       Critères de recherche et profils préconfigurés
├── scraper.py      Client API LeBonCoin + parsing des annonces
├── analyzer.py     Estimation du prix marché et scoring
├── database.py     Stockage SQLite des annonces et résultats
├── notifier.py     Affichage console + notifications Telegram
└── main.py         CLI et orchestration
```
