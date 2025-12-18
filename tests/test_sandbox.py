"""
Unit tests for the Docker sandbox runner.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import os


class TestDockerSandbox:
    """Tests for DockerSandbox functionality."""
    
    @patch('backend.sandbox.docker_runner.docker')
    @patch('backend.sandbox.docker_runner.get_settings')
    def test_sandbox_initialization(self, mock_settings, mock_docker):
        """Test sandbox initialization."""
        mock_settings.return_value = Mock(
            sandbox_timeout=60,
            sandbox_memory_limit="512m",
            sandbox_cpu_limit=1.0,
            sandbox_network_disabled=True
        )
        mock_docker.from_env.return_value = Mock()
        
        from backend.sandbox.docker_runner import DockerSandbox
        
        sandbox = DockerSandbox()
        
        assert sandbox.settings.sandbox_timeout == 60
        mock_docker.from_env.assert_called_once()
    
    @patch('backend.sandbox.docker_runner.docker')
    @patch('backend.sandbox.docker_runner.get_settings')
    def test_write_files(self, mock_settings, mock_docker):
        """Test file writing to temp directory."""
        mock_settings.return_value = Mock(
            sandbox_timeout=60,
            sandbox_memory_limit="512m",
            sandbox_cpu_limit=1.0,
            sandbox_network_disabled=True
        )
        mock_docker.from_env.return_value = Mock()
        
        from backend.sandbox.docker_runner import DockerSandbox
        
        sandbox = DockerSandbox()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            files = {
                "main.py": "print('hello')",
                "utils/helper.py": "def help(): pass"
            }
            
            sandbox._write_files(temp_dir, files)
            
            assert (Path(temp_dir) / "main.py").exists()
            assert (Path(temp_dir) / "utils" / "helper.py").exists()
            
            with open(Path(temp_dir) / "main.py") as f:
                assert f.read() == "print('hello')"
    
    @patch('backend.sandbox.docker_runner.docker')
    @patch('backend.sandbox.docker_runner.get_settings')
    def test_create_init_files(self, mock_settings, mock_docker):
        """Test __init__.py creation."""
        mock_settings.return_value = Mock(
            sandbox_timeout=60,
            sandbox_memory_limit="512m",
            sandbox_cpu_limit=1.0,
            sandbox_network_disabled=True
        )
        mock_docker.from_env.return_value = Mock()
        
        from backend.sandbox.docker_runner import DockerSandbox
        
        sandbox = DockerSandbox()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a subdirectory
            os.makedirs(Path(temp_dir) / "subdir")
            
            sandbox._create_init_files(temp_dir)
            
            assert (Path(temp_dir) / "__init__.py").exists()
            assert (Path(temp_dir) / "subdir" / "__init__.py").exists()
    
    @patch('backend.sandbox.docker_runner.docker')
    @patch('backend.sandbox.docker_runner.get_settings')
    def test_health_check_docker_available(self, mock_settings, mock_docker):
        """Test health check when Docker is available."""
        mock_settings.return_value = Mock(
            sandbox_timeout=60,
            sandbox_memory_limit="512m",
            sandbox_cpu_limit=1.0,
            sandbox_network_disabled=True
        )
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.version.return_value = {"Version": "24.0.0"}
        mock_client.images.get.side_effect = Exception("Not found")
        mock_docker.from_env.return_value = mock_client
        
        from backend.sandbox.docker_runner import DockerSandbox
        
        sandbox = DockerSandbox()
        health = sandbox.health_check()
        
        assert health["docker_available"] is True
        assert health["docker_version"] == "24.0.0"
    
    @patch('backend.sandbox.docker_runner.docker')
    @patch('backend.sandbox.docker_runner.get_settings')
    def test_get_image_fallback(self, mock_settings, mock_docker):
        """Test image selection fallback."""
        mock_settings.return_value = Mock(
            sandbox_timeout=60,
            sandbox_memory_limit="512m",
            sandbox_cpu_limit=1.0,
            sandbox_network_disabled=True
        )
        
        mock_client = Mock()
        mock_client.images.get.side_effect = Exception("Not found")
        mock_docker.from_env.return_value = mock_client
        
        from backend.sandbox.docker_runner import DockerSandbox
        
        sandbox = DockerSandbox()
        image = sandbox._get_image()
        
        assert image == DockerSandbox.SANDBOX_IMAGE


class TestSandboxResult:
    """Tests for SandboxResult dataclass."""
    
    def test_sandbox_result_creation(self):
        """Test SandboxResult creation."""
        from backend.sandbox.docker_runner import SandboxResult
        
        result = SandboxResult(
            success=True,
            exit_code=0,
            stdout="Test passed",
            stderr="",
            execution_time=1.5
        )
        
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Test passed"
        assert result.execution_time == 1.5
    
    def test_sandbox_result_with_error(self):
        """Test SandboxResult with error."""
        from backend.sandbox.docker_runner import SandboxResult
        
        result = SandboxResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="AssertionError",
            execution_time=0.5,
            error_message="Test failed"
        )
        
        assert result.success is False
        assert result.error_message == "Test failed"

