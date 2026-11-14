# tests/core/conftest.py
"""Unit-level directory: dialect facts only, no database.

The tests here construct a dialect and inspect what it declares; no fixture
asks for a connection, so this directory declares no ``prepare`` / ``teardown``
contract and owns no logical database.  It exists because a test directory has
to say why it needs nothing, rather than leaving that to be inferred from a
missing conftest.
"""
