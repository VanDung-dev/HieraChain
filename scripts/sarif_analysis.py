"""
SARIF Analysis Script

This script parses a SARIF (Static Analysis Results Interchange Format) file 
and prints out the analysis results in a readable format.
"""

import json

sarif = json.load(open('python.sarif', 'r', encoding='utf-8'))

for run in sarif.get('runs', []):
    for r in run.get('results', []):
        loc = r['locations'][0]['physicalLocation']
        print(r.get('ruleId'), '|', r['message'].get('text'), '|', loc['artifactLocation'].get('uri'), ':', loc['region'].get('startLine'))
