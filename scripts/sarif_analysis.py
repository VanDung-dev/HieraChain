"""
SARIF Analysis Script

This script parses a SARIF (Static Analysis Results Interchange Format) file 
and prints out the analysis results in a readable format.

Usage:
    python scripts/sarif_analysis.py [sarif_file]
    
If no file is specified, defaults to 'python.sarif'.
"""

import json
import sys
import os


def _load_sarif_file(sarif_file: str) -> dict | None:
    if not os.path.exists(sarif_file):
        print(f"Info: SARIF file '{sarif_file}' not found.")
        print("\nTo generate a SARIF file, run a static analysis tool with SARIF output.")
        print("Example with pylint:")
        print("  pylint hierachain --output-format=sarif > python.sarif")
        print("\nNo analysis performed.")
        return None

    try:
        with open(sarif_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in SARIF file: {e}")
        sys.exit(1)


def _iter_runs(sarif: dict):
    for run in sarif.get('runs', []):
        tool_name = run.get('tool', {}).get('driver', {}).get('name', 'Unknown')
        results = run.get('results', [])
        yield tool_name, results


def _format_location(result: dict) -> tuple[str, str]:
    locations = result.get('locations', [])
    if not locations:
        return "", ""
    loc = locations[0].get('physicalLocation', {})
    uri = loc.get('artifactLocation', {}).get('uri', 'unknown')
    line = loc.get('region', {}).get('startLine', '?')
    return str(uri), str(line)


def _print_run_results(tool_name: str, results: list[dict]) -> int:
    total = 0
    if results:
        print(f"\n=== {tool_name} ({len(results)} findings) ===\n")

    for r in results:
        uri, line = _format_location(r)
        if not uri:
            continue

        rule_id = r.get('ruleId', 'unknown')
        message = r.get('message', {}).get('text', 'No message')
        level = r.get('level', 'note')

        print(f"[{level.upper()}] {rule_id}")
        print(f"  File: {uri}:{line}")
        print(f"  Message: {message}")
        print()
        total += 1

    return total


def _print_summary(total_results: int) -> None:
    if total_results == 0:
        print("No findings in SARIF file.")
    else:
        print(f"\nTotal findings: {total_results}")


def analyze_sarif(sarif_file: str) -> None:
    """Parse and display SARIF analysis results."""
    sarif = _load_sarif_file(sarif_file)
    if sarif is None:
        return

    total_results = 0
    for tool_name, results in _iter_runs(sarif):
        total_results += _print_run_results(tool_name, results)

    _print_summary(total_results)


if __name__ == "__main__":
    sarif_file = sys.argv[1] if len(sys.argv) > 1 else 'python.sarif'
    analyze_sarif(sarif_file)
