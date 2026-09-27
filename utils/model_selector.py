"""Compatibility import for the production async model selector.

Tests must mock the provider API explicitly; this module never fabricates answers.
"""
from utils.universal_model import ModelSelector

__all__ = ["ModelSelector"]
