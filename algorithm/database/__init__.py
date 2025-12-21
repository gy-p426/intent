"""
Database module for algorithm integration service.

This module provides database connectivity and schema information retrieval
for the algorithm integration service.
"""

from .schema_retriever import DatabaseSchemaRetriever

__all__ = ['DatabaseSchemaRetriever']