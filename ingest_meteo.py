import hashlib, json, uuid
from datetime import datetime, timezone
import oracledb, requests

SOURCE = "open-meteo"
URL = "https://api.open-meteo.com/v1/forecast"
PARAMS = {"latitude": 48.85, "longitude": 2.35, "current": "temperature_2m,wind_speed_10m"}

# Mêmes paramètres que la connexion SQL Developer "oracle-free-staging"
DB = dict(user="staging", password="staging", dsn="localhost:1521/FREEPDB1")


def fetch():
    """Appelle l'API et renvoie la réponse brute (un dict)."""
    resp = requests.get(URL, params=PARAMS, timeout=10)
    resp.raise_for_status()           # 4xx / 5xx -> exception : on ne stocke pas une erreur
    return resp.json()


def store(payload, run_id):
    """Insère le payload tel quel dans staging.meteo_raw. Ne crée aucune table."""
    raw = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(raw.encode()).hexdigest()
    with oracledb.connect(**DB) as conn:
        with conn.cursor() as cur:           # en synchrone, on exécute via un curseur
            try:
                cur.execute(
                    "INSERT INTO meteo_raw (source, endpoint, run_id, payload, payload_hash) "
                    "VALUES (:1, :2, :3, :4, :5)",
                    [SOURCE, URL, run_id, raw, payload_hash],
                )
                conn.commit()
                return 1
            except oracledb.IntegrityError as e:
                if "ORA-00001" in str(e):   # doublon : déjà en base, on ne fait rien
                    return 0
                raise


if __name__ == "__main__":
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    n = store(fetch(), run_id)
    print(f"run {run_id} : {n} ligne insérée")
