"""
Unit tests for API dependencies

Following TDD approach: Write tests FIRST
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.dependencies import get_orchestrator, reset_orchestrator
from src.orchestrator_old import Orchestrator


class TestGetOrchestrator:
    """Test get_orchestrator dependency injection"""

    def test_get_orchestrator_returns_orchestrator_instance(self):
        """Should return an Orchestrator instance"""
        # Arrange & Act
        orchestrator = get_orchestrator()

        # Assert
        assert orchestrator is not None
        assert isinstance(orchestrator, Orchestrator)

    def test_get_orchestrator_returns_singleton(self):
        """Should return the SAME instance on multiple calls (singleton pattern)"""
        # Arrange & Act
        orchestrator1 = get_orchestrator()
        orchestrator2 = get_orchestrator()

        # Assert
        assert orchestrator1 is orchestrator2
        assert id(orchestrator1) == id(orchestrator2)

    def test_get_orchestrator_initializes_once(self):
        """Should only initialize Orchestrator once"""
        # Arrange
        reset_orchestrator()  # Reset singleton

        # Act
        with patch.object(Orchestrator, 'init') as mock_init:
            orchestrator1 = get_orchestrator()
            orchestrator2 = get_orchestrator()
            orchestrator3 = get_orchestrator()

        # Assert
        # init() should be called only once despite 3 calls
        assert mock_init.call_count == 1

    def test_reset_orchestrator_clears_singleton(self):
        """reset_orchestrator should clear the singleton for testing"""
        # Arrange
        orchestrator1 = get_orchestrator()

        # Act
        reset_orchestrator()
        orchestrator2 = get_orchestrator()

        # Assert
        assert orchestrator1 is not orchestrator2
        assert id(orchestrator1) != id(orchestrator2)

    def test_get_orchestrator_loads_existing_config(self):
        """Should attempt to load existing config if available"""
        # Arrange
        reset_orchestrator()

        # Act
        with patch.object(Orchestrator, 'init') as mock_init:
            orchestrator = get_orchestrator()

        # Assert
        mock_init.assert_called_once()
        # Orchestrator should be initialized
        assert orchestrator is not None

    def test_get_orchestrator_handles_config_load_error(self):
        """Should handle gracefully if config doesn't exist yet"""
        # Arrange
        reset_orchestrator()

        # Act & Assert - should not raise exception
        orchestrator = get_orchestrator()
        assert orchestrator is not None


class TestDependencyInjection:
    """Test that dependency can be used in FastAPI"""

    def test_can_be_used_as_fastapi_dependency(self):
        """get_orchestrator should be usable with Depends()"""
        from fastapi import Depends

        # This should not raise any errors
        # FastAPI will inspect the function signature
        def route_handler(orchestrator: Orchestrator = Depends(get_orchestrator)):
            return orchestrator

        # Verify it's a callable
        assert callable(get_orchestrator)

        # Verify return type annotation exists (FastAPI needs this)
        import inspect
        sig = inspect.signature(get_orchestrator)
        assert sig.return_annotation == Orchestrator
