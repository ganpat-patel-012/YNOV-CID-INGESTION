# TP 1 – Une table dans staging, alimentée par une API

**Nom :** Ganpat Patel · **Branche :** `tp-1`

Le TP est réparti sur deux dépôts :

| Dépôt | Contenu |
|---|---|
| [YNOV-CID-SQL](https://github.com/ganpat-patel-012/YNOV-CID-SQL/tree/tp-1) | Le squelette : `sql/staging/002_init_staging_velib.sql` |
| [YNOV-CID-INGESTION](https://github.com/ganpat-patel-012/YNOV-CID-INGESTION/tree/tp-1) (ce dépôt) | Le script : `staging/ingest_velib.py` |

Le SQL a été commité et poussé **avant** le Python : commit `9c5da43` « TP1: squelette staging »
(YNOV-CID-SQL, 27/11/2026 15:27:33) puis le script dans ce dépôt.

## 1. API choisie : Vélib' Métropole – état des stations

- **URL :** https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json
- **Clé :** aucune.
- **Où est la liste :** sous `data.stations` (la racine contient `lastUpdatedOther`, `ttl`, `data`).
- **Champ identifiant :** `station_id` (1 524 stations, toutes avec un `station_id` unique).

Exemple d'objet :

```json
{"station_id": 213688169, "stationCode": "16107", "num_bikes_available": 11,
 "num_bikes_available_types": [{"mechanical": 10}, {"ebike": 1}],
 "num_docks_available": 24, "is_installed": 1, "is_renting": 1, "is_returning": 1,
 "last_reported": 1795786483, ...}
```

## 2. Commandes

**Appliquer le squelette** (une fois, dans SQL Developer, connexion `oracle-free-staging`) :
ouvrir `sql/staging/002_init_staging_velib.sql` du dépôt YNOV-CID-SQL et exécuter avec **F5**.
Résultat : `Table VELIB_RAW created.` ; `SELECT table_name FROM user_tables;` liste `VELIB_RAW`.

Le fichier s'appelle `002_…` et non `001_…` : dans ce dépôt, `001_init_staging.sql` contient
déjà la table `meteo_raw` de l'installation. On ne modifie jamais un script SQL déjà appliqué,
on en ajoute un nouveau, numéroté à la suite (principe des migrations).

**Lancer le script :**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # puis renseigner les identifiants
.venv/bin/python staging/ingest_velib.py
```

Le fichier `.env` (ignoré par Git) contient `DB_USER`, `DB_PASSWORD`, `DB_DSN`.

## 3. Frontières du schéma (partie 2.3)

| Connexion | Requête | Résultat obtenu | Pourquoi |
|---|---|---|---|
| oracle-free-staging | `SELECT count(*) FROM velib_raw;` | `0` | La table lui appartient |
| oracle-free-admin | `SELECT count(*) FROM staging.velib_raw;` | `0` | L'administrateur voit tout |
| oracle-free-integration | `SELECT count(*) FROM staging.velib_raw;` | `ORA-00942: table or view "STAGING"."VELIB_RAW" does not exist` | La table existe, mais integration n'a pas le droit de la voir |

## 4. Trois lancements successifs

```
run 20261127T142814-bb02f1c8 : 1524 insérées, 0 doublons
run 20261127T142818-a446c67d : 0 insérées, 1524 doublons
run 20261127T142822-0403819c : 0 insérées, 1524 doublons
```

Le nombre de lignes ne bouge pas : chaque station a le même contenu, donc le même
`payload_hash`, et la contrainte `UNIQUE (source, external_id, payload_hash)` refuse l'INSERT
(ORA-00001), que le script compte comme doublon.

**Requête de preuve** (connexion staging) :

```sql
SELECT run_id, count(*) AS lignes, min(ingested_at) AS debut
FROM velib_raw
GROUP BY run_id
ORDER BY debut;
```

```
RUN_ID                     LIGNES  DEBUT
20261127T142814-bb02f1c8   1524    27/11/26 14:28:16,649566
20261127T142843-2e82d564   65      27/11/26 14:28:44,360513
```

Les lancements 2 et 3 n'apparaissent pas : ils n'ont inséré aucune ligne. La ligne `…2e82d564`
est le lancement fait après la panne (partie 5) : entre-temps, 65 stations avaient changé
(vélos pris ou rendus), elles sont entrées comme nouvelles lignes. C'est voulu : le staging
accumule l'historique, seuls les contenus identiques sont refusés.

**Le brut reste interrogeable :**

```sql
SELECT external_id,
       json_value(payload, '$.num_bikes_available') AS valeur,
       ingested_at
FROM velib_raw
WHERE run_id = '20261127T142814-bb02f1c8'
FETCH FIRST 10 ROWS ONLY;
```

```
EXTERNAL_ID   VALEUR  INGESTED_AT
213688169     11      27/11/26 14:28:16,649566
19179944124   5       27/11/26 14:28:16,731492
18795078746   2       27/11/26 14:28:16,737927
36255         0       27/11/26 14:28:16,740438
251039991     4       27/11/26 14:28:16,741814
85002689      3       27/11/26 14:28:16,743107
2515829865    18      27/11/26 14:28:16,744479
516709288     5       27/11/26 14:28:16,745384
37874517      21      27/11/26 14:28:16,745902
210565680     33      27/11/26 14:28:16,746316
```

Aucun `external_id` vide (`SELECT count(*) … WHERE external_id IS NULL` → 0).

## 5. Casser quelque chose (partie 3.2)

Test : URL remplacée par `…/station_status_WRONG.json`, puis relance.

**Le script a-t-il planté ?** Oui, immédiatement, code de sortie 1 :

```
requests.exceptions.HTTPError: 404 Client Error: Not Found for url:
https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status_WRONG.json
```

`raise_for_status()` transforme la réponse 404 en exception dans `fetch()`, avant tout accès
à la base.

**Qu'y a-t-il dans la base pour ce run_id ?** Rien. `store()` n'a jamais été appelée : aucune
ligne, la table est restée à 1 524 lignes et 1 seul run_id. Même si l'erreur était arrivée
pendant la boucle d'insertion, le commit unique en fin de `store()` garantit « tout ou rien ».

**Que ferais-je demain matin en voyant l'erreur ?**
1. Lire le message : un 404 signifie que l'URL n'existe plus (endpoint déplacé ou renommé),
   ce n'est pas une panne passagère ; un timeout ou un 5xx serait plutôt temporaire.
2. Tester l'URL à la main (navigateur / `curl`) et vérifier la documentation de l'API.
3. Corriger l'URL et relancer : c'est sans danger, car le script est idempotent.
4. Accepter le trou dans l'historique : l'API Vélib' ne donne que l'état actuel, l'état
   des stations pendant la panne est perdu.

**Après correction de l'URL :** `run 20261127T142843-2e82d564 : 65 insérées, 1459 doublons`.
1 459 stations inchangées sont refusées, 65 stations modifiées entrent : cohérent avec
1 524 stations.

## Organisation : un dossier par couche

```
.
├── staging/                  <- ingestion : API -> staging.<source>_raw
│   ├── ingest_velib.py       <- TP 1 (fetch() ne connaît pas la base, store() ne connaît pas l'API)
│   └── ingest_meteo.py       <- exemple de l'installation
├── integration/              <- transformations staging -> integration (vide pour l'instant)
├── mart/                     <- tables métier integration -> mart (vide pour l'instant)
├── .env.example              <- modèle du fichier .env (sans vrai mot de passe)
└── requirements.txt
```
