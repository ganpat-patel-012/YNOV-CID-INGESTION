import hashlib, json, uuid
from datetime import datetime, timezone
import oracledb, requests

SOURCE = "open-meteo"
URL = "https://api.open-meteo.com/v1/forecast"
PARAMS = {"latitude": 48.85, "longitude": 2.35, "current": "temperature_2m,wind_speed_10m"}

# Mêmes paramètres que la connexion SQL Developer "oracle-free-staging"
DB = dict(user="staging", password="staging", dsn="localhost:1521/FREEPDB1")

# Champs techniques de l'API qui changent à chaque appel sans que la donnée change.
# Ils restent stockés dans le payload, mais sont exclus de l'empreinte : sinon
# chaque relance produit un hash différent et l'idempotence ne fonctionne plus.
VOLATILE_KEYS = {"generationtime_ms"}


def payload_fingerprint(payload):
    """SHA-256 de la forme canonique du payload, sans les champs volatils."""
    stable = {k: v for k, v in payload.items() if k not in VOLATILE_KEYS}
    canonical = json.dumps(stable, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def fetch():
    """Appelle l'API et renvoie la réponse brute (un dict)."""
    resp = requests.get(URL, params=PARAMS, timeout=10)
    resp.raise_for_status()           # 4xx / 5xx -> exception : on ne stocke pas une erreur
    return resp.json()


def store(payloads, run_id):
    """Insère chaque payload tel quel dans staging.meteo_raw. Ne crée aucune table.
    Renvoie (insérées, doublons)."""
    inserees = doublons = 0
    with oracledb.connect(**DB) as conn:
        with conn.cursor() as cur:           # en synchrone, on exécute via un curseur
            for payload in payloads:
                raw = json.dumps(payload, sort_keys=True)   # le brut complet, tel quel
                try:
                    cur.execute(
                        "INSERT INTO meteo_raw (source, endpoint, run_id, payload, payload_hash) "
                        "VALUES (:1, :2, :3, :4, :5)",
                        [SOURCE, URL, run_id, raw, payload_fingerprint(payload)],
                    )
                    inserees += 1
                except oracledb.IntegrityError as e:
                    if "ORA-00001" not in str(e):
                        raise
                    doublons += 1              # déjà en base : on compte et on continue
        conn.commit()
    return inserees, doublons


if __name__ == "__main__":
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    inserees, doublons = store([fetch()], run_id)
    print(f"run {run_id} : {inserees} ligne(s) insérée(s), {doublons} doublon(s)")
