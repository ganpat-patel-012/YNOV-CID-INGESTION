"""Test (pour aller plus loin) : appeler store() deux fois avec le même objet
ne doit créer qu'une seule ligne dans staging.velib_raw.

Lancer depuis la racine du dépôt : .venv/bin/python tests/test_idempotence.py
Nécessite Oracle démarré et le fichier .env. Le test nettoie ce qu'il insère.
"""
import sys
import uuid
from pathlib import Path

import oracledb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "staging"))
import ingest_velib  # noqa: E402

# Un objet factice, avec un identifiant qu'aucune vraie station ne peut avoir
FAKE_ID = f"TEST-{uuid.uuid4().hex[:8]}"
ITEM = {"station_id": FAKE_ID, "num_bikes_available": 3, "num_docks_available": 7}


def count_rows(cur):
    return cur.execute(
        "SELECT count(*) FROM velib_raw WHERE external_id = :1", [FAKE_ID]
    ).fetchone()[0]


def test_store_twice_inserts_once():
    try:
        assert ingest_velib.store([ITEM], "test-run-1") == (1, 0), "1er appel : 1 insérée attendue"
        assert ingest_velib.store([ITEM], "test-run-2") == (0, 1), "2e appel : 1 doublon attendu"
        with oracledb.connect(**ingest_velib.DB) as conn:
            assert count_rows(conn.cursor()) == 1, "une seule ligne doit exister"

        # Même station, contenu différent : doit entrer (le staging accumule)
        changed = dict(ITEM, num_bikes_available=4)
        assert ingest_velib.store([changed], "test-run-3") == (1, 0), "contenu modifié : 1 insérée attendue"
    finally:
        with oracledb.connect(**ingest_velib.DB) as conn:   # nettoyage
            conn.cursor().execute("DELETE FROM velib_raw WHERE external_id = :1", [FAKE_ID])
            conn.commit()


if __name__ == "__main__":
    test_store_twice_inserts_once()
    print("OK : 2 appels identiques -> 1 ligne ; contenu modifié -> nouvelle ligne ; nettoyage fait")
