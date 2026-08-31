"""Safe, deterministic KMZ/KML parsing for administrator-reviewed imports."""

import hashlib
import math
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from defusedxml import ElementTree

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 100
MAX_FEATURES = 5_000
ALLOWED_STATUSES = {
    "planned",
    "under_construction",
    "active",
    "reserved",
    "damaged",
    "deactivated",
}


class KmzValidationError(ValueError):
    """Raised when an uploaded archive is unsafe or unsupported."""


@dataclass(slots=True)
class ParsedFeature:
    source_ref: str
    name: str
    feature_type: str
    status: str
    geometry: dict[str, Any]
    properties: dict[str, Any]


@dataclass(slots=True)
class ParsedKmz:
    filename: str
    source_namespace: str
    file_sha256: str
    features: list[ParsedFeature]
    warnings: list[dict[str, str]] = field(default_factory=list)
    bounds: list[float] | None = None

    def preview(self, existing_refs: set[str]) -> dict[str, Any]:
        type_counts = Counter(feature.feature_type for feature in self.features)
        geometry_counts = Counter(feature.geometry["type"] for feature in self.features)
        status_counts = Counter(feature.status for feature in self.features)
        updating = sum(feature.source_ref in existing_refs for feature in self.features)
        return {
            "filename": self.filename,
            "source_namespace": self.source_namespace,
            "file_sha256": self.file_sha256,
            "feature_count": len(self.features),
            "new_count": len(self.features) - updating,
            "update_count": updating,
            "type_counts": dict(sorted(type_counts.items())),
            "geometry_counts": dict(sorted(geometry_counts.items())),
            "status_counts": dict(sorted(status_counts.items())),
            "bounds": self.bounds,
            "warnings": self.warnings,
            "sample": [
                {
                    "source_ref": feature.source_ref,
                    "name": feature.name,
                    "feature_type": feature.feature_type,
                    "geometry_type": feature.geometry["type"],
                }
                for feature in self.features[:12]
            ],
        }


def normalize_namespace(value: str | None, filename: str) -> str:
    candidate = (value or PurePosixPath(filename).stem).strip().lower()
    candidate = re.sub(r"[^a-z0-9._-]+", "-", candidate).strip("-._")
    if not candidate:
        raise KmzValidationError("source namespace is empty")
    return candidate[:120]


def parse_kmz(
    content: bytes,
    *,
    filename: str,
    source_namespace: str | None,
    default_status: str,
) -> ParsedKmz:
    if len(content) > MAX_UPLOAD_BYTES:
        raise KmzValidationError("KMZ exceeds the 20 MB upload limit")
    if not content:
        raise KmzValidationError("KMZ file is empty")
    if default_status not in ALLOWED_STATUSES:
        raise KmzValidationError("unsupported default status")
    if not zipfile.is_zipfile(BytesIO(content)):
        raise KmzValidationError("file is not a valid KMZ/ZIP archive")

    with zipfile.ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise KmzValidationError("KMZ contains too many archive entries")
        total_size = sum(entry.file_size for entry in entries)
        if total_size > MAX_UNCOMPRESSED_BYTES:
            raise KmzValidationError("KMZ uncompressed content exceeds 50 MB")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts:
                raise KmzValidationError("KMZ contains an unsafe archive path")
            if entry.flag_bits & 0x1:
                raise KmzValidationError("encrypted KMZ files are not supported")
            if entry.compress_size and entry.file_size > 1_000_000:
                if entry.file_size / entry.compress_size > 200:
                    raise KmzValidationError("KMZ has an unsafe compression ratio")

        kml_entries = [entry for entry in entries if entry.filename.lower().endswith(".kml")]
        if not kml_entries:
            raise KmzValidationError("KMZ does not contain a KML document")
        selected = next(
            (
                entry
                for entry in kml_entries
                if PurePosixPath(entry.filename).name.lower() == "doc.kml"
            ),
            kml_entries[0],
        )
        kml_content = archive.read(selected)

    try:
        root = ElementTree.fromstring(kml_content)
    except Exception as exc:
        raise KmzValidationError("KML XML is malformed or contains forbidden entities") from exc

    namespace = normalize_namespace(source_namespace, filename)
    styles = _read_styles(root)
    warnings: list[dict[str, str]] = []
    parsed: list[ParsedFeature] = []
    _walk_kml(root, [], styles, default_status, parsed, warnings)
    if not parsed:
        raise KmzValidationError("KML does not contain supported geographic features")
    if len(parsed) > MAX_FEATURES:
        raise KmzValidationError(f"KML exceeds the {MAX_FEATURES} feature limit")

    refs = [feature.source_ref for feature in parsed]
    if len(refs) != len(set(refs)):
        raise KmzValidationError("KML contains duplicate Placemark IDs")

    return ParsedKmz(
        filename=PurePosixPath(filename).name[:255],
        source_namespace=namespace,
        file_sha256=hashlib.sha256(content).hexdigest(),
        features=parsed,
        warnings=warnings[:100],
        bounds=_calculate_bounds(parsed),
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct_text(element, name: str) -> str:
    for child in element:
        if _local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _descendant(element, name: str):
    return next((child for child in element.iter() if _local_name(child.tag) == name), None)


def _read_styles(root) -> dict[str, dict[str, str]]:
    styles: dict[str, dict[str, str]] = {}
    for element in root.iter():
        if _local_name(element.tag) != "Style" or not element.attrib.get("id"):
            continue
        icon_style = _descendant(element, "IconStyle")
        line_style = _descendant(element, "LineStyle")
        icon_href = ""
        if icon_style is not None:
            href_element = _descendant(icon_style, "href")
            icon_href = (href_element.text or "").strip() if href_element is not None else ""
        line_color = _direct_text(line_style, "color") if line_style is not None else ""
        line_width = _direct_text(line_style, "width") if line_style is not None else ""
        icon_color_match = re.search(r"_([0-9a-fA-F]{6})(?:\.[^.]+)?$", icon_href)
        styles[element.attrib["id"]] = {
            "icon_href": PurePosixPath(icon_href).name if icon_href else "",
            "icon_color": f"#{icon_color_match.group(1).lower()}" if icon_color_match else "",
            "line_color_kml": line_color,
            "line_color": _kml_color_to_hex(line_color),
            "line_width": line_width,
        }
    return styles


def _walk_kml(
    element,
    folders: list[str],
    styles: dict[str, dict[str, str]],
    default_status: str,
    parsed: list[ParsedFeature],
    warnings: list[dict[str, str]],
) -> None:
    local = _local_name(element.tag)
    next_folders = folders
    if local == "Folder":
        folder_name = _direct_text(element, "name")
        if folder_name:
            next_folders = [*folders, folder_name]
    if local == "Placemark":
        feature = _parse_placemark(element, next_folders, styles, default_status, warnings)
        if feature is not None:
            parsed.append(feature)
        return
    for child in element:
        _walk_kml(child, next_folders, styles, default_status, parsed, warnings)


def _parse_placemark(
    element,
    folders: list[str],
    styles: dict[str, dict[str, str]],
    default_status: str,
    warnings: list[dict[str, str]],
) -> ParsedFeature | None:
    raw_name = _direct_text(element, "name") or "Elemento sem nome"
    source_ref = (
        element.attrib.get("id")
        or hashlib.sha256(f"{'/'.join(folders)}:{raw_name}".encode()).hexdigest()[:32]
    )
    if len(source_ref) > 160:
        source_ref = hashlib.sha256(source_ref.encode()).hexdigest()
    name = raw_name[:160]
    if len(raw_name) > 160:
        warnings.append({"code": "name_truncated", "message": f"Name truncated: {raw_name[:60]}"})

    geometry_elements = [
        child
        for child in element.iter()
        if _local_name(child.tag) in {"Point", "LineString", "Polygon"}
    ]
    if len(geometry_elements) != 1:
        warnings.append(
            {
                "code": "unsupported_geometry",
                "message": f"Skipped {name}: expected one Point, LineString or Polygon",
            }
        )
        return None
    try:
        geometry = _parse_geometry(geometry_elements[0])
    except KmzValidationError as exc:
        warnings.append({"code": "invalid_geometry", "message": f"Skipped {name}: {exc}"})
        return None

    style_ref = _direct_text(element, "styleUrl").removeprefix("#")
    style = styles.get(style_ref, {})
    icon_name = style.get("icon_href", "")
    feature_type = _infer_feature_type(name, geometry["type"], icon_name)
    description = _direct_text(element, "description")[:20_000]
    properties: dict[str, Any] = {
        "source": "kmz",
        "source_ref": source_ref,
        "folder_path": folders,
        "original_name": raw_name,
        "kml_style": style,
    }
    if description:
        properties["description"] = description
    return ParsedFeature(
        source_ref=source_ref,
        name=name,
        feature_type=feature_type,
        status=default_status,
        geometry=geometry,
        properties=properties,
    )


def _parse_geometry(element) -> dict[str, Any]:
    geometry_type = _local_name(element.tag)
    coordinates_element = _descendant(element, "coordinates")
    if coordinates_element is None or not coordinates_element.text:
        raise KmzValidationError("geometry has no coordinates")
    coordinates = [_parse_tuple(value) for value in coordinates_element.text.split()]
    if geometry_type == "Point":
        if not coordinates:
            raise KmzValidationError("Point is empty")
        return {"type": "Point", "coordinates": coordinates[0]}
    if geometry_type == "LineString":
        if len(coordinates) < 2:
            raise KmzValidationError("LineString needs at least two coordinates")
        return {"type": "LineString", "coordinates": coordinates}
    if geometry_type == "Polygon":
        if len(coordinates) < 4:
            raise KmzValidationError("Polygon needs a closed ring")
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        return {"type": "Polygon", "coordinates": [coordinates]}
    raise KmzValidationError("unsupported geometry")


def _parse_tuple(value: str) -> list[float]:
    parts = value.split(",")
    if len(parts) < 2:
        raise KmzValidationError("invalid coordinate tuple")
    try:
        longitude, latitude = float(parts[0]), float(parts[1])
    except ValueError as exc:
        raise KmzValidationError("coordinate is not numeric") from exc
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise KmzValidationError("coordinate is not finite")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise KmzValidationError("coordinate is outside WGS84 bounds")
    return [longitude, latitude]


def _infer_feature_type(name: str, geometry_type: str, icon_name: str) -> str:
    if geometry_type in {"LineString", "Polygon"}:
        return "cable" if geometry_type == "LineString" else "area"
    source = f"{icon_name} {name}".lower()
    if "cto" in source:
        return "cto"
    if "ceo" in source or "emenda" in source:
        return "splice_box"
    if "olt" in source:
        return "olt"
    if "dio" in source:
        return "dio"
    if "splitter" in source:
        return "splitter"
    if "poste" in source:
        return "pole"
    return "other"


def _kml_color_to_hex(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{8}", value):
        return ""
    return f"#{value[6:8]}{value[4:6]}{value[2:4]}".lower()


def _calculate_bounds(features: list[ParsedFeature]) -> list[float] | None:
    points: list[list[float]] = []
    for feature in features:
        geometry = feature.geometry
        if geometry["type"] == "Point":
            points.append(geometry["coordinates"])
        elif geometry["type"] == "LineString":
            points.extend(geometry["coordinates"])
        elif geometry["type"] == "Polygon":
            points.extend(geometry["coordinates"][0])
    if not points:
        return None
    return [
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    ]
