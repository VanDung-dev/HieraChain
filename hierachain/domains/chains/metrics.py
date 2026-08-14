"""
Operation metrics tracking helpers for HieraChain Ledger.
"""


def _safe_ratio(numerator: int, denominator: int) -> float:
    """Return numerator / denominator, defaulting to 0.0 when empty."""
    return numerator / max(denominator, 1)


class OperationMetricsTracker:
    """Tracks domain operation metrics (success, quality, approvals, etc.)."""

    def __init__(self):
        self._metrics: dict[str, int] = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "quality_checks_passed": 0,
            "quality_checks_failed": 0,
            "approvals_granted": 0,
            "approvals_rejected": 0,
            "compliance_violations": 0,
        }

    # -- convenience accessors ------------------------------------------

    def __getitem__(self, key: str) -> int:
        return self._metrics[key]

    def copy(self) -> dict[str, int]:
        """Return a shallow copy of the current metrics."""
        return dict(self._metrics)

    # -- recording helpers ----------------------------------------------

    def record_operation_started(self):
        self._metrics["total_operations"] += 1

    def record_operation_result(self, success: bool):
        if success:
            self._metrics["successful_operations"] += 1
        else:
            self._metrics["failed_operations"] += 1

    def record_quality_result(self, result: str):
        if result == "passed":
            self._metrics["quality_checks_passed"] += 1
        elif result == "failed":
            self._metrics["quality_checks_failed"] += 1

    def record_approval_result(self, status: str):
        if status == "approved":
            self._metrics["approvals_granted"] += 1
        elif status == "rejected":
            self._metrics["approvals_rejected"] += 1

    def record_compliance_result(self, status: str):
        if status == "non_compliant":
            self._metrics["compliance_violations"] += 1

    # -- computed rates -------------------------------------------------

    @property
    def success_rate(self) -> float:
        return _safe_ratio(
            self._metrics["successful_operations"],
            self._metrics["total_operations"],
        )

    @property
    def quality_pass_rate(self) -> float:
        total = (
            self._metrics["quality_checks_passed"] +
            self._metrics["quality_checks_failed"]
        )
        return _safe_ratio(self._metrics["quality_checks_passed"], total)

    @property
    def approval_rate(self) -> float:
        total = self._metrics["approvals_granted"] + self._metrics["approvals_rejected"]
        return _safe_ratio(self._metrics["approvals_granted"], total)
