# YNOV-CID-INGESTION

Script d'ingestion du module M1 · Collecte & ingestion de données :
API Open-Meteo → Python → Oracle (`staging.meteo_raw`).

Prérequis : la base Oracle et la table `meteo_raw` créées avec les scripts du dépôt **YNOV-CID-SQL**.

## Lancer

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python ingest_meteo.py
```

Connexion : `staging` / `localhost:1521/FREEPDB1`.

## Vérifier dans SQL Developer (connexion `oracle-free-staging`)

```sql
SELECT run_id, ingested_at,
       json_value(payload, '$.current.temperature_2m') AS temperature
FROM meteo_raw
ORDER BY ingested_at DESC;
```

## Remarque sur la déduplication

La contrainte `UNIQUE (source, payload_hash)` ne bloque pas un second appel :
la réponse de l'API contient `generationtime_ms`, qui change à chaque appel,
donc l'empreinte SHA-256 change aussi.
