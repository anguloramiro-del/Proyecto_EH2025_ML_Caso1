"""Read Stata/SPSS in bounded chunks and validate the person–household join.

The source files are never changed. Derived numeric columns use float64 so
Stata integer columns remain compatible when later chunks contain missing
values. All Stata integer storage types fit exactly in float64. String keys
retain their leading zeros. Value labels are saved separately, not substituted
for the original codes.
"""

from __future__ import annotations

import hashlib
from itertools import chain
import json
import math
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any


PERSON_COLUMNS = (
    "folio", "nro", "depto", "area", "s01a_02", "s01a_03", "cmasi",
    "upm", "estrato", "factor", "yhogpc",
    "s03a_04", "s03b_10", "s03b_11", "s03b_12", "niv_ed",
)
HOUSING_COLUMNS = ("totper", "s06a_07", "s06a_09", "s06a_10", "s06a_12")


class DataIntegrityError(ValueError):
    """A source cannot be transformed without compromising its integrity."""


def _temporary_path(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        prefix=f".{destination.stem}-", suffix=destination.suffix,
        dir=destination.parent, delete=False,
    ) as handle:
        return Path(handle.name)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _arrow_schema(frame: Any) -> Any:
    import pandas as pd
    import pyarrow as pa

    fields = []
    for name, dtype in frame.dtypes.items():
        if pd.api.types.is_bool_dtype(dtype):
            arrow_type = pa.bool_()
        elif pd.api.types.is_numeric_dtype(dtype):
            arrow_type = pa.float64()
        elif pd.api.types.is_object_dtype(dtype) or pd.api.types.is_string_dtype(dtype):
            arrow_type = pa.string()
        else:
            raise DataIntegrityError(f"Tipo no previsto en la columna {name}: {dtype}")
        fields.append(pa.field(str(name), arrow_type, nullable=True))
    return pa.schema(fields)


def _as_arrow(frame: Any, schema: Any) -> Any:
    import pyarrow as pa

    if list(frame.columns) != schema.names:
        raise DataIntegrityError("Las columnas cambiaron entre fragmentos del archivo de origen.")
    arrays = [pa.array(frame[field.name], type=field.type, from_pandas=True) for field in schema]
    return pa.Table.from_arrays(arrays, schema=schema)


def convert_stata(
    raw_path: str | Path,
    parquet_path: str | Path,
    metadata_path: str | Path,
    *,
    chunk_size: int = 50_000,
) -> dict[str, Any]:
    """Convert one .dta to Parquet and save its source labels and provenance.

    Stata dates are retained as their original numeric values. Ordinary and
    extended Stata missing values become Arrow nulls; the conversion does not
    impute them or replace them with zero. That normalization is recorded in
    the metadata. Every chunk uses the same normalized schema, including when
    an entire early chunk is missing in a numeric column.
    """
    import pandas as pd
    import pyarrow.parquet as pq

    raw = Path(raw_path).resolve()
    parquet = Path(parquet_path).resolve()
    metadata = Path(metadata_path).resolve()
    if not raw.is_file():
        raise FileNotFoundError(f"Falta el archivo Stata: {raw.name}")
    if raw.suffix.lower() != ".dta":
        raise ValueError("La ingesta requiere un archivo .dta del INE.")
    if chunk_size < 1:
        raise ValueError("chunk_size debe ser positivo.")
    if len({raw, parquet, metadata}) != 3:
        raise ValueError("Las rutas de origen, Parquet y metadatos deben ser distintas.")

    parquet_tmp = _temporary_path(parquet)
    metadata_tmp = _temporary_path(metadata)
    try:
        with pd.read_stata(
            raw, iterator=True, chunksize=chunk_size, convert_categoricals=False,
            convert_dates=False, convert_missing=False, preserve_dtypes=True,
        ) as reader:
            variable_labels = reader.variable_labels()
            value_labels = {
                str(label_set): {str(code): str(label) for code, label in values.items()}
                for label_set, values in reader.value_labels().items()
            }
            first = next(reader, None)
            if first is None or first.empty:
                raise DataIntegrityError("El archivo Stata no contiene observaciones.")
            schema = _arrow_schema(first)
            row_count = 0
            chunk_count = 0
            with pq.ParquetWriter(parquet_tmp, schema=schema, compression="zstd") as writer:
                for frame in chain([first], reader):
                    writer.write_table(_as_arrow(frame, schema))
                    row_count += len(frame)
                    chunk_count += 1
            payload = {
                "source_file": raw.name,
                "source_format": "Stata DTA",
                "source_sha256": _sha256(raw),
                "source_bytes": raw.stat().st_size,
                "rows": row_count,
                "chunks": chunk_count,
                "columns": schema.names,
                "arrow_types": {field.name: str(field.type) for field in schema},
                "variable_labels": variable_labels,
                "value_labels": value_labels,
                "normalization": {
                    "categorical_codes": "Original codes retained; labels stored separately.",
                    "numeric_storage": "Stata numeric storage normalized to float64.",
                    "dates": "Original Stata numeric date values retained.",
                    "missing_values": "Stata ordinary and extended missings become null; no imputation.",
                    "string_keys": "Original strings, including leading zeros, retained.",
                },
            }
            _write_json(metadata_tmp, payload)
        parquet_tmp.replace(parquet)
        metadata_tmp.replace(metadata)
        return payload
    finally:
        parquet_tmp.unlink(missing_ok=True)
        metadata_tmp.unlink(missing_ok=True)


def _json_plain(value: Any) -> Any:
    """Normalize metadata scalar/container types without changing data values."""
    if isinstance(value, dict):
        return {str(key): _json_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_plain(item) for item in value]
    if hasattr(value, "item"):
        return _json_plain(value.item())
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise DataIntegrityError(f"Tipo de metadato no serializable: {type(value).__name__}")


def _spss_missing_to_null(
    frame: Any, missing_ranges: dict[str, Any]
) -> tuple[Any, dict[str, int]]:
    """Normalize only missing ranges explicitly declared in the SPSS file."""
    import pandas as pd

    normalized = frame
    counts = {}
    for name, rules in missing_ranges.items():
        if name not in frame:
            raise DataIntegrityError(f"Los metadatos declaran missing para una columna ausente: {name}")
        series = frame[name]
        mask = pd.Series(False, index=frame.index)
        for rule in rules:
            lower, upper = rule["lo"], rule["hi"]
            if lower == upper:
                mask |= series.eq(lower).fillna(False)
            else:
                mask |= series.between(lower, upper, inclusive="both").fillna(False)
        counts[name] = int(mask.sum())
        if counts[name]:
            if normalized is frame:
                normalized = frame.copy()
            normalized.loc[mask, name] = None
    return normalized, counts


def convert_spss(
    raw_path: str | Path,
    parquet_path: str | Path,
    metadata_path: str | Path,
    *,
    chunk_size: int = 50_000,
    normalize_user_missing: bool = True,
) -> dict[str, Any]:
    """Convert a .sav/.zsav without substituting labels for valid codes.

    Numeric SPSS dates remain numeric and their display formats are recorded.
    System missing values become null. By default, user-defined missing values
    also become null according to the file's own missing_ranges, with counts
    and original rules recorded. No missing value is imputed or made zero.
    Set normalize_user_missing=False to retain the user-missing sentinels.
    No download date is inferred from the file's timestamps or metadata.
    """
    import pandas as pd
    import pyarrow
    import pyarrow.parquet as pq
    import pyreadstat

    raw = Path(raw_path).resolve()
    parquet = Path(parquet_path).resolve()
    metadata = Path(metadata_path).resolve()
    if not raw.is_file():
        raise FileNotFoundError(f"Falta el archivo SPSS: {raw.name}")
    if raw.suffix.lower() not in {".sav", ".zsav"}:
        raise ValueError("La ingesta SPSS requiere un archivo .sav o .zsav.")
    if chunk_size < 1:
        raise ValueError("chunk_size debe ser positivo.")
    if len({raw, parquet, metadata}) != 3:
        raise ValueError("Las rutas de origen, Parquet y metadatos deben ser distintas.")

    parquet_tmp = _temporary_path(parquet)
    metadata_tmp = _temporary_path(metadata)
    try:
        _, source_meta = pyreadstat.read_sav(
            str(raw), metadataonly=True, apply_value_formats=False,
            user_missing=True, disable_datetime_conversion=True,
        )
        missing_ranges = _json_plain(source_meta.missing_ranges or {})
        reader = pyreadstat.read_file_in_chunks(
            pyreadstat.read_sav, str(raw), chunksize=chunk_size,
            apply_value_formats=False, user_missing=True,
            disable_datetime_conversion=True,
        )
        first_pair = next(reader, None)
        if first_pair is None or first_pair[0].empty:
            raise DataIntegrityError("El archivo SPSS no contiene observaciones.")
        schema = _arrow_schema(first_pair[0])
        row_count = 0
        chunk_count = 0
        user_missing_counts = {name: 0 for name in missing_ranges}
        with pq.ParquetWriter(parquet_tmp, schema=schema, compression="zstd") as writer:
            for frame, _ in chain([first_pair], reader):
                if frame.empty:
                    continue
                if normalize_user_missing:
                    frame, counts = _spss_missing_to_null(frame, missing_ranges)
                    for name, count in counts.items():
                        user_missing_counts[name] += count
                writer.write_table(_as_arrow(frame, schema))
                row_count += len(frame)
                chunk_count += 1
        expected_rows = source_meta.number_rows
        if expected_rows is not None and row_count != int(expected_rows):
            raise DataIntegrityError("La conversión SPSS no conservó el número de observaciones del archivo.")
        payload = {
            "source_file": raw.name,
            "source_format": "SPSS SAV",
            "source_sha256": _sha256(raw),
            "source_bytes": raw.stat().st_size,
            "rows": row_count,
            "chunks": chunk_count,
            "columns": schema.names,
            "arrow_types": {field.name: str(field.type) for field in schema},
            "variable_labels": _json_plain(source_meta.column_names_to_labels),
            "value_labels": _json_plain(source_meta.value_labels),
            "variable_value_labels": _json_plain(source_meta.variable_value_labels),
            "variable_to_label": _json_plain(source_meta.variable_to_label),
            "missing_ranges": missing_ranges,
            "normalized_user_missing_counts": user_missing_counts if normalize_user_missing else {},
            "original_variable_types": _json_plain(source_meta.original_variable_types),
            "readstat_variable_types": _json_plain(source_meta.readstat_variable_types),
            "file_encoding": source_meta.file_encoding,
            "file_label": source_meta.file_label,
            "software": {
                "pandas": pd.__version__, "pyarrow": pyarrow.__version__,
                "pyreadstat": pyreadstat.__version__,
            },
            "normalization": {
                "categorical_codes": "Valid original codes retained; labels stored separately.",
                "numeric_storage": "SPSS numeric storage normalized to float64.",
                "dates": "Original SPSS numeric date values retained; formats recorded.",
                "system_missing": "System missing values become null; no imputation.",
                "user_missing": (
                    "Only explicitly declared SPSS missing ranges become null; original rules and counts recorded."
                    if normalize_user_missing else
                    "User-defined missing sentinels retained as source values; rules recorded."
                ),
                "string_keys": "String values and leading zeros retained; empty strings remain unless declared missing.",
            },
        }
        _write_json(metadata_tmp, payload)
        parquet_tmp.replace(parquet)
        metadata_tmp.replace(metadata)
        return payload
    finally:
        parquet_tmp.unlink(missing_ok=True)
        metadata_tmp.unlink(missing_ok=True)


def convert_microdata(
    raw_path: str | Path,
    parquet_path: str | Path,
    metadata_path: str | Path,
    *,
    chunk_size: int = 50_000,
) -> dict[str, Any]:
    """Dispatch supported original survey formats without changing their names."""
    suffix = Path(raw_path).suffix.lower()
    if suffix == ".dta":
        return convert_stata(raw_path, parquet_path, metadata_path, chunk_size=chunk_size)
    if suffix in {".sav", ".zsav"}:
        return convert_spss(raw_path, parquet_path, metadata_path, chunk_size=chunk_size)
    raise ValueError("Formato no admitido: utilice .dta, .sav o .zsav del proveedor de datos.")


def create_analysis_table(
    person_parquet: str | Path,
    housing_parquet: str | Path,
    out_parquet: str | Path,
    audit_json: str | Path,
) -> dict[str, Any]:
    """Create a checked many-to-one person–household table using DuckDB.

    Raises DataIntegrityError for missing/blank keys, duplicate logical keys,
    unmatched households, invalid weights, or a change in person row count.
    No person identifiers or individual records are written to the audit.
    """
    import duckdb

    person = Path(person_parquet).resolve()
    housing = Path(housing_parquet).resolve()
    output = Path(out_parquet).resolve()
    audit = Path(audit_json).resolve()
    if not person.is_file() or not housing.is_file():
        raise FileNotFoundError("Faltan los Parquet de Persona o Vivienda.")
    if output in {person, housing} or audit in {person, housing, output}:
        raise ValueError("Los productos no pueden sobrescribir los archivos de entrada.")
    output_tmp = _temporary_path(output)
    audit_tmp = _temporary_path(audit)
    try:
        with TemporaryDirectory(prefix=".duckdb-ingestion-", dir=output.parent) as spill:
            with duckdb.connect(":memory:") as con:
                con.execute("SET memory_limit = '512MB'")
                con.execute("SET threads = 2")
                con.execute("SET temp_directory = ?", [spill])
                con.read_parquet(str(person)).create_view("persons")
                con.read_parquet(str(housing)).create_view("housing")
                present_person = set(con.table("persons").columns)
                present_housing = set(con.table("housing").columns)
                missing_person = sorted(set(PERSON_COLUMNS) - present_person)
                missing_housing = sorted({"folio", *HOUSING_COLUMNS} - present_housing)
                if missing_person or missing_housing:
                    raise DataIntegrityError(
                        "Faltan columnas verificadas; Persona: " + ", ".join(missing_person)
                        + "; Vivienda: " + ", ".join(missing_housing)
                    )
                person_types = {
                    row[0]: row[1] for row in con.execute("DESCRIBE persons").fetchall()
                }
                housing_types = {
                    row[0]: row[1] for row in con.execute("DESCRIBE housing").fetchall()
                }
                if person_types["folio"] != "VARCHAR" or housing_types["folio"] != "VARCHAR":
                    raise DataIntegrityError(
                        "folio debe conservarse como texto en ambas fuentes; no se permite un cruce por conversión numérica."
                    )

                person_rows = con.execute("SELECT count(*) FROM persons").fetchall()[0][0]
                housing_rows = con.execute("SELECT count(*) FROM housing").fetchall()[0][0]
                if person_rows == 0 or housing_rows == 0:
                    raise DataIntegrityError("No se puede analizar una fuente sin observaciones.")
                bad_person_keys = con.execute("""
                    SELECT count(*) FROM persons WHERE folio IS NULL OR nro IS NULL
                    OR trim(CAST(folio AS VARCHAR)) = ''
                """).fetchall()[0][0]
                bad_housing_keys = con.execute("""
                    SELECT count(*) FROM housing WHERE folio IS NULL
                    OR trim(CAST(folio AS VARCHAR)) = ''
                """).fetchall()[0][0]
                if bad_person_keys or bad_housing_keys:
                    raise DataIntegrityError("Existen claves de Persona o Vivienda vacías/nulas.")
                duplicate_person_keys = con.execute("""
                    SELECT count(*) FROM (
                        SELECT folio, nro FROM persons GROUP BY folio, nro HAVING count(*) > 1
                    )
                """).fetchall()[0][0]
                duplicate_household_keys = con.execute("""
                    SELECT count(*) FROM (
                        SELECT folio FROM housing GROUP BY folio HAVING count(*) > 1
                    )
                """).fetchall()[0][0]
                if duplicate_person_keys or duplicate_household_keys:
                    raise DataIntegrityError(
                        "Claves duplicadas: se rechaza el cruce para evitar multiplicar personas."
                    )
                invalid_weights = con.execute("""
                    SELECT count(*) FROM persons WHERE factor IS NULL
                    OR NOT isfinite(CAST(factor AS DOUBLE)) OR factor <= 0
                """).fetchall()[0][0]
                if invalid_weights:
                    raise DataIntegrityError("Existen factores de expansión nulos, no finitos o no positivos.")
                unmatched = con.execute("""
                    SELECT count(*) FROM persons p LEFT JOIN housing h ON p.folio = h.folio
                    WHERE h.folio IS NULL
                """).fetchall()[0][0]
                if unmatched:
                    raise DataIntegrityError(
                        "Hay personas cuyo hogar no aparece en Vivienda; se requiere revisar la fuente."
                    )

                select_person = ", ".join(f'p."{name}"' for name in PERSON_COLUMNS)
                select_housing = ", ".join(
                    f'h."{name}" AS "hh_{name}"' for name in HOUSING_COLUMNS
                )
                query = (
                    f"SELECT {select_person}, {select_housing} "
                    "FROM persons p LEFT JOIN housing h ON p.folio = h.folio"
                )
                con.sql(query).create_view("analysis")
                joined_rows, joined_weight = con.execute(
                    "SELECT count(*), sum(factor) FROM analysis"
                ).fetchall()[0]
                source_weight = con.execute("SELECT sum(factor) FROM persons").fetchall()[0][0]
                if joined_rows != person_rows or not math.isclose(
                    float(joined_weight), float(source_weight), rel_tol=1e-12, abs_tol=1e-8
                ):
                    raise DataIntegrityError("El cruce cambió el número de personas o la suma de sus pesos.")
                con.table("analysis").write_parquet(str(output_tmp), compression="zstd")
                payload = {
                    "person_source": person.name,
                    "housing_source": housing.name,
                    "person_rows": int(person_rows),
                    "housing_rows": int(housing_rows),
                    "joined_rows": int(joined_rows),
                    "join": "LEFT JOIN many-to-one on folio",
                    "person_key": ["folio", "nro"],
                    "household_key": ["folio"],
                    "null_person_keys": 0,
                    "null_household_keys": 0,
                    "duplicate_person_key_groups": 0,
                    "duplicate_household_key_groups": 0,
                    "unmatched_person_rows": 0,
                    "source_weight_sum": float(source_weight),
                    "joined_weight_sum": float(joined_weight),
                    "row_and_weight_invariance": True,
                    "columns": con.table("analysis").columns,
                }
                _write_json(audit_tmp, payload)
        output_tmp.replace(output)
        audit_tmp.replace(audit)
        return payload
    finally:
        output_tmp.unlink(missing_ok=True)
        audit_tmp.unlink(missing_ok=True)
