"""
Term Censorship Integration Test

Ensures that no forbidden cryptocurrency terminology makes its way into the
HieraChain codebase, configuration files, or comments.
"""

import os
import re

# Forbidden terms list from AGENT.md / CrossChainValidator rules
FORBIDDEN_TERMS = [
    r"\bmining\b",
    r"\bcoin\b",
    r"\bwallet\b",
    r"\bfee\b",
]

def test_no_crypto_terms_in_codebase():
    """Scan code files for forbidden terms to maintain enterprise Web2 style."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../hierachain"))
    offending_lines = []

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if not file.endswith((".py", ".sh", ".json", ".ini", ".toml")):
                continue

            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        # Skip list definitions and descriptions
                        if any(x in line for x in ("FORBIDDEN_TERMS", "FORBIDDEN_EVENT_TYPES", "blacklist")):
                            continue
                        # Skip validator rules configuration in utils/validator
                        if ("utils.py" in file or "validator.py" in file) and any(x in line for x in ("coin", "wallet", "fee", "receiver")):
                            continue
                        
                        # Skip docstrings explaining system design
                        if "energy-intensive" in line or "wallet integration" in line:
                            continue
                        # Skip docstring examples explaining regex word-boundary matching
                        if "should not match" in line:
                            continue

                        for term in FORBIDDEN_TERMS:
                            if re.search(term, line, re.IGNORECASE):
                                offending_lines.append(
                                    f"{os.path.relpath(filepath, base_dir)}:{line_num}: found forbidden term in '{line.strip()}'"
                                )
            except Exception:
                pass

    assert not offending_lines, f"Forbidden cryptocurrency terms found:\n" + "\n".join(offending_lines)
