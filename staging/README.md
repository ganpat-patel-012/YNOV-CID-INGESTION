# Couche staging : scripts d'ingestion

Chaque script appelle une API et insère ses réponses **telles quelles** dans la table
`staging.<source>_raw`. Aucun script ne crée de table : le squelette est dans
[YNOV-CID-SQL](https://github.com/ganpat-patel-012/YNOV-CID-SQL/tree/tp-1/sql/staging).

| Script | API | Table |
|---|---|---|
| `ingest_velib.py` | Vélib' Métropole, état des stations (TP 1) | `staging.velib_raw` |
| `ingest_meteo.py` | Open-Meteo (exemple de l'installation) | `staging.meteo_raw` |

Lancer depuis la racine du dépôt : `.venv/bin/python staging/ingest_velib.py`
