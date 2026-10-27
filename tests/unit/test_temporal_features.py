"""Statistical unit tests for temporal feature construction and cohorts.

These tests pin the exact temporal cuts (t-6 and t-3 only), the common cohort
for M0/M1, the scaler being fit on training rows only, and the tie rule that
keeps M0 when the candidate M1 does not strictly reduce MAE on 2021.
"""

from __future__ import annotations

import numpy as np
import pytest

from participa_geo.ingestion.schema import (
    FootprintStatus,
    IdentityStatus,
    MunicipalityKey,
    MunicipalObservation,
)
from participa_geo.prediction.cohorts import IncompleteIdentityError, TerritoryIdentity
from participa_geo.prediction.features import FEATURE_ORDER, build_examples
from participa_geo.prediction.training import (
    fit_ridge,
    predict_m0,
    predict_ridge,
    select_family,
)


def _obs(
    code: str,
    year: int,
    *,
    ln: int | None = None,
    sv: int = 1000,
    nv: int = 1000,
    ns: int = 0,
    young: float = 0.3,
    senior: float = 0.2,
    rural: float = 0.4,
    name: str = "M",
) -> MunicipalObservation:
    if ln is None:
        ln = sv + nv + ns
    return MunicipalObservation(
        key=MunicipalityKey(state_code="14", municipality_code=code),
        year=year,
        ln=ln,
        sv=sv,
        nv=nv,
        ns=ns,
        municipality_name=name,
        young_share=young,
        senior_share=senior,
        rural_share=rural,
    )


def _identity(*codes: str) -> dict[str, TerritoryIdentity]:
    return {
        code: TerritoryIdentity(
            IdentityStatus.verified_catalogue, FootprintStatus.not_verified
        )
        for code in codes
    }


def test_features_only_use_t_minus_3_and_6():
    obs = [
        _obs("001", 2021, sv=1500, nv=1500, young=0.33, senior=0.22, rural=0.44),
        _obs("001", 2024, sv=1600, nv=1400, young=0.36, senior=0.25, rural=0.41),
    ]
    ds = build_examples(obs, 2027, _identity("001"))
    assert ds.target_year == 2027
    assert len(ds.rows) == 1
    row = ds.rows[0]

    # same-type abstention comes from t-6 (2021); previous from t-3 (2024).
    assert row.features["same_type_abstention_pct"] == pytest.approx(50.0)
    assert row.features["previous_abstention_pct"] == pytest.approx(100 * 1400 / 3000)
    assert row.features["previous_young_share"] == pytest.approx(0.36)
    assert row.features["previous_senior_share"] == pytest.approx(0.25)
    assert row.features["previous_rural_share"] == pytest.approx(0.41)
    assert row.features["is_midterm"] == 1.0

    assert row.origins["same_type_abstention_pct"] == 2021
    assert row.origins["previous_abstention_pct"] == 2024
    assert row.origins["previous_young_share"] == 2024
    assert row.origins["previous_senior_share"] == 2024
    assert row.origins["previous_rural_share"] == 2024

    # No 2027 demographic is used: the target is unknown and every data feature
    # is sourced from 2021 or 2024 only.
    assert row.target is None
    assert set(o for o in row.origins.values() if o is not None) == {2021, 2024}


def test_common_cohort_for_baseline_and_ridge():
    obs: list[MunicipalObservation] = []
    for code in ("001", "003"):
        for year in (2009, 2012, 2015, 2018, 2021):
            obs.append(_obs(code, year))
    # "002" is eligible everywhere except 2018 (known count below 1000).
    for year in (2009, 2012, 2015, 2021):
        obs.append(_obs("002", year))
    obs.append(_obs("002", 2018, sv=499, nv=499))

    identity = _identity("001", "002", "003")
    ds = build_examples(obs, 2021, identity)
    codes = [r.municipality_code for r in ds.rows]
    assert codes == ["001", "003"]
    assert "002" in [e.municipality_code for e in ds.exclusions]

    # M0 and M1 operate on the exact same cohort rows (M0 does not expand it).
    ds15 = build_examples(obs, 2015, identity)
    ds18 = build_examples(obs, 2018, identity)
    fitted = fit_ridge([ds15, ds18])
    pred_m0 = predict_m0(ds)
    _, pred_m1 = predict_ridge(fitted, ds)
    assert len(pred_m0) == len(pred_m1) == len(ds.rows)


def test_scaler_fit_excludes_test_year():
    # The scaler for the 2015/2018 -> 2021 selection fit must be computed from
    # 2015+2018 rows only. A sentinel (extreme 2021 young share, used as the
    # t-3 feature of the 2024 target) must not move the training means.
    obs: list[MunicipalObservation] = []
    for code in ("001", "002", "003"):
        obs.append(_obs(code, 2009, young=0.10))
        obs.append(_obs(code, 2012, young=0.20))
        obs.append(_obs(code, 2015, young=0.30))
        obs.append(_obs(code, 2018, young=0.35))
        obs.append(_obs(code, 2021, young=0.95))  # sentinel
        obs.append(_obs(code, 2024, young=0.99))
    identity = _identity("001", "002", "003")

    ds15 = build_examples(obs, 2015, identity)
    ds18 = build_examples(obs, 2018, identity)
    ds24 = build_examples(obs, 2024, identity)

    fitted_selection = fit_ridge([ds15, ds18])
    fitted_with_test = fit_ridge([ds15, ds18, ds24])

    idx = FEATURE_ORDER.index("previous_young_share")
    # Selection fit mean is exactly the mean of the 2012/2015 young shares.
    expected = np.mean([0.20] * 3 + [0.30] * 3)
    assert fitted_selection.scaler_mean[idx] == pytest.approx(expected)
    # Including the 2024 test year (carrying the 2021 sentinel) shifts the mean.
    assert fitted_with_test.scaler_mean[idx] != pytest.approx(
        fitted_selection.scaler_mean[idx]
    )


def test_tie_keeps_baseline():
    assert select_family(10.0, 10.0) == "M0"  # tie keeps M0
    assert select_family(10.0, 9.0) == "M1"  # M1 strictly better
    assert select_family(10.0, 11.0) == "M0"  # M0 better


def test_missing_identity_fails_loudly():
    obs = [_obs("001", 2021), _obs("001", 2024)]
    with pytest.raises(IncompleteIdentityError):
        build_examples(obs, 2027, {})  # "001" absent -> must not assume verified


def test_ambiguous_identity_excluded():
    obs = [
        _obs("001", 2021),
        _obs("001", 2024),
        _obs("002", 2021),
        _obs("002", 2024),
    ]
    identity = {
        "001": TerritoryIdentity(
            IdentityStatus.verified_catalogue, FootprintStatus.not_verified
        ),
        "002": TerritoryIdentity(IdentityStatus.ambiguous, FootprintStatus.not_verified),
    }
    ds = build_examples(obs, 2027, identity)
    assert [r.municipality_code for r in ds.rows] == ["001"]
    assert "002" in [e.municipality_code for e in ds.exclusions]
