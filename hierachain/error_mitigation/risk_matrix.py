"""
Risk priority matrix for error severity assessment.

Uses impact vs likelihood matrix to determine priority levels.
"""

import logging

from hierachain.error_mitigation.classifier_types import PriorityLevel, ImpactLevel, LikelihoodLevel

logger = logging.getLogger(__name__)


class RiskPriorityMatrix:
    def __init__(self):
        self.matrix = {
            ImpactLevel.CATASTROPHIC: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.MEDIUM: PriorityLevel.CRITICAL,
                LikelihoodLevel.LOW: PriorityLevel.HIGH,
                LikelihoodLevel.VERY_LOW: PriorityLevel.HIGH,
            },
            ImpactLevel.MAJOR: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.HIGH: PriorityLevel.CRITICAL,
                LikelihoodLevel.MEDIUM: PriorityLevel.HIGH,
                LikelihoodLevel.LOW: PriorityLevel.HIGH,
                LikelihoodLevel.VERY_LOW: PriorityLevel.MEDIUM,
            },
            ImpactLevel.MODERATE: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.HIGH,
                LikelihoodLevel.HIGH: PriorityLevel.HIGH,
                LikelihoodLevel.MEDIUM: PriorityLevel.MEDIUM,
                LikelihoodLevel.LOW: PriorityLevel.MEDIUM,
                LikelihoodLevel.VERY_LOW: PriorityLevel.LOW,
            },
            ImpactLevel.MINOR: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.MEDIUM,
                LikelihoodLevel.HIGH: PriorityLevel.MEDIUM,
                LikelihoodLevel.MEDIUM: PriorityLevel.LOW,
                LikelihoodLevel.LOW: PriorityLevel.LOW,
                LikelihoodLevel.VERY_LOW: PriorityLevel.LOW,
            },
            ImpactLevel.NEGLIGIBLE: {
                LikelihoodLevel.VERY_HIGH: PriorityLevel.LOW,
                LikelihoodLevel.HIGH: PriorityLevel.LOW,
                LikelihoodLevel.MEDIUM: PriorityLevel.LOW,
                LikelihoodLevel.LOW: PriorityLevel.LOW,
                LikelihoodLevel.VERY_LOW: PriorityLevel.LOW,
            },
        }
        logger.info("Initialized RiskPriorityMatrix")

    def calculate_priority(
        self, impact: ImpactLevel, likelihood: LikelihoodLevel
    ) -> PriorityLevel:
        priority = self.matrix[impact][likelihood]
        logger.debug(
            "Priority calculated: %s + %s = %s",
            impact.name, likelihood.name, priority.name,
        )
        return priority
