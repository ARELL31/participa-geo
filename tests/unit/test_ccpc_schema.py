"""Unit tests for CCPC CSV schema validation in ``read_ccpc``.

The source must fail closed on any deviation from the exact 16-column allowlist,
non-negative integer counts, the ``LN = SV + NV + NS`` identity, year/entity,
section type, sex and age constraints. ``DEL`` (and ``DEF``, blank in 2009/2012)
are retained as ``None`` — never invented.
"""

from __future__ import annotations

import pytest

from participa_geo.ingestion.schema import CCPCSchemaError
from participa_geo.ingestion.source import read_ccpc

HEADER = (
    "AELEC,FELECCION,EDOCVE,EDONOM,MPIOCVE,MPIONOM,"
    "SECCION,TIPOSEC,DEF,DEL,SEXO,EDAD,LN,SV,NV,NS"
)


def _write(tmp_path, header: str, *rows: str, encoding: str = "utf-8") -> object:
    path = tmp_path / "jalisco-2024.csv"
    lines = [header, *rows]
    path.write_text("\n".join(lines) + "\n", encoding=encoding)
    return path


def _row(
    aelec: str = "2024",
    edocve: str = "14",
    mpiocve: str = "1",
    tiposec: str = "U",
    def_: str = "1",
    del_: str = "2",
    sexo: str = "0",
    edad: str = "30",
    ln: str = "100",
    sv: str = "40",
    nv: str = "40",
    ns: str = "20",
    seccion: str = "1",
) -> str:
    return ",".join(
        [
            aelec,
            "2/6/2024",
            edocve,
            "JALISCO",
            mpiocve,
            "Acatic",
            seccion,
            tiposec,
            def_,
            del_,
            sexo,
            edad,
            ln,
            sv,
            nv,
            ns,
        ]
    )


def test_parse_valid_row(tmp_path):
    path = _write(tmp_path, HEADER, _row())
    rows = list(read_ccpc(path, expected_year=2024))
    assert len(rows) == 1
    row = rows[0]
    assert row.year == 2024
    assert row.state_code == "14"
    assert row.municipality_code == "001"
    assert row.ln == 100 and row.sv == 40 and row.nv == 40 and row.ns == 20
    assert row.local_district == 2
    assert row.federal_district == 1


def test_del_missing_is_retained(tmp_path):
    path = _write(tmp_path, HEADER, _row(del_=""))
    rows = list(read_ccpc(path, expected_year=2024))
    assert rows[0].local_district is None


def test_def_missing_is_retained(tmp_path):
    # 2009/2012 publish blank DEF (whitespace) alongside blank DEL.
    path = _write(tmp_path, HEADER, _row(aelec="2009", def_=" ", del_=" "))
    rows = list(read_ccpc(path, expected_year=2009))
    assert rows[0].federal_district is None
    assert rows[0].local_district is None


def test_unknown_column_rejected(tmp_path):
    bad_header = HEADER + ",EXTRA"
    path = _write(tmp_path, bad_header, _row())
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_renamed_column_rejected(tmp_path):
    bad_header = HEADER.replace("NS", "NS_")
    path = _write(tmp_path, bad_header, _row())
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_wrong_year_rejected(tmp_path):
    path = _write(tmp_path, HEADER, _row(aelec="2018"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_wrong_entity_rejected(tmp_path):
    path = _write(tmp_path, HEADER, _row(edocve="15"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_negative_count_rejected(tmp_path):
    path = _write(tmp_path, HEADER, _row(ln="-1", sv="0", nv="0", ns="-1"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_accounting_identity_enforced(tmp_path):
    path = _write(tmp_path, HEADER, _row(ln="101", sv="40", nv="40", ns="20"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_sexo_out_of_range_rejected(tmp_path):
    path = _write(tmp_path, HEADER, _row(sexo="3"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_sexo_2_rejected_in_historical_year(tmp_path):
    # SEXO=2 exists only in 2024; its absence in earlier years is not a zero count.
    path = _write(tmp_path, HEADER, _row(aelec="2009", sexo="2"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2009))


def test_sexo_2_allowed_in_2024(tmp_path):
    path = _write(tmp_path, HEADER, _row(sexo="2"))
    rows = list(read_ccpc(path, expected_year=2024))
    assert rows[0].sex == 2


def test_edad_below_18_rejected(tmp_path):
    path = _write(tmp_path, HEADER, _row(edad="17"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_tiposec_invalid_rejected(tmp_path):
    path = _write(tmp_path, HEADER, _row(tiposec="X"))
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_duplicate_key_rejected(tmp_path):
    # Same (year, entity, municipality, section, sex, age) key twice.
    path = _write(
        tmp_path,
        HEADER,
        _row(ln="100", sv="40", nv="40", ns="20"),
        _row(ln="200", sv="80", nv="80", ns="40"),
    )
    with pytest.raises(CCPCSchemaError):
        list(read_ccpc(path, expected_year=2024))


def test_high_age_preserved_raw(tmp_path):
    # Ages above 100 are kept raw (aggregated to 100+ only in reporting).
    path = _write(tmp_path, HEADER, _row(edad="130"))
    rows = list(read_ccpc(path, expected_year=2024))
    assert rows[0].age == 130


def test_bom_header_tolerated(tmp_path):
    # The 2024 member carries a UTF-8 BOM; encoding utf-8-sig strips it.
    path = _write(tmp_path, HEADER, _row(), encoding="utf-8-sig")
    rows = list(read_ccpc(path, expected_year=2024))
    assert len(rows) == 1
