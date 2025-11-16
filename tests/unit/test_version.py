"""
Test version management functionality for Hierarchical-Blockchain Framework.
"""

import unittest
from hierarchical_blockchain.units.version import (
    get_version, get_complete_version, get_major_version, 
    get_documentation_status, compare_versions, VERSION
)


class TestVersion(unittest.TestCase):
    """Test version management functions."""
    
    def test_get_version(self):
        """Test get_version function."""
        self.assertEqual(get_version((1, 0, 0, "final", 0)), "1.0.0")
        self.assertEqual(get_version((2, 1, 3, "alpha", 0)), "2.1.3-alpha")
        self.assertEqual(get_version((3, 2, 0, "beta", 1)), "3.2.0-beta1")
        self.assertEqual(get_version((4, 0, 0, "rc", 2)), "4.0.0-rc2")
        self.assertEqual(get_version((5, 0, 0, "dev", 0)), "5.0.0.dev")
    
    def test_get_complete_version(self):
        """Test get_complete_version function."""
        self.assertEqual(get_complete_version(), VERSION)
        test_version = (1, 0, 0, "final", 0)
        self.assertEqual(get_complete_version(test_version), test_version)
    
    def test_get_major_version(self):
        """Test get_major_version function."""
        self.assertEqual(get_major_version(), "0.0")
        self.assertEqual(get_major_version((1, 2, 3, "final", 0)), "1.2")
        self.assertEqual(get_major_version((5, 10, 0, "beta", 1)), "5.10")
    
    def test_get_documentation_status(self):
        """Test get_documentation_status function."""
        self.assertEqual(get_documentation_status((1, 0, 0, "alpha", 0)), "under development")
        self.assertEqual(get_documentation_status((1, 0, 0, "beta", 0)), "in beta")
        self.assertEqual(get_documentation_status((1, 0, 0, "rc", 0)), "release candidate")
        self.assertEqual(get_documentation_status((1, 0, 0, "final", 0)), "stable")
        self.assertEqual(get_documentation_status((1, 0, 0, "dev", 0)), "development")
    
    def test_compare_versions(self):
        """Test compare_versions function."""
        # Test string version comparisons
        self.assertEqual(compare_versions("1.0.0", "1.0.1"), -1)
        self.assertEqual(compare_versions("1.0.1", "1.0.0"), 1)
        self.assertEqual(compare_versions("1.0.0", "1.0.0"), 0)
        self.assertEqual(compare_versions("1.0.0.alpha", "1.0.0.beta"), -1)
        self.assertEqual(compare_versions("1.0.0.dev", "1.0.0.alpha"), -1)
        self.assertEqual(compare_versions("1.0.0.final", "1.0.0.rc"), 1)
        
        # Test tuple version comparisons
        self.assertEqual(compare_versions((1, 0, 0, "final", 0), (1, 0, 1, "final", 0)), -1)
        self.assertEqual(compare_versions((1, 0, 1, "final", 0), (1, 0, 0, "final", 0)), 1)
        self.assertEqual(compare_versions((1, 0, 0, "final", 0), (1, 0, 0, "final", 0)), 0)


if __name__ == '__main__':
    unittest.main()