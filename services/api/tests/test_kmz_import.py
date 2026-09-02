"""KMZ preview, safety and idempotent import integration tests."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.database import SessionLocal
from app.models.map_feature import MapFeature

KML = b"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Style id="cto-blue">
      <IconStyle><Icon><href>cto_0000ff.png</href></Icon></IconStyle>
    </Style>
    <Style id="cable-magenta">
      <LineStyle><color>ffea41ea</color><width>3</width></LineStyle>
    </Style>
    <Folder><name>Rede teste</name>
      <Placemark id="cto-001">
        <name>CTO 001</name><styleUrl>#cto-blue</styleUrl>
        <Point><coordinates>-46.42,-24.01,0</coordinates></Point>
      </Placemark>
      <Placemark id="ceo-001">
        <name>CEO 001</name>
        <Point><coordinates>-46.421,-24.011,0</coordinates></Point>
      </Placemark>
      <Placemark id="cable-001">
        <name>Cabo 12FO</name><styleUrl>#cable-magenta</styleUrl>
        <LineString><coordinates>-46.42,-24.01,0 -46.421,-24.011,0</coordinates></LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""


def kmz_file(kml: bytes = KML, member: str = "doc.kml") -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(member, kml)
    return output.getvalue()


def upload_payload(content: bytes | None = None):
    return {
        "files": {
            "file": ("rede-teste.kmz", content or kmz_file(), "application/vnd.google-earth.kmz")
        },
        "data": {"source_namespace": "rede-teste", "default_status": "active"},
    }


def test_viewer_cannot_preview_or_import_kmz(client, viewer_headers):
    payload = upload_payload()
    assert (
        client.post("/api/v1/imports/kmz/preview", headers=viewer_headers, **payload).status_code
        == 403
    )
    assert client.get("/api/v1/imports/kmz/export", headers=viewer_headers).status_code == 403


def test_admin_previews_and_imports_kmz_idempotently(client, admin_headers):
    preview = client.post("/api/v1/imports/kmz/preview", headers=admin_headers, **upload_payload())
    assert preview.status_code == 200, preview.text
    summary = preview.json()
    assert summary["feature_count"] == 3
    assert summary["new_count"] == 3
    assert summary["geometry_counts"] == {"LineString": 1, "Point": 2}
    assert summary["type_counts"] == {"cable": 1, "cto": 1, "splice_box": 1}
    assert summary["bounds"] == [-46.421, -24.011, -46.42, -24.01]

    imported = client.post("/api/v1/imports/kmz", headers=admin_headers, **upload_payload())
    assert imported.status_code == 201, imported.text
    result = imported.json()
    assert result["created_count"] == 3
    assert result["updated_count"] == 0
    assert result["already_imported"] is False

    repeated = client.post("/api/v1/imports/kmz", headers=admin_headers, **upload_payload())
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["already_imported"] is True

    second_preview = client.post(
        "/api/v1/imports/kmz/preview", headers=admin_headers, **upload_payload()
    ).json()
    assert second_preview["new_count"] == 0
    assert second_preview["update_count"] == 3
    assert second_preview["already_imported"] is True

    with SessionLocal() as db:
        assert db.query(MapFeature).count() == 3
        cable = db.query(MapFeature).filter(MapFeature.source_ref == "cable-001").one()
        assert cable.properties["kml_style"]["line_color"] == "#ea41ea"
        assert cable.status == "active"

    history = client.get("/api/v1/imports", headers=admin_headers)
    assert history.status_code == 200
    assert len(history.json()) == 1

    exported = client.get("/api/v1/imports/kmz/export", headers=admin_headers)
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"] == "application/vnd.google-earth.kmz"
    assert exported.headers["x-feature-count"] == "3"
    assert exported.headers["content-disposition"].endswith('.kmz"')
    with ZipFile(BytesIO(exported.content)) as archive:
        assert archive.namelist() == ["doc.kml"]
        exported_kml = archive.read("doc.kml")
    assert b"CTO 001" in exported_kml
    assert b"Cabo 12FO" in exported_kml
    assert b"LineString" in exported_kml


def test_import_rejects_unsafe_or_invalid_archives(client, admin_headers):
    unsafe = client.post(
        "/api/v1/imports/kmz/preview",
        headers=admin_headers,
        **upload_payload(kmz_file(member="../doc.kml")),
    )
    assert unsafe.status_code == 422
    assert "unsafe archive path" in unsafe.json()["detail"]

    invalid = client.post(
        "/api/v1/imports/kmz/preview",
        headers=admin_headers,
        files={"file": ("invalid.kmz", b"not-a-zip", "application/octet-stream")},
        data={"source_namespace": "invalid", "default_status": "planned"},
    )
    assert invalid.status_code == 422
