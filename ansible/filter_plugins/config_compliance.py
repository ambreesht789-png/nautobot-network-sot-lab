"""Ansible filter plugins for configuration compliance comparison.

The comparison is deliberately line-oriented rather than parser-based. A parser
gives richer results but has to understand every platform's grammar; a
normalised line diff works across vendors and is transparent enough that a
network engineer can audit the result by hand.

Filters provided:
    normalize_config    Strip noise so two configurations can be compared
    config_compliance   Compare intended against actual, return a result dict
    compliance_summary  Aggregate per-device results into totals
"""

from __future__ import annotations

import re
from typing import Any


def normalize_config(
    config: str, ignore_patterns: list[str] | None = None
) -> list[str]:
    """Reduce a configuration blob to a comparable list of lines.

    Trailing whitespace, blank lines, comment-only lines and anything matching
    an ignore pattern are removed. Indentation is preserved, because on most
    platforms it carries hierarchy and two identical lines under different
    parents are not the same line.
    """
    if not config:
        return []

    patterns = [re.compile(pattern) for pattern in (ignore_patterns or [])]
    normalized: list[str] = []

    for raw_line in config.splitlines():
        line = raw_line.rstrip()

        if not line.strip():
            continue

        if any(pattern.search(line) for pattern in patterns):
            continue

        normalized.append(line)

    return normalized


def config_compliance(
    intended: str,
    actual: str,
    ignore_patterns: list[str] | None = None,
    fail_on_extra: bool = False,
) -> dict[str, Any]:
    """Compare an intended configuration against the running configuration.

    Returns a structured result rather than a boolean, so the caller can report
    precisely which lines are missing instead of only that something is wrong.
    """
    intended_lines = normalize_config(intended, ignore_patterns)
    actual_lines = normalize_config(actual, ignore_patterns)

    intended_set = set(intended_lines)
    actual_set = set(actual_lines)

    missing = [line for line in intended_lines if line not in actual_set]
    extra = [line for line in actual_lines if line not in intended_set]

    compliant = not missing and (not extra or not fail_on_extra)

    total = len(intended_lines)
    matched = total - len(missing)
    percentage = round((matched / total) * 100, 2) if total else 100.0

    return {
        "compliant": compliant,
        "missing_lines": missing,
        "extra_lines": extra,
        "intended_line_count": total,
        "actual_line_count": len(actual_lines),
        "matched_line_count": matched,
        "compliance_percentage": percentage,
    }


def compliance_summary(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-device compliance results into overall figures."""
    if not results:
        return {
            "total_devices": 0,
            "compliant_devices": 0,
            "non_compliant_devices": 0,
            "compliance_rate": 100.0,
            "total_missing_lines": 0,
        }

    total = len(results)
    compliant = sum(1 for result in results.values() if result.get("compliant"))
    missing = sum(len(result.get("missing_lines", [])) for result in results.values())

    return {
        "total_devices": total,
        "compliant_devices": compliant,
        "non_compliant_devices": total - compliant,
        "compliance_rate": round((compliant / total) * 100, 2),
        "total_missing_lines": missing,
    }


class FilterModule:
    """Expose the filters to Ansible."""

    def filters(self) -> dict[str, Any]:
        return {
            "normalize_config": normalize_config,
            "config_compliance": config_compliance,
            "compliance_summary": compliance_summary,
        }
