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

## Idempotence

Relancer le script ne duplique rien :

```
run ... : 1 ligne(s) insérée(s), 0 doublon(s)
run ... : 0 ligne(s) insérée(s), 1 doublon(s)
```

Le payload complet est stocké tel quel. L'empreinte `payload_hash` (SHA-256 du JSON
aux clés triées) exclut seulement `generationtime_ms`, un champ technique de l'API qui
change à chaque appel : sans cela, chaque relance aurait une empreinte différente et
la contrainte `UNIQUE (source, payload_hash)` ne détecterait jamais de doublon.
