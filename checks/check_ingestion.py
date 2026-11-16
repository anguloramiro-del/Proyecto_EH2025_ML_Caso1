"""Isolated Stata/SPSS integrity checks; temporary records are not results.

Run from the project root: .venv/bin/python checks/check_ingestion.py
"""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion import (
    DataIntegrityError, convert_microdata, convert_spss, convert_stata,
    create_analysis_table,
)


def main() -> None:
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    import pyreadstat

    with TemporaryDirectory(prefix="ingestion-check-", dir=ROOT / "checks") as temp:
        folder = Path(temp)
        persons = pd.DataFrame({
            "folio": ["0001", "0001", "0002"], "nro": [1, 2, 1],
            "depto": [1, 1, 2], "area": [1, 1, 2], "s01a_02": [1, 2, 2],
            "s01a_03": [15, 16, 17], "cmasi": [2, 1, 3],
            "upm": [10, 10, 20], "estrato": [1, 1, 2], "factor": [1.0, 2.0, 3.0],
            "s03a_04": [1, 2, 1], "s03b_10": [1, np.nan, 4],
            "s03b_11": [np.nan, np.nan, 3], "s03b_12": [2, np.nan, 2],
            "niv_ed": [3, 3, 3],
            # An entire early chunk is missing; a later chunk contains a value.
            "yhogpc": [np.nan, np.nan, 400.0],
            "sparse_string": ["", "", "present"],
        })
        housing = pd.DataFrame({
            "folio": ["0001", "0002"], "totper": [2, 1],
            "s06a_07": [1, 2], "s06a_09": [1, 2],
            "s06a_10": [1, 2], "s06a_12": [1, 2],
        })
        dta = folder / "test_persons.dta"
        persons.to_stata(
            dta, write_index=False, version=118,
            variable_labels={"cmasi": "Condición de Matriculación y Asistencia"},
            value_labels={"cmasi": {1: "No matriculado", 2: "Asiste", 3: "No asiste"}},
        )
        pfile = folder / "persons.parquet"
        meta = folder / "source_labels.json"
        original_dta_hash = sha256(dta.read_bytes()).hexdigest()
        result = convert_stata(dta, pfile, meta, chunk_size=2)
        restored = pq.read_table(pfile).to_pandas()
        assert len(restored) == 3 and result["chunks"] == 2
        assert restored["folio"].tolist() == ["0001", "0001", "0002"]
        assert restored["cmasi"].tolist() == [2, 1, 3]
        assert restored["yhogpc"].isna().tolist() == [True, True, False]
        assert restored["yhogpc"].iloc[2] == 400.0
        labels = json.loads(meta.read_text())
        assert labels["variable_labels"]["cmasi"] == "Condición de Matriculación y Asistencia"
        assert labels["value_labels"]["cmasi"]["2"] == "Asiste"
        assert labels["source_sha256"] == original_dta_hash
        assert sha256(dta.read_bytes()).hexdigest() == original_dta_hash
        convert_microdata(
            dta, folder / "dispatch_stata.parquet", folder / "dispatch_stata.json", chunk_size=2
        )

        # Native SAV: labels must not replace codes; declared missing is not zero.
        sav_persons = persons.copy()
        sav_persons["user_missing_code"] = [0.0, 99.0, 1.0]
        sav_persons["text_missing"] = ["niñez", "NR", ""]
        sav_persons["raw_date"] = [0.0, 86400.0, 172800.0]
        sav = folder / "test_persons.sav"
        pyreadstat.write_sav(
            sav_persons, str(sav),
            column_labels={"cmasi": "Condición de Matriculación y Asistencia"},
            variable_value_labels={
                "cmasi": {1: "No matriculado", 2: "Asiste", 3: "No asiste"},
                "user_missing_code": {0: "Cero válido", 99: "Sin respuesta"},
            },
            missing_ranges={"user_missing_code": [99], "text_missing": ["NR"]},
            variable_format={"raw_date": "DATE11"},
        )
        sav_hash = sha256(sav.read_bytes()).hexdigest()
        sav_parquet = folder / "sav_persons.parquet"
        sav_metadata = folder / "sav_metadata.json"
        sav_result = convert_microdata(sav, sav_parquet, sav_metadata, chunk_size=2)
        from_sav = pq.read_table(sav_parquet).to_pandas()
        assert sav_result["rows"] == 3 and sav_result["chunks"] == 2
        assert from_sav["folio"].tolist() == ["0001", "0001", "0002"]
        assert from_sav["cmasi"].tolist() == [2, 1, 3]
        assert from_sav["yhogpc"].isna().tolist() == [True, True, False]
        assert from_sav["user_missing_code"].iloc[0] == 0
        assert from_sav["user_missing_code"].isna().tolist() == [False, True, False]
        assert from_sav["text_missing"].iloc[0] == "niñez"
        assert pd.isna(from_sav["text_missing"].iloc[1])
        assert from_sav["text_missing"].iloc[2] == ""
        assert from_sav["raw_date"].tolist() == [0.0, 86400.0, 172800.0]
        assert sav_result["variable_labels"]["cmasi"] == "Condición de Matriculación y Asistencia"
        assert any(
            float(code) == 2 and label == "Asiste"
            for code, label in sav_result["variable_value_labels"]["cmasi"].items()
        )
        assert sav_result["normalized_user_missing_counts"] == {
            "user_missing_code": 1, "text_missing": 1
        }
        assert "raw_date" in sav_result["original_variable_types"]
        assert sav_result["source_sha256"] == sav_hash
        assert sha256(sav.read_bytes()).hexdigest() == sav_hash
        assert "download_date" not in sav_result

        raw_codes_parquet = folder / "sav_preserved_missing.parquet"
        retained = convert_spss(
            sav, raw_codes_parquet, folder / "sav_preserved_missing.json",
            chunk_size=2, normalize_user_missing=False,
        )
        raw_codes = pq.read_table(raw_codes_parquet).to_pandas()
        assert raw_codes["user_missing_code"].tolist() == [0, 99, 1]
        assert raw_codes["text_missing"].tolist() == ["niñez", "NR", ""]
        assert retained["normalized_user_missing_counts"] == {}

        hfile = folder / "housing.parquet"
        housing.to_parquet(hfile, index=False)
        output = folder / "analysis.parquet"
        audit = folder / "audit.json"
        report = create_analysis_table(pfile, hfile, output, audit)
        joined = pq.read_table(output).to_pandas()
        assert len(joined) == 3
        household_sizes = joined.set_index(["folio", "nro"])["hh_totper"].to_dict()
        assert household_sizes == {("0001", 1): 2, ("0001", 2): 2, ("0002", 1): 1}
        assert report["source_weight_sum"] == report["joined_weight_sum"] == 6.0
        assert "totper" not in joined and "hh_totper" in joined
        sav_joined = create_analysis_table(
            sav_parquet, hfile, folder / "sav_analysis.parquet", folder / "sav_audit.json"
        )
        assert sav_joined["joined_rows"] == 3 and sav_joined["joined_weight_sum"] == 6.0

        def must_reject(p, h, reason):
            bad_output = folder / f"rejected_{reason}.parquet"
            bad_audit = folder / f"rejected_{reason}.json"
            try:
                create_analysis_table(p, h, bad_output, bad_audit)
            except DataIntegrityError:
                assert not bad_output.exists() and not bad_audit.exists()
            else:
                raise AssertionError(f"No se rechazó la inconsistencia: {reason}")

        duplicate_households = folder / "housing_duplicate.parquet"
        pd.concat([housing, housing.iloc[[0]]], ignore_index=True).to_parquet(
            duplicate_households, index=False
        )
        must_reject(pfile, duplicate_households, "duplicate_household")
        duplicate_persons = folder / "persons_duplicate.parquet"
        pd.concat([persons, persons.iloc[[0]]], ignore_index=True).to_parquet(
            duplicate_persons, index=False
        )
        must_reject(duplicate_persons, hfile, "duplicate_person")
        missing_household = folder / "housing_missing.parquet"
        housing.iloc[[0]].to_parquet(missing_household, index=False)
        must_reject(pfile, missing_household, "unmatched_household")
        null_key = folder / "persons_null_key.parquet"
        bad_persons = persons.copy()
        bad_persons.loc[0, "folio"] = None
        bad_persons.to_parquet(null_key, index=False)
        must_reject(null_key, hfile, "null_key")
        numeric_key = folder / "housing_numeric_key.parquet"
        bad_housing = housing.copy()
        bad_housing["folio"] = [1, 2]
        bad_housing.to_parquet(numeric_key, index=False)
        must_reject(pfile, numeric_key, "numeric_key_coercion")
        try:
            convert_microdata(folder / "unsupported.csv", folder / "out.parquet", folder / "out.json")
        except ValueError:
            pass
        else:
            raise AssertionError("El despachador aceptó un formato no autorizado.")
    print("PASS: Stata/SPSS codes, labels, dates, missing values, chunk schemas and dispatch.")
    print("PASS: join cardinality, weight invariance and rejection controls.")
    print("All temporary test records were removed; no empirical project results were created.")


if __name__ == "__main__":
    main()
