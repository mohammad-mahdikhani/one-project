from pathlib import Path

from ste.importer import read_pdf, read_upload, write_xlsx
from ste.matcher import match_rows
from ste.site_seed import SITE_PRODUCTS

PDF = Path("/home/ubuntu/.cursor/projects/workspace/uploads/_____________________12_____1__3f01.pdf")


def test_read_aquajoy_pdf():
    rows = read_pdf(PDF.read_bytes())
    assert len(rows) >= 200
    first = next(item for item in rows if item.sku == "01103008")
    assert "تصفیه آب" in first.name
    assert first.price == 132000000
    elite = next(item for item in rows if item.sku == "01105512")
    assert elite.price == 546000000


def test_xlsx_roundtrip_and_site_matching(tmp_path):
    rows = read_pdf(PDF.read_bytes())
    data = write_xlsx(rows, tmp_path / "aquajoy.xlsx")
    parsed = read_upload("aquajoy.xlsx", data)
    assert len(parsed) == len(rows)
    results = match_rows(parsed, list(SITE_PRODUCTS))
    updates = [item for item in results if item.action == "update"]
    missing = [item for item in results if item.action == "create"]
    assert len(updates) >= 8
    assert any(item.sheet.sku == "01103008" for item in updates)
    assert any("AJ-3500" in item.sheet.name or "3500" in item.sheet.name for item in missing)
