"""
Algorithm Integration Service Package

This package provides algorithm integration capabilities for the intent recognition service,
including algorithm routing, parameter extraction, NL2SQL integration, and algorithm execution.
"""

# Core service and interfaces
from .service import AlgorithmIntegrationService
from .interfaces import *
from .models import *
from .config_manager import AlgorithmConfigManager, get_algorithm_config_manager

# Component implementations
from .router import AlgorithmRouter
from .extractor import ParameterExtractor
from .clients import NL2SQLClient
from .executor import AlgorithmExecutor
from .streaming import StreamingResponseHandler
from .tasks import TaskManager
from .processors import DataProcessor

__version__ = "1.0.0"
__author__ = "Algorithm Integration Team"

__all__ = [
    # Core service
    'AlgorithmIntegrationService',
    
    # Configuration
    'AlgorithmConfigManager',
    'get_algorithm_config_manager',
    
    # Component implementations
    'AlgorithmRouter',
    'ParameterExtractor',
    'NL2SQLClient',
    'AlgorithmExecutor',
    'StreamingResponseHandler',
    'TaskManager',
    'DataProcessor',
    
    # Models and interfaces are exported via * imports
]