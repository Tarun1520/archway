"""The eligibility gate and the license families: plain rules, tested with certainty."""

import pytest

from app.policy.eligibility import EligibilityPolicy, check_component, rank_key
from app.policy.licenses import license_family

POLICY = EligibilityPolicy()


@pytest.mark.parametrize("text, family", [
    ("MIT", "permissive"), ("MIT License", "permissive"), ("Apache Software License", "permissive"),
    ("BSD-3-Clause", "permissive"), ("ISC", "permissive"), ("Apache 2.0 License", "permissive"),
    ("GNU Lesser General Public License v3 or later (LGPLv3+)", "weak_copyleft"), ("MPL-2.0", "weak_copyleft"),
    ("GPL v3", "strong_copyleft"), ("AGPL-3.0", "strong_copyleft"),
    ("LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only", "weak_copyleft"),  # OR: the most permissive choice
    ("MIT AND Apache-2.0 AND BSD-3-Clause", "permissive"),
    ("MIT AND GPL-3.0", "strong_copyleft"),  # AND: the most restrictive part
    ("Fair Source v1.0", "non_open"), ("SEE LICENSE IN LICENSE", "unknown"), ("NOASSERTION", "unknown"), (None, "unknown"),
])
def test_license_families(text, family):
    assert license_family(text) == family


def component(cid="c", license="MIT", status="detected", archived=False, fit=3, kind="building_block", stars=100):
    return {"id": cid, "fit": fit, "kind": kind,
            "facts": {"license": license, "license_status": status, "archived": archived, "stars": stars}}


def test_the_rules_in_order():
    assert check_component(component(), [], POLICY).status == "eligible"
    assert check_component(component(license="AGPL-3.0"), [], POLICY).status == "excluded"
    assert check_component(component(archived=True), [], POLICY).status == "excluded"
    assert check_component(component(fit=1, kind="reference_app"), [], POLICY).status == "unresolved"
    assert check_component(component(license=None, status="none_detected"), [], POLICY).status == "review_required"
    assert check_component(component(license="LGPL-3.0"), [], POLICY).status == "review_required"
    assert check_component(component(license="AGPL-3.0"), [], EligibilityPolicy(licenses="copyleft_ok")).status == "eligible"


def test_a_decision_that_it_does_not_meet_the_requirement_makes_it_unresolved_and_not_evaluated_does_not():
    no = [{"question_type": "requirement_fit", "final_result": "does_not_meet"}]
    unknown = [{"question_type": "requirement_fit", "final_result": None}]
    assert check_component(component(), no, POLICY).status == "unresolved"
    assert check_component(component(), unknown, POLICY).status == "eligible"


def test_every_verdict_but_eligible_says_why():
    for c in [component(license="GPL-3.0"), component(archived=True), component(license=None, status="not_retrieved")]:
        verdict = check_component(c, [], POLICY)
        assert verdict.status != "eligible" and verdict.reasons


def test_no_score_can_lift_an_ineligible_component_above_an_eligible_one():
    best_but_gpl = component("gpl", license="GPL-3.0", fit=3, stars=100_000)
    modest = component("ok", fit=2, stars=3)
    ranked = sorted([best_but_gpl, modest], key=lambda c: rank_key(c, check_component(c, [], POLICY)))
    assert [c["id"] for c in ranked] == ["ok", "gpl"]
