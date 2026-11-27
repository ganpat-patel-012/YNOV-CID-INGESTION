"""TP1 : ingestion de l'état des stations Vélib' dans staging.velib_raw.

Une ligne par station, payload tel que l'API l'a renvoyé, doublons refusés par la base.
Ce script ne crée jamais de table : le squelette est dans YNOV-CID-SQL (sql/002_init_staging_velib.sql).
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

import oracledb
import requests
from dotenv import load_dotenv

SOURCE = "velib"
URL = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/station_status.json"

# Identifiants de connexion lus dans .env (jamais commité)
load_dotenv()
DB = dict(user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], dsn=os.environ["DB_DSN"])


def fetch() -> list[dict]:
    """Appelle l'API et renvoie la liste des stations. Ne connaît pas la base."""
    resp = requests.get(URL, timeout=10)
    resp.raise_for_status()                  # 4xx / 5xx -> exception : on ne stocke pas une erreur
    return resp.json()["data"]["stations"]   # la liste est sous data.stations


def store(items: list[dict], run_id: str) -> tuple[int, int]:
    """Insère une ligne par station. Ne connaît pas l'API. Renvoie (insérées, doublons)."""
    inserees = doublons = 0
    with oracledb.connect(**DB) as conn:     # une seule connexion pour tout le run
        with conn.cursor() as cur:           # un seul curseur pour toute la boucle
            for item in items:
                external_id = str(item["station_id"])
                raw = json.dumps(item, sort_keys=True)              # forme canonique de l'objet
                payload_hash = hashlib.sha256(raw.encode()).hexdigest()  # hash de l'objet, pas de la réponse
                try:
                    cur.execute(
                        "INSERT INTO velib_raw (source, endpoint, external_id, run_id, payload, payload_hash) "
                        "VALUES (:1, :2, :3, :4, :5, :6)",
                        [SOURCE, URL, external_id, run_id, raw, payload_hash],
                    )
                    inserees += 1
                except oracledb.IntegrityError as e:
                    if "ORA-00001" not in str(e):   # autre erreur d'intégrité : on ne la cache pas
                        raise
                    doublons += 1                   # déjà en base : on compte et on continue
        conn.commit()                        # un seul commit à la fin : tout ou rien
    return inserees, doublons


if __name__ == "__main__":
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    inserees, doublons = store(fetch(), run_id)
    print(f"run {run_id} : {inserees} insérées, {doublons} doublons")
