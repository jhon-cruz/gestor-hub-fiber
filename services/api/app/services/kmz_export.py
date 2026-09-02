"""Deterministic KMZ export for the current geographic inventory."""

import json
from io import BytesIO
from typing import Any
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

KML_NAMESPACE = "http://www.opengis.net/kml/2.2"
ElementTree.register_namespace("", KML_NAMESPACE)


def _element(parent, tag_name: str, text: Any | None = None, **attributes):
    item = ElementTree.SubElement(parent, f"{{{KML_NAMESPACE}}}{tag_name}", attributes)
    if text is not None:
        item.text = str(text)
    return item


def _coordinate(value: list[float]) -> str:
    coordinates = [f"{float(value[0]):.7f}", f"{float(value[1]):.7f}"]
    if len(value) > 2:
        coordinates.append(f"{float(value[2]):.2f}")
    return ",".join(coordinates)


def _coordinates(values: list[list[float]]) -> str:
    return " ".join(_coordinate(value) for value in values)


def _kml_color(hex_color: str | None, alpha: str = "ff") -> str:
    value = (hex_color or "#008fff").lstrip("#")
    if len(value) != 6 or any(character not in "0123456789abcdefABCDEF" for character in value):
        value = "008fff"
    red, green, blue = value[0:2], value[2:4], value[4:6]
    return f"{alpha}{blue}{green}{red}".lower()


def _append_geometry(parent, geometry: dict[str, Any]) -> None:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point" and isinstance(coordinates, list):
        point = _element(parent, "Point")
        _element(point, "coordinates", _coordinate(coordinates))
    elif geometry_type == "LineString" and isinstance(coordinates, list):
        line = _element(parent, "LineString")
        _element(line, "tessellate", "1")
        _element(line, "coordinates", _coordinates(coordinates))
    elif geometry_type == "Polygon" and isinstance(coordinates, list) and coordinates:
        polygon = _element(parent, "Polygon")
        outer = _element(polygon, "outerBoundaryIs")
        ring = _element(outer, "LinearRing")
        _element(ring, "coordinates", _coordinates(coordinates[0]))
        for inner_coordinates in coordinates[1:]:
            inner = _element(polygon, "innerBoundaryIs")
            inner_ring = _element(inner, "LinearRing")
            _element(inner_ring, "coordinates", _coordinates(inner_coordinates))
    elif geometry_type in {"MultiPoint", "MultiLineString", "MultiPolygon"}:
        multi = _element(parent, "MultiGeometry")
        child_type = geometry_type.removeprefix("Multi")
        for child_coordinates in coordinates or []:
            _append_geometry(multi, {"type": child_type, "coordinates": child_coordinates})
    elif geometry_type == "GeometryCollection":
        multi = _element(parent, "MultiGeometry")
        for child in geometry.get("geometries", []):
            _append_geometry(multi, child)


def _append_style(placemark, geometry: dict[str, Any], properties: dict[str, Any]) -> None:
    style_data = properties.get("kml_style")
    style_data = style_data if isinstance(style_data, dict) else {}
    color = style_data.get("line_color") or style_data.get("icon_color") or "#008fff"
    style = _element(placemark, "Style")
    if geometry.get("type") in {"LineString", "MultiLineString"}:
        line_style = _element(style, "LineStyle")
        _element(line_style, "color", _kml_color(color))
        _element(line_style, "width", style_data.get("line_width") or "3")
    elif geometry.get("type") in {"Polygon", "MultiPolygon"}:
        line_style = _element(style, "LineStyle")
        _element(line_style, "color", _kml_color(color))
        _element(line_style, "width", style_data.get("line_width") or "2")
        polygon_style = _element(style, "PolyStyle")
        _element(polygon_style, "color", _kml_color(color, "55"))
    else:
        icon_style = _element(style, "IconStyle")
        _element(icon_style, "color", _kml_color(color))
        _element(icon_style, "scale", "1.1")


def build_kmz(features: list[dict[str, Any]], document_name: str) -> bytes:
    """Serialize GeoJSON-backed features as a standards-compatible KMZ archive."""

    root = ElementTree.Element(f"{{{KML_NAMESPACE}}}kml")
    document = _element(root, "Document")
    _element(document, "name", document_name)
    _element(document, "description", "Exportado pelo Gestor Hub Fiber")

    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        placemark = _element(document, "Placemark", id=str(feature["id"]))
        _element(placemark, "name", properties.get("name") or "Elemento sem nome")
        description = properties.get("description") or properties.get("notes")
        if description:
            _element(placemark, "description", description)
        _append_style(placemark, geometry, properties)
        extended = _element(placemark, "ExtendedData")
        fields = {
            "gestor_hub_id": feature["id"],
            "tipo": properties.get("feature_type"),
            "status": properties.get("status"),
            "fibras": properties.get("fiber_count", properties.get("capacity")),
            "origem": properties.get("source_namespace"),
            "pasta": properties.get("folder_path"),
        }
        for key, value in fields.items():
            if value is None or value == "":
                continue
            data = _element(extended, "Data", name=key)
            _element(data, "value", value if isinstance(value, str) else json.dumps(value))
        _append_geometry(placemark, geometry)

    kml_content = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("doc.kml", kml_content)
    return output.getvalue()
