# Poker Stream GTO Analyzer — Setup

## Prérequis

1. **Python 3.11+** — https://www.python.org/downloads/
2. **Tesseract OCR** — https://github.com/UB-Mannheim/tesseract/wiki
   - Windows: télécharger l'installer et ajouter au PATH
3. **TexasSolver** — https://github.com/bupticybee/TexasSolver
   - Compiler ou télécharger le binaire pré-compilé
4. **Carte de capture HDMI** (ex: Elgato, AVerMedia)

## Installation

```bash
# Cloner le repo
git clone https://github.com/lastiww/inventive-ai.git
cd inventive-ai

# Installer les dépendances Python
pip install -r poker_analyzer/requirements.txt
```

## Lancer le logiciel (Python)

```bash
# Winamax, capture card device 0
python -m poker_analyzer --device 0 --site winamax

# CoinPoker, device 1, debug OCR activé
python -m poker_analyzer --device 1 --site coinpoker --debug

# Avec positions de fenêtres personnalisées
python -m poker_analyzer --device 0 --site winamax \
    --capture-x 0 --capture-y 0 \
    --overlay-x 1920 --overlay-y 0 \
    --width 960 --height 540

# Spécifier le chemin du solver
python -m poker_analyzer --solver-path /chemin/vers/TexasSolver
```

## Créer le .exe

```bash
python build_exe.py
# → dist/PokerGTOAnalyzer.exe
```

## Raccourcis clavier

| Touche | Action |
|--------|--------|
| **D** | Toggle rectangles debug OCR (voir les zones de détection) |
| **E** | Toggle mode Exploitative / GTO only |
| **Q** / ESC | Quitter |

## Setup matériel

```
Source vidéo (stream YouTube)
    │
    ├── Splitter HDMI ──→ Écran 1 (visionnage)
    │
    └── Carte de capture ──→ PC ──→ Logiciel ──→ Écran 2 (overlay GTO)
```

## Calibration des templates OCR

Pour que la détection des cartes fonctionne, il faut capturer des templates :

1. Lancer le logiciel avec `--debug`
2. Les rectangles verts montrent les zones de détection
3. Faire des screenshots des cartes individuelles
4. Les sauvegarder dans `poker_analyzer/ocr/templates/winamax/` ou `coinpoker/`
5. Format: `rank_A.png`, `rank_K.png`, ..., `suit_h.png`, `suit_d.png`, etc.
