"""
Test version management functionality for Hierarchical-Blockchain Framework.
"""

from hierarchical_blockchain.units.version import (
    get_version, get_complete_version, get_major_version, 
    get_documentation_status, compare_versions, VERSION
)


def test_get_version():
    """Test get_version function."""
    assert get_version((1, 0, 0, "final", 0)) == "1.0.0"
    assert get_version((2, 1, 3, "alpha", 0)) == "2.1.3-alpha"
    assert get_version((3, 2, 0, "beta", 1)) == "3.2.0-beta1"
    assert get_version((4, 0, 0, "rc", 2)) == "4.0.0-rc2"
    assert get_version((5, 0, 0, "dev", 0)) == "5.0.0.dev"


def test_get_complete_version():
    """Test get_complete_version function."""
    assert get_complete_version() == VERSION
    test_version = (1, 0, 0, "final", 0)
    assert get_complete_version(test_version) == test_version


def test_get_major_version():
    """Test get_major_version function."""
    assert get_major_version() == "0.0"
    assert get_major_version((1, 2, 3, "final", 0)) == "1.2"
    assert get_major_version((5, 10, 0, "beta", 1)) == "5.10"


def test_get_documentation_status():
    """Test get_documentation_status function."""
    assert get_documentation_status((1, 0, 0, "alpha", 0)) == "under development"
    assert get_documentation_status((1, 0, 0, "beta", 0)) == "in beta"
    assert get_documentation_status((1, 0, 0, "rc", 0)) == "release candidate"
    assert get_documentation_status((1, 0, 0, "final", 0)) == "stable"
    assert get_documentation_status((1, 0, 0, "dev", 0)) == "development"


def test_compare_versions():
    """Test compare_versions function."""
    # Test string version comparisons
    assert compare_versions("1.0.0", "1.0.1") == -1
    assert compare_versions("1.0.1", "1.0.0") == 1
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.0.alpha", "1.0.0.beta") == -1
    assert compare_versions("1.0.0.dev", "1.0.0.alpha") == -1
    assert compare_versions("1.0.0.final", "1.0.0.rc") == 1
    
    # Test tuple version comparisons
    assert compare_versions((1, 0, 0, "final", 0), (1, 0, 1, "final", 0)) == -1
    assert compare_versions((1, 0, 1, "final", 0), (1, 0, 0, "final", 0)) == 1
    assert compare_versions((1, 0, 0, "final", 0), (1, 0, 0, "final", 0)) == 0


def run_tests():
    """Run all tests."""
    test_get_version()
    test_get_complete_version()
    test_get_major_version()
    test_get_documentation_status()
    test_compare_versions()
    print("All tests passed!")
