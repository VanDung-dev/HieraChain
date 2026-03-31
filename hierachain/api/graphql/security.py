"""
GraphQL Security Module

Provides security measures for GraphQL queries:
- Query depth limiting
- Query complexity analysis
- Introspection query detection
- Rate limiting per IP
"""

import time
import re
from collections import defaultdict
from threading import Lock

# Security configuration
MAX_QUERY_DEPTH = 10
MAX_COMPLEXITY = 1000
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # seconds


class GraphQLSecurity:
    """GraphQL security manager with rate limiting and query analysis."""
    
    def __init__(self):
        self._lock = Lock()
        self._request_counts: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every 60 seconds
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """
        Check if client IP has exceeded rate limit.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if within rate limit, False if exceeded
        """
        now = time.time()
        
        with self._lock:
            # Periodic cleanup
            self._maybe_cleanup(now)
            
            # Get requests within window
            cutoff = now - RATE_LIMIT_WINDOW
            self._request_counts[client_ip] = [
                ts for ts in self._request_counts[client_ip] if ts > cutoff
            ]
            
            # Check limit
            if len(self._request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
                return False
            
            # Record this request
            self._request_counts[client_ip].append(now)
            return True
    
    def _maybe_cleanup(self, now: float) -> None:
        """Periodic cleanup of old entries."""
        if now - self._last_cleanup > self._cleanup_interval:
            cutoff = now - RATE_LIMIT_WINDOW
            for ip in list(self._request_counts.keys()):
                self._request_counts[ip] = [
                    ts for ts in self._request_counts[ip] if ts > cutoff
                ]
                if not self._request_counts[ip]:
                    del self._request_counts[ip]
            self._last_cleanup = now


# Singleton instance
_security = GraphQLSecurity()


def check_rate_limit(client_ip: str) -> bool:
    """Check if client IP is within rate limit."""
    return _security.check_rate_limit(client_ip)


def is_introspection_query(query: str) -> bool:
    """
    Check if query is an introspection query.
    
    Args:
        query: GraphQL query string
        
    Returns:
        True if introspection query detected
    """
    # Check for common introspection patterns
    introspection_patterns = [
        r"__schema",
        r"__type",
        r"__typename",
        r"query\s+\{\s*__schema",
        r"query\s+\{\s*__type",
    ]
    
    query_lower = query.lower()
    for pattern in introspection_patterns:
        if re.search(pattern, query_lower):
            return True
    
    return False


def get_query_depth(query: str) -> int:
    """
    Calculate the depth of a GraphQL query.
    
    Args:
        query: GraphQL query string
        
    Returns:
        Maximum depth of the query
    """
    # Remove comments
    query = re.sub(r'#[^\n]*', '', query)
    
    # Simple depth calculation based on indentation and braces
    max_depth = 0
    current_depth = 0
    
    # Count opening and closing braces
    for char in query:
        if char == '{':
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char == '}':
            current_depth = max(0, current_depth - 1)
    
    return max_depth


def estimate_complexity(query: str) -> int:
    """
    Estimate the complexity of a GraphQL query.
    
    Simple heuristic based on:
    - Number of fields requested
    - Number of list iterations
    - Nested query depth
    
    Args:
        query: GraphQL query string
        
    Returns:
        Estimated complexity score
    """
    # Remove comments and strings
    query = re.sub(r'#[^\n]*', '', query)
    query = re.sub(r'"[^"]*"', '""', query)
    
    complexity = 0
    
    # Count field selections
    field_matches = re.findall(r'\b\w+\s*\{', query)
    complexity += len(field_matches) * 2
    
    # Count list operations (connection patterns)
    list_patterns = re.findall(r'(first|last|after|before|limit)\s*:\s*\d+', query)
    complexity += len(list_patterns) * 5
    
    # Add depth factor
    depth = get_query_depth(query)
    complexity += depth * 3
    
    # Count fragments
    fragment_count = len(re.findall(r'fragment\s+\w+', query))
    complexity += fragment_count * 10
    
    return complexity