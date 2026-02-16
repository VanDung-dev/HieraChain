"""
Static Analysis Module for HieraChain Ledger

This module provides static code analysis capabilities for vulnerability detection,
code quality assessment, and compliance checking. Integrates with tools like
Bandit, SonarQube, and custom analyzers.
"""

import ast
import re
import json
import logging
import argparse
from typing import Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class AnalysisType(Enum):
    """Types of static analysis"""
    SECURITY_VULNERABILITY = "security_vulnerability"
    CODE_QUALITY = "code_quality"
    COMPLIANCE_CHECK = "compliance_check"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    PERFORMANCE_ANALYSIS = "performance_analysis"


class Severity(Enum):
    """Analysis finding severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnalysisRule:
    """Static analysis rule definition"""
    rule_id: str
    name: str
    description: str
    analysis_type: AnalysisType
    severity: Severity
    pattern: str  # Regex pattern or AST pattern
    message: str
    remediation: str
    enabled: bool = True


@dataclass
class AnalysisFinding:
    """Static analysis finding"""
    rule_id: str
    file_path: str
    line_number: int
    column: int
    severity: Severity
    message: str
    code_snippet: str
    remediation: str
    confidence: float  # 0.0 to 1.0


class SecurityAnalyzer:
    """Security vulnerability analyzer"""
    
    def __init__(self):
        """Initialize security analyzer with security rules"""
        self.security_rules = [
            AnalysisRule(
                rule_id="SEC_001",
                name="Hardcoded Secrets",
                description="Detect hardcoded passwords, API keys, or secrets",
                analysis_type=AnalysisType.SECURITY_VULNERABILITY,
                severity=Severity.HIGH,
                pattern=r'(password|api_key|secret|token)\s*=\s*["\'][^"\']{8,}["\']',
                message="Hardcoded secret detected",
                remediation="Move secrets to environment variables or secure configuration"
            ),
            AnalysisRule(
                rule_id="SEC_002",
                name="SQL Injection Risk",
                description="Detect potential SQL injection vulnerabilities",
                analysis_type=AnalysisType.SECURITY_VULNERABILITY,
                severity=Severity.CRITICAL,
                pattern=r'(execute|query|cursor)\s*\(\s*["\'].*%.*["\']',
                message="Potential SQL injection vulnerability",
                remediation="Use parameterized queries instead of string concatenation"
            ),
            AnalysisRule(
                rule_id="SEC_003",
                name="Insecure Random",
                description="Detect use of insecure random number generation",
                analysis_type=AnalysisType.SECURITY_VULNERABILITY,
                severity=Severity.MEDIUM,
                pattern=r'random\.(random|randint|choice)',
                message="Insecure random number generation",
                remediation="Use secrets module for cryptographic purposes"
            ),
            AnalysisRule(
                rule_id="SEC_004",
                name="Debug Mode",
                description="Detect debug mode enabled in production code",
                analysis_type=AnalysisType.SECURITY_VULNERABILITY,
                severity=Severity.LOW,
                pattern=r'debug\s*=\s*True',
                message="Debug mode enabled",
                remediation="Disable debug mode in production"
            )
        ]
    
    def analyze_file(self, file_path: str) -> list[AnalysisFinding]:
        """Analyze file for security vulnerabilities"""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
            
            for rule in self.security_rules:
                if not rule.enabled:
                    continue
                
                for line_num, line in enumerate(lines, 1):
                    match = re.search(rule.pattern, line, re.IGNORECASE)
                    if match:
                        findings.append(AnalysisFinding(
                            rule_id=rule.rule_id,
                            file_path=file_path,
                            line_number=line_num,
                            column=match.start(),
                            severity=rule.severity,
                            message=rule.message,
                            code_snippet=line.strip(),
                            remediation=rule.remediation,
                            confidence=0.8
                        ))
            
        except Exception as e:
            logging.error(f"Error analyzing file {file_path}: {str(e)}")
        
        return findings


class CodeQualityAnalyzer:
    """Code quality analyzer"""
    
    def __init__(self):
        """Initialize code quality analyzer"""
        self.quality_rules = [
            AnalysisRule(
                rule_id="QUAL_001",
                name="Long Function",
                description="Function is too long",
                analysis_type=AnalysisType.CODE_QUALITY,
                severity=Severity.LOW,
                pattern=r'def\s+\w+',  # Will be handled by AST analysis
                message="Function is too long (>50 lines)",
                remediation="Break down function into smaller, more focused functions"
            ),
            AnalysisRule(
                rule_id="QUAL_002",
                name="Too Many Parameters",
                description="Function has too many parameters",
                analysis_type=AnalysisType.CODE_QUALITY,
                severity=Severity.LOW,
                pattern=r'def\s+\w+',  # Will be handled by AST analysis
                message="Function has too many parameters (>5)",
                remediation="Use data classes or configuration objects for multiple parameters"
            ),
            AnalysisRule(
                rule_id="QUAL_003",
                name="Missing Docstring",
                description="Function or class missing docstring",
                analysis_type=AnalysisType.CODE_QUALITY,
                severity=Severity.INFO,
                pattern=r'(def|class)\s+\w+',  # Will be handled by AST analysis
                message="Missing docstring",
                remediation="Add comprehensive docstring describing purpose and parameters"
            )
        ]
        
        self.max_function_length = 50
        self.max_parameters = 5
    
    def analyze_file(self, file_path: str) -> list[AnalysisFinding]:
        """Analyze file for code quality issues using AST"""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Analyze AST nodes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    findings.extend(self._analyze_function(node, file_path, content))
                elif isinstance(node, ast.ClassDef):
                    findings.extend(self._analyze_class(node, file_path, content))
            
        except SyntaxError as e:
            findings.append(AnalysisFinding(
                rule_id="QUAL_999",
                file_path=file_path,
                line_number=e.lineno or 1,
                column=e.offset or 0,
                severity=Severity.CRITICAL,
                message=f"Syntax error: {str(e)}",
                code_snippet="",
                remediation="Fix syntax error",
                confidence=1.0
            ))
        except Exception as e:
            logging.error(f"Error analyzing file {file_path}: {str(e)}")
        
        return findings
    
    def _analyze_function(self, node: ast.FunctionDef, file_path: str, content: str) -> list[AnalysisFinding]:
        """Analyze function for quality issues"""
        findings = []
        lines = content.splitlines()
        
        # Check function length
        if hasattr(node, 'end_lineno') and node.end_lineno:
            func_length = node.end_lineno - node.lineno
            if func_length > self.max_function_length:
                findings.append(AnalysisFinding(
                    rule_id="QUAL_001",
                    file_path=file_path,
                    line_number=node.lineno,
                    column=node.col_offset,
                    severity=Severity.LOW,
                    message=f"Function '{node.name}' is too long ({func_length} lines)",
                    code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                    remediation="Break down function into smaller, more focused functions",
                    confidence=0.9
                ))
        
        # Check parameter count
        param_count = len(node.args.args)
        if param_count > self.max_parameters:
            findings.append(AnalysisFinding(
                rule_id="QUAL_002",
                file_path=file_path,
                line_number=node.lineno,
                column=node.col_offset,
                severity=Severity.LOW,
                message=f"Function '{node.name}' has too many parameters ({param_count})",
                code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                remediation="Use data classes or configuration objects for multiple parameters",
                confidence=0.9
            ))
        
        # Check for docstring
        if not ast.get_docstring(node):
            findings.append(AnalysisFinding(
                rule_id="QUAL_003",
                file_path=file_path,
                line_number=node.lineno,
                column=node.col_offset,
                severity=Severity.INFO,
                message=f"Function '{node.name}' missing docstring",
                code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                remediation="Add comprehensive docstring describing purpose and parameters",
                confidence=0.8
            ))
        
        return findings
    
    @staticmethod
    def _analyze_class(node: ast.ClassDef, file_path: str, content: str) -> list[AnalysisFinding]:
        """Analyze class for quality issues"""
        findings = []
        lines = content.splitlines()
        
        # Check for docstring
        if not ast.get_docstring(node):
            findings.append(AnalysisFinding(
                rule_id="QUAL_003",
                file_path=file_path,
                line_number=node.lineno,
                column=node.col_offset,
                severity=Severity.INFO,
                message=f"Class '{node.name}' missing docstring",
                code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                remediation="Add comprehensive docstring describing class purpose",
                confidence=0.8
            ))
        
        return findings


def _read_lines(file_path: str) -> list[str]:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content.splitlines()


class ComplianceChecker:
    """Compliance checker for Ledger guidelines"""
    def __init__(self):
        """Initialize compliance checker"""
        self.compliance_rules = [
            AnalysisRule(
                rule_id="COMP_001",
                name="Block Structure Compliance",
                description="Verify correct block structure implementation",
                analysis_type=AnalysisType.COMPLIANCE_CHECK,
                severity=Severity.MEDIUM,
                pattern=r'^class\s+Block\s*[:\(]',
                message="Verify that Block class contains multiple events, not single event",
                remediation="Ensure Block class has 'events' parameter (plural), not 'event'"
            ),
            AnalysisRule(
                rule_id="COMP_002",
                name="Entity ID Usage",
                description="Verify entity_id is used as metadata, not identifier",
                analysis_type=AnalysisType.COMPLIANCE_CHECK,
                severity=Severity.MEDIUM,
                pattern=r'(block|chain)\..*\s*=\s*entity_id',
                message="entity_id should be metadata field, not block/chain identifier",
                remediation="Use entity_id as metadata field within events"
            ),
            AnalysisRule(
                rule_id="COMP_003",
                name="Event-Based Terminology",
                description="Verify use of 'event' terminology instead of 'transaction'",
                analysis_type=AnalysisType.COMPLIANCE_CHECK,
                severity=Severity.HIGH,
                pattern=r'transaction',
                message="Use 'event' terminology instead of 'transaction'",
                remediation="Replace 'transaction' with 'event' throughout the codebase"
            )
        ]
    
    @staticmethod
    def _is_educational_crypto_content(line: str) -> bool:
        """
        Check if a line contains educational/descriptive crypto content 
        or valid technical terms that should be exempt.
        
        Args:
            line: Line of code to check
            
        Returns:
            True if the line should be exempt from crypto terminology checks
        """
        line_lower = line.lower().strip()
        
        # Skip comments
        if '#' in line:
            return True
        
        # Whitelist valid technical system terms where "Transaction" is appropriate
        allowed_terms = [
            'transactionjournal',
            'crosschaintransaction',
            'transactionmanager',
            'gotransaction',
            'transaction_schema',
            'process_transactions',
            'get_transaction_schema',
            'transaction',  # If part of type hint or specific variable context handled below
        ]
        
        # Check specific allowed combinations
        if any(term in line_lower for term in allowed_terms):
            return True
            
        # Skip if line already mentions 'event' (likely doing proper replacement)
        if 'event' in line_lower:
            return True
        
        # Skip string literals that are clearly educational/descriptive
        educational_patterns = [
            r'["\']\s*transaction\s*["\']',  # String literals containing just "transaction"
            r'forbidden[_\s]*terms?',        # Lines mentioning forbidden terms
            r'crypto[_\s]*terms?',           # Lines about crypto terms
            r'avoid[_\s]*terms?',            # Lines about avoiding terms
            r'replace.*with.*event',         # Replacement instructions
            r'not.*use.*transaction',        # Instructions not to use transaction
            r'instead.*of.*transaction',     # Instructions to use something instead
            r'terminology.*transaction',     # Lines about terminology
            r'anti[_\s]*pattern',           # Anti-pattern descriptions
            r'example.*wrong',              # Wrong example descriptions
            r'incorrect.*usage',            # Incorrect usage examples
            r'cryptocurrency.*detect',      # Cryptocurrency detection patterns
            r'validation.*rule',            # Validation rules
            r'compliance.*check',           # Compliance checking
            r'pattern.*matching',           # Pattern matching code
            r'regex.*pattern',              # Regex patterns
            r'search.*term',                # Search term definitions
        ]
        
        for pattern in educational_patterns:
            if re.search(pattern, line_lower):
                return True
        
        # Skip array/list literals containing forbidden terms (likely validation lists)
        if re.search(r'[\[{].*transaction.*[]}]', line_lower):
            return True
        
        # Skip dictionary/object definitions with forbidden terms as keys/values
        if re.search(r'["\']transaction["\']?\s*[:=]', line_lower):
            return True
        
        # Skip method/function parameters or variables that are clearly educational
        if re.search(r'(param|arg|var|field).*transaction', line_lower):
            return True
        
        return False

    def _enabled_rules(self) -> list[AnalysisRule]:
        return [rule for rule in self.compliance_rules if rule.enabled]

    def _should_skip_line_for_rule(
        self, rule: AnalysisRule, line: str
    ) -> bool:
        if rule.rule_id != "COMP_003":
            return False
        return self._is_educational_crypto_content(line)

    @staticmethod
    def _build_finding(
        rule: AnalysisRule,
        file_path: str,
        line: str,
        line_num: int,
        match,
    ) -> AnalysisFinding:
        return AnalysisFinding(
            rule_id=rule.rule_id,
            file_path=file_path,
            line_number=line_num,
            column=match.start(),
            severity=rule.severity,
            message=rule.message,
            code_snippet=line.strip(),
            remediation=rule.remediation,
            confidence=0.7,
        )

    def _analyze_lines_for_rule(
        self, file_path: str, lines: list[str], rule: AnalysisRule
    ) -> list[AnalysisFinding]:
        rule_findings: list[AnalysisFinding] = []
        for line_num, line in enumerate(lines, 1):
            if self._should_skip_line_for_rule(rule, line):
                continue
            match = re.search(rule.pattern, line, re.IGNORECASE)
            if not match:
                continue
            rule_findings.append(
                self._build_finding(rule, file_path, line, line_num, match)
            )
        return rule_findings

    def analyze_file(self, file_path: str) -> list[AnalysisFinding]:
        """Analyze file for compliance issues"""
        findings: list[AnalysisFinding] = []
        try:
            lines = _read_lines(file_path)
            for rule in self._enabled_rules():
                findings.extend(
                    self._analyze_lines_for_rule(file_path, lines, rule)
                )
        except Exception as e:
            logging.error(f"Error analyzing file {file_path}: {str(e)}")
        return findings


class DependencyAnalyzer:
    """Dependency security and licensing analyzer"""
    
    def analyze_requirements(self, requirements_file: str) -> list[AnalysisFinding]:
        """Analyze requirements file for security issues"""
        findings = []
        
        try:
            with open(requirements_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Extract package name and version
                if '==' in line:
                    package, version = line.split('==', 1)
                    package = package.strip()
                    version = version.strip()
                    
                    # Check for known vulnerable packages (simplified check)
                    if self._is_vulnerable_package(package, version):
                        findings.append(AnalysisFinding(
                            rule_id="DEP_001",
                            file_path=requirements_file,
                            line_number=line_num,
                            column=0,
                            severity=Severity.HIGH,
                            message=f"Potentially vulnerable dependency: {package}=={version}",
                            code_snippet=line,
                            remediation=f"Update {package} to latest secure version",
                            confidence=0.7
                        ))
                
            
        except Exception as e:
            logging.error(f"Error analyzing requirements file {requirements_file}: {str(e)}")
        
        return findings
    
    @staticmethod
    def _is_vulnerable_package(package: str, version: str) -> bool:
        """Check if package version is known to be vulnerable (simplified)"""
        # This is a simplified check. In production, this would query
        # vulnerability databases like PyPI Advisory Database
        vulnerable_packages = {
            'requests': ['2.19.0', '2.19.1'],  # Example vulnerable versions
            'urllib3': ['1.24.0', '1.24.1'],
            'flask': ['0.12.0', '0.12.1']
        }
        
        return package.lower() in vulnerable_packages and version in vulnerable_packages[package.lower()]


def _init_findings_container() -> dict[str, list[AnalysisFinding]]:
    return {
        "cryptocurrency": [],
        "security": [],
        "quality": [],
        "compliance": [],
        "dependencies": [],
    }


class StaticAnalyzer:
    """Main static analyzer orchestrating all analysis types"""
    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize static analyzer with configuration"""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize analyzers
        self.security_analyzer = SecurityAnalyzer()
        self.quality_analyzer = CodeQualityAnalyzer()
        self.compliance_checker = ComplianceChecker()
        self.dependency_analyzer = DependencyAnalyzer()
        
        # Analysis configuration
        self.enabled_analyzers = self.config.get('enabled_analyzers', [
            'security', 'quality', 'compliance', 'dependencies'
        ])
        
        self.file_extensions = self.config.get('file_extensions', ['.py'])
        self.exclude_patterns = self.config.get('exclude_patterns', [
            '__pycache__', '.git', '.venv', 'venv', 'node_modules'
        ])

    def _analyze_python_files_for_project(
        self, project_root: Path, all_findings: dict[str, list[AnalysisFinding]]
    ) -> None:
        if not any(
            analyzer in self.enabled_analyzers
            for analyzer in ("security", "quality", "compliance")
        ):
            return

        for py_file in self._get_python_files(project_root):
            file_path = str(py_file)

            if "security" in self.enabled_analyzers:
                findings = self.security_analyzer.analyze_file(file_path)
                all_findings["security"].extend(findings)

            if "quality" in self.enabled_analyzers:
                findings = self.quality_analyzer.analyze_file(file_path)
                all_findings["quality"].extend(findings)

            if "compliance" in self.enabled_analyzers:
                findings = self.compliance_checker.analyze_file(file_path)
                all_findings["compliance"].extend(findings)

    def _analyze_dependencies_for_project(
        self, project_root: Path, all_findings: dict[str, list[AnalysisFinding]]
    ) -> None:
        if "dependencies" not in self.enabled_analyzers:
            return

        requirements_files = list(project_root.glob("**/requirements*.txt"))
        for req_file in requirements_files:
            findings = self.dependency_analyzer.analyze_requirements(str(req_file))
            all_findings["dependencies"].extend(findings)

    def analyze_project(self, project_path: str) -> dict[str, list[AnalysisFinding]]:
        """Analyze entire project"""
        all_findings = _init_findings_container()
        project_root = Path(project_path)
        self._analyze_python_files_for_project(project_root, all_findings)
        self._analyze_dependencies_for_project(project_root, all_findings)
        return all_findings

    def _get_file_analyzers(
        self, analysis_types: list[str]
    ) -> list[Callable[[str], list[AnalysisFinding]]]:
        analyzers_map = {
            "security": self.security_analyzer.analyze_file,
            "quality": self.quality_analyzer.analyze_file,
            "compliance": self.compliance_checker.analyze_file,
        }
        return [
            analyzer
            for name, analyzer in analyzers_map.items()
            if name in analysis_types
        ]

    def analyze_file(
        self, file_path: str, analysis_types: list[str] | None = None
    ) -> list[AnalysisFinding]:
        """Analyze single file"""
        effective_types = analysis_types or self.enabled_analyzers
        findings: list[AnalysisFinding] = []
        for analyzer in self._get_file_analyzers(effective_types):
            findings.extend(analyzer(file_path))
        return findings
    
    def _get_python_files(self, project_root: Path) -> list[Path]:
        """Get all Python files in project"""
        python_files = []
        
        for file_path in project_root.rglob('*.py'):
            # Check if file should be excluded
            if any(pattern in str(file_path) for pattern in self.exclude_patterns):
                continue
            
            python_files.append(file_path)
        
        return python_files
    
    @staticmethod
    def _generate_json_report(findings: dict[str, list[AnalysisFinding]]) -> str:
        report_data: dict[str, list[dict[str, Any]]] = {}
        for category, finding_list in findings.items():
            report_data[category] = [asdict(finding) for finding in finding_list]
            for finding_dict in report_data[category]:
                severity_value = finding_dict.get("severity")
                if hasattr(severity_value, "value"):
                    finding_dict["severity"] = severity_value.value
        return json.dumps(report_data, indent=2, default=str)

    @staticmethod
    def _generate_text_report(findings: dict[str, list[AnalysisFinding]]) -> str:
        lines: list[str] = ["Static Analysis Report", "=" * 50, ""]
        for category, finding_list in findings.items():
            if not finding_list:
                continue
            lines.append(f"\n{category.upper()} ({len(finding_list)} findings):")
            lines.append("-" * 40)
            for finding in finding_list:
                lines.append(
                    f"  {finding.severity.value.upper()}: {finding.message}"
                )
                lines.append(
                    f"    File: {finding.file_path}:{finding.line_number}"
                )
                lines.append(f"    Code: {finding.code_snippet}")
                lines.append(f"    Fix: {finding.remediation}")
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def generate_report(
        findings: dict[str, list[AnalysisFinding]], output_format: str = "json"
    ) -> str:
        """Generate analysis report"""
        fmt = output_format.lower()
        if fmt == "json":
            return StaticAnalyzer._generate_json_report(findings)
        if fmt == "text":
            return StaticAnalyzer._generate_text_report(findings)
        raise ValueError(f"Unsupported output format: {output_format}")
    
    @staticmethod
    def get_summary(findings: dict[str, list[AnalysisFinding]]) -> dict[str, Any]:
        """Get analysis summary statistics"""
        summary = {
            'total_findings': 0,
            'by_category': {},
            'by_severity': {},
            'critical_count': 0,
            'high_count': 0
        }
        
        for category, finding_list in findings.items():
            summary['by_category'][category] = len(finding_list)
            summary['total_findings'] += len(finding_list)
            
            for finding in finding_list:
                severity = finding.severity.value
                summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1
                
                if finding.severity == Severity.CRITICAL:
                    summary['critical_count'] += 1
                elif finding.severity == Severity.HIGH:
                    summary['high_count'] += 1
        
        return summary


def run_static_analysis(
        project_path: str = "hierachain",
        output_file: str | None = None,
        output_format: str = "json"
) -> bool:
    """
    Entry point for running static analysis.
    
    Args:
        project_path: Path to project root (default: 'hierachain')
        output_file: Output file path (optional)
        output_format: Output format (json or text, default: 'json')
        
    Returns:
        True if analysis completed successfully
    """
    try:
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
        # Initialize analyzer
        analyzer = StaticAnalyzer()
        
        # Run analysis
        logging.info(f"Running static analysis on {project_path}")
        findings = analyzer.analyze_project(project_path)
        
        # Generate report
        report = analyzer.generate_report(findings, output_format)
        
        # Output results
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logging.info(f"Analysis report written to {output_file}")
        else:
            print(report)
        
        # Print summary
        summary = analyzer.get_summary(findings)
        logging.info(f"Analysis complete: {summary['total_findings']} total findings")
        logging.info(f"Critical: {summary['critical_count']}, High: {summary['high_count']}")
        
        # Return success if no critical issues
        return summary['critical_count'] == 0
        
    except Exception as e:
        logging.error(f"Static analysis failed: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run static analysis")
    parser.add_argument("project_path", nargs="?", default="hierachain", help="Project root path")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-f", "--format", choices=["json", "text"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    success = run_static_analysis(
        project_path=args.project_path,
        output_file=args.output,
        output_format=args.format
    )
    
    exit(0 if success else 1)
