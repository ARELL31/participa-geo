"""CLI exit status reflects national GeoServer verification results."""

from __future__ import annotations


def _verify_with(monkeypatch, audit):
    import gis.geoserver.national as national
    import participa_geo.settings as settings
    from participa_geo.cli import main

    monkeypatch.setattr(national, "verify_national_layers", lambda _settings: audit)
    monkeypatch.setattr(settings, "Settings", lambda: object())
    return main(["gis", "verify-national"])


def test_verify_national_cli_returns_nonzero_for_failed_audit(monkeypatch, capsys):
    status = _verify_with(monkeypatch, {"verification_passed": False, "failed_checks": ["wms"]})

    assert status == 1
    assert '"verification_passed": false' in capsys.readouterr().out


def test_verify_national_cli_returns_zero_for_passing_audit(monkeypatch, capsys):
    status = _verify_with(monkeypatch, {"verification_passed": True, "failed_checks": []})

    assert status == 0
    assert '"verification_passed": true' in capsys.readouterr().out
