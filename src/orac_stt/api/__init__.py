"""
API module for ORAC STT.

This module contains the REST API endpoints and related functionality
for the ORAC Speech-to-Text service.
"""

from . import health, metrics, stt

__all__ = ["health", "metrics", "stt"]