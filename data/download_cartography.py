"""Reproduce the licensed Bolivia ADM1 layer used by the EH2025 project.

The default uses the cached provider metadata and a commit-pinned GeoJSON.
Missing cached inputs are downloaded from their public primary sources. The
source SHA-256 is fixed, so a changed remote file cannot silently replace the
reviewed cartography. Geometry coordinates are not repaired or re-simplified.

Run from the project root with a Python environment containing Shapely:
    python data/download_cartography.py
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
import unicodedata
import urllib.request
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://www.geoboundaries.org/api/current/gbOpen/BOL/ADM1/"
BOUNDARY_ID = "BOL-ADM1-26024454"
SOURCE_COMMIT = "9469f09592ced973a3448cf66b6100b741b64c0d"
SOURCE_URL = (
    "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/"
    + SOURCE_COMMIT
    + "/releaseData/gbOpen/BOL/ADM1/geoBoundaries-BOL-ADM1_simplified.geojson"
)
SOURCE_SHA256 = "8bb31745f9e9fcf06cff7a423ebdc9934dc7d4c0d925856a7efb237f9fb915da"
PROVIDER_LICENSE_URL = "https://www.geoboundaries.org/index.html#usage"
CC_BY_URL = "https://creativecommons.org/licenses/by/4.0/"
API_DOCUMENTATION_URL = "https://www.geoboundaries.org/api.html"
INE_CODEBOOK_URL = "https://anda.ine.gob.bo/index.php/catalog/256/variable/F27/V1956?name=depto"
DEPARTMENTS = {
    1: "Chuquisaca", 2: "La Paz", 3: "Cochabamba", 4: "Oruro",
    5: "Potosí", 6: "Tarija", 7: "Santa Cruz", 8: "Beni", 9: "Pando",
}
ATTRIBUTION = (
    "Cartografía referencial: GeoBolivia, datos de 2015, distribuida por "
    "geoBoundaries gbOpen (CC BY 4.0). Origen declarado Public Domain en los "
    "metadatos de geoBoundaries. Se añadieron códigos departamentales del INE "
    "y nombres normalizados; no se modificaron las geometrías. "
    "https://www.geoboundaries.org/"
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(prefix=f".{path.name}-", dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        handle.write(content)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _cached_or_download(path: Path, url: str) -> tuple[bytes, bool]:
    if path.exists():
        return path.read_bytes(), False
    request = urllib.request.Request(
        url, headers={"User-Agent": "EH2025 academic cartography reproducibility"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        content = response.read()
    if not content:
        raise ValueError(f"La fuente devolvió un archivo vacío: {url}")
    _atomic_write(path, content)
    return content, True


def _normal_name(value: str) -> str:
    value = "".join(
        character for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return " ".join(value.upper().replace("DEPARTAMENTO DE ", "").split())


def normalize_and_validate(source: dict) -> tuple[dict, dict]:
    """Require nine named, valid polygonal features and add INE join codes."""
    from shapely.geometry import shape
    from shapely.validation import explain_validity
    import shapely

    if source.get("type") != "FeatureCollection" or len(source.get("features", [])) != 9:
        raise ValueError("La cartografía debe contener exactamente nueve departamentos.")
    name_to_code = {_normal_name(name): code for code, name in DEPARTMENTS.items()}
    name_to_code["EL BENI"] = 8
    result_features = []
    geometries = []
    seen = set()
    per_department = []
    for feature in source["features"]:
        original_properties = feature.get("properties", {})
        original_name = original_properties.get("shapeName")
        code = name_to_code.get(_normal_name(str(original_name)))
        if code is None or code in seen:
            raise ValueError("Nombre departamental no reconocido o repetido en la fuente.")
        if original_properties.get("shapeGroup") != "BOL":
            raise ValueError("La fuente contiene una geometría que no está identificada como Bolivia.")
        if original_properties.get("shapeType") != "ADM1":
            raise ValueError("La fuente contiene un nivel administrativo diferente de ADM1.")
        geometry = shape(feature.get("geometry"))
        if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"La geometría de {DEPARTMENTS[code]} no es poligonal.")
        if geometry.is_empty or not geometry.is_valid or geometry.area <= 0:
            raise ValueError(
                f"Geometría no válida para {DEPARTMENTS[code]}: {explain_validity(geometry)}"
            )
        west, south, east, north = geometry.bounds
        if not all(math.isfinite(value) for value in geometry.bounds):
            raise ValueError("La fuente contiene coordenadas no finitas.")
        # Broad geographic plausibility limits; not a legal boundary test.
        if not (-70 <= west < east <= -56 and -24 <= south < north <= -9):
            raise ValueError(f"Extensión geográfica inesperada para {DEPARTMENTS[code]}.")
        normalized = dict(feature)
        normalized["id"] = str(code)
        normalized["properties"] = {
            **original_properties,
            "depto": code,
            "nombre": DEPARTMENTS[code],
        }
        # Preserve the provider's geometry object unchanged.
        normalized["geometry"] = feature["geometry"]
        result_features.append(normalized)
        geometries.append(geometry)
        seen.add(code)
        per_department.append({
            "depto": code, "nombre": DEPARTMENTS[code],
            "geometry_type": geometry.geom_type,
            "bounds_lonlat": list(geometry.bounds), "is_valid": True,
        })
    if seen != set(DEPARTMENTS):
        raise ValueError("No están presentes los nueve códigos departamentales 1–9.")
    bounds = [
        min(geometry.bounds[0] for geometry in geometries),
        min(geometry.bounds[1] for geometry in geometries),
        max(geometry.bounds[2] for geometry in geometries),
        max(geometry.bounds[3] for geometry in geometries),
    ]
    result = {
        "type": "FeatureCollection",
        "name": "Bolivia departamentos para enlace con EH2025",
        "bbox": bounds,
        "attribution": ATTRIBUTION,
        "license": "CC BY 4.0 (geoBoundaries gbOpen); upstream Public Domain per provider metadata",
        "features": sorted(result_features, key=lambda feature: feature["properties"]["depto"]),
    }
    validation = {
        "feature_count": len(result_features),
        "unique_department_codes": sorted(seen),
        "all_geometries_valid": True,
        "all_geometries_nonempty": True,
        "geometry_types": dict(Counter(geometry.geom_type for geometry in geometries)),
        "bounds_lonlat": bounds,
        "coordinate_interpretation": "GeoJSON longitude/latitude; geographic bounds checked.",
        "geometry_coordinates_changed": False,
        "geometry_repairs_performed": False,
        "department_code_source": INE_CODEBOOK_URL,
        "per_department": sorted(per_department, key=lambda record: record["depto"]),
        "validation_software": {"shapely": shapely.__version__},
    }
    return result, validation


def _update_manifest(cartography_fields: dict) -> dict:
    path = ROOT / "data/source_manifest.json"
    if any(not key.startswith("cartography_") for key in cartography_fields):
        raise ValueError("Solo pueden modificarse campos cartográficos del manifiesto.")
    current = json.loads(path.read_text(encoding="utf-8"))
    original_noncart = {key: value for key, value in current.items() if not key.startswith("cartography_")}
    updated = {**current, **cartography_fields}
    final_noncart = {key: value for key, value in updated.items() if not key.startswith("cartography_")}
    if final_noncart != original_noncart:
        raise AssertionError("Se intentó modificar un campo de procedencia no cartográfico.")
    _atomic_write(path, _json_bytes(updated))
    return {
        "noncartography_fields_preserved": True,
        "noncartography_fields_sha256": _sha256(
            json.dumps(original_noncart, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ),
        "cartography_fields_written": sorted(cartography_fields),
    }


def main() -> None:
    metadata_dir = ROOT / "data/metadata"
    api_path = metadata_dir / "cartography_api_response.json"
    raw_path = metadata_dir / "cartography_source_original.geojson"
    api_bytes, api_downloaded = _cached_or_download(api_path, API_URL)
    api = json.loads(api_bytes)
    if (
        api.get("boundaryID") != BOUNDARY_ID
        or api.get("boundaryISO") != "BOL"
        or api.get("boundaryType") != "ADM1"
        or int(api.get("admUnitCount", 0)) != 9
    ):
        raise ValueError("El recurso del proveedor cambió; se requiere revisar su versión antes de sustituirlo.")
    if api.get("boundaryLicense") != "Public Domain":
        raise ValueError("La licencia de origen difiere de la revisada; no se asumirá un permiso nuevo.")
    raw_bytes, source_downloaded = _cached_or_download(raw_path, SOURCE_URL)
    if _sha256(raw_bytes) != SOURCE_SHA256:
        raise ValueError("El GeoJSON no coincide con el SHA-256 de la versión revisada.")
    normalized, validation = normalize_and_validate(json.loads(raw_bytes))
    normalized_bytes = _json_bytes(normalized)
    output = ROOT / "data/bolivia_departamentos.geojson"
    _atomic_write(output, normalized_bytes)
    now = datetime.now(timezone.utc)
    access_date = now.astimezone(ZoneInfo("America/La_Paz")).date().isoformat()
    fields = {
        "cartography_source": SOURCE_URL,
        "cartography_license": "CC BY 4.0 (geoBoundaries gbOpen); upstream Public Domain per API metadata",
        "cartography_api_url": API_URL,
        "cartography_boundary_id": BOUNDARY_ID,
        "cartography_year_represented": str(api["boundaryYearRepresented"]),
        "cartography_access_date": access_date,
        "cartography_geojson_path": "data/bolivia_departamentos.geojson",
        "cartography_metadata_path": "data/metadata/cartography_source.json",
        "cartography_attribution": ATTRIBUTION,
        "cartography_sha256": _sha256(normalized_bytes),
    }
    manifest_report = _update_manifest(fields)
    metadata = {
        "provider": "geoBoundaries gbOpen / William & Mary geoLab",
        "upstream_source": api["boundarySource"],
        "api_url": API_URL,
        "api_snapshot_file": "data/metadata/cartography_api_response.json",
        "api_snapshot_sha256": _sha256(api_bytes),
        "boundary_id": BOUNDARY_ID,
        "boundary_year_represented": api["boundaryYearRepresented"],
        "source_data_update_date": api["sourceDataUpdateDate"],
        "provider_build_date": api["buildDate"],
        "git_commit": SOURCE_COMMIT,
        "api_declared_download_url": api["simplifiedGeometryGeoJSON"],
        "resolved_commit_pinned_download_url": SOURCE_URL,
        "source_geometry_variant": "Provider's simplified GeoJSON",
        "raw_source_file": "data/metadata/cartography_source_original.geojson",
        "raw_source_sha256": _sha256(raw_bytes),
        "normalized_geojson_file": fields["cartography_geojson_path"],
        "normalized_geojson_sha256": fields["cartography_sha256"],
        "review_and_build_date": access_date,
        "review_and_build_at_utc": now.isoformat(),
        "downloaded_during_this_execution": {"api": api_downloaded, "geometry": source_downloaded},
        "upstream_license": {
            "name": api["boundaryLicense"], "detail": api["licenseDetail"],
            "source_url_as_recorded_by_provider": api["licenseSource"],
            "verification_scope": (
                "Public Domain is the upstream license recorded in the primary geoBoundaries API. "
                "The original GeoBolivia metadata URL was not reachable during this review."
            ),
        },
        "distribution_license": {
            "name": "Creative Commons Attribution 4.0 International",
            "spdx": "CC-BY-4.0", "license_url": CC_BY_URL,
            "provider_license_statement_url": PROVIDER_LICENSE_URL,
            "api_license_documentation_url": API_DOCUMENTATION_URL,
            "attribution_required": True,
        },
        "attribution": ATTRIBUTION,
        "recommended_citation": (
            "Runfola, D., et al. (2020). geoBoundaries: A global database of political "
            "administrative boundaries. PLoS ONE, 15(4), e0231866. "
            "https://doi.org/10.1371/journal.pone.0231866"
        ),
        "transformations": [
            "Selected the provider's pre-simplified ADM1 geometry pinned to the documented commit.",
            "Matched source department names to INE EH2025 depto codes 1–9.",
            "Added properties.depto, properties.nombre and string feature.id; sorted by code.",
            "Preserved all source geometry coordinates and original shape properties.",
        ],
        "scope": (
            "Reference layer for locating nine departments. Geometry year is 2015; it is not "
            "an INE 2025 boundary certification, a source of EH2025 indicators or a basis for "
            "municipal estimates or legal boundary claims."
        ),
        "validation": validation,
        "source_manifest_update": manifest_report,
    }
    _atomic_write(metadata_dir / "cartography_source.json", _json_bytes(metadata))
    print(json.dumps({
        "output": str(output), "feature_count": validation["feature_count"],
        "codes": validation["unique_department_codes"],
        "all_geometries_valid": validation["all_geometries_valid"],
        "geometry_types": validation["geometry_types"],
        "bounds_lonlat": validation["bounds_lonlat"],
        "noncartography_fields_preserved": manifest_report["noncartography_fields_preserved"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
