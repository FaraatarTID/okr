"""The Python license gate accepts psycopg by name only, not the whole LGPL-3.0-only family."""

from __future__ import annotations

from scripts import verify_dependency_licenses as licenses


def test_psycopg_packages_are_accepted_under_lgpl_3_only():
    assert licenses._python_license_accepted("psycopg", "LGPL-3.0-only")
    assert licenses._python_license_accepted("psycopg-binary", "LGPL-3.0-only")
    assert licenses._python_license_accepted("Psycopg", "LGPL-3.0-only")


def test_another_package_under_the_same_license_still_fails():
    assert not licenses._python_license_accepted("some-other-lib", "LGPL-3.0-only")


def test_psycopg_under_a_different_license_still_fails():
    assert not licenses._python_license_accepted("psycopg", "GPL-3.0-only")
    assert not licenses._python_license_accepted("psycopg", "unknown")


def test_previously_allowed_licenses_are_unaffected():
    assert licenses._python_license_accepted("anything", "MIT")
    assert licenses._python_license_accepted(
        "psycopg2-binary", "GNU Library or Lesser General Public License (LGPL)"
    )
