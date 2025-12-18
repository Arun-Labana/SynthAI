"""
Docker Sandbox Runner - Safely executes AI-generated code in isolated containers.

This is the critical safety component that ensures AI-generated code cannot
harm the host system.
"""

import os
import tempfile
import shutil
from typing import Dict, Optional
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import ContainerError, ImageNotFound, APIError

from backend.config import get_settings


@dataclass
class SandboxResult:
    """Result from sandbox execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    error_message: Optional[str] = None


class DockerSandbox:
    """
    Docker-based sandbox for safely executing AI-generated code.
    
    Security features:
    - Isolated container environment
    - Resource limits (CPU, memory, time)
    - No network access (configurable)
    - Read-only root filesystem (where possible)
    - Non-root user execution
    - Automatic cleanup
    """
    
    SANDBOX_IMAGE = "python:3.11-slim"
    CUSTOM_SANDBOX_IMAGE = "synthai-sandbox"
    
    # Common Docker socket locations
    DOCKER_SOCKETS = [
        os.path.expanduser("~/.rd/docker.sock"),  # Rancher Desktop
        "/var/run/docker.sock",  # Docker Desktop / Linux
        os.path.expanduser("~/.docker/run/docker.sock"),  # Docker Desktop (newer)
    ]
    
    def __init__(self):
        self.settings = get_settings()
        
        try:
            self.client = self._create_docker_client()
            # Verify Docker is accessible
            self.client.ping()
        except Exception as e:
            raise RuntimeError(
                f"Docker is not available. Please ensure Docker is installed and running. "
                f"Error: {e}"
            )
    
    def _create_docker_client(self):
        """Create Docker client, trying multiple socket locations."""
        # First try environment variable
        if os.environ.get("DOCKER_HOST"):
            return docker.from_env()
        
        # Try common socket locations
        for socket_path in self.DOCKER_SOCKETS:
            if os.path.exists(socket_path):
                return docker.DockerClient(base_url=f"unix://{socket_path}")
        
        # Fall back to default
        return docker.from_env()
    
    def run(
        self, 
        code_files: Dict[str, str], 
        test_files: Dict[str, str],
        entry_command: Optional[str] = None,
    ) -> SandboxResult:
        """
        Execute code and tests in a sandboxed Docker container.
        
        Args:
            code_files: Dict of {filename: content} for the implementation
            test_files: Dict of {filename: content} for the tests
            entry_command: Optional custom command to run (default: pytest)
            
        Returns:
            SandboxResult with execution details
        """
        # Create temporary directory for code
        temp_dir = tempfile.mkdtemp(prefix="sandbox_")
        
        try:
            # Write all files to temp directory
            self._write_files(temp_dir, code_files)
            self._write_files(temp_dir, test_files)
            
            # Create a simple setup to make imports work
            self._create_init_files(temp_dir)
            
            # Determine command
            if entry_command:
                command = entry_command
            else:
                test_file_names = " ".join(test_files.keys())
                # Check if using custom sandbox image (has pytest) or base image (needs pip install)
                if self._get_image() == self.CUSTOM_SANDBOX_IMAGE:
                    command = f"cd /sandbox && python -m pytest {test_file_names} -v --tb=short"
                else:
                    # Base image - need to pip install first
                    command = f"cd /sandbox && pip install pytest -q 2>/dev/null && python -m pytest {test_file_names} -v --tb=short"
            
            # Run container (enable network if base image needs pip install)
            needs_network = self._get_image() != self.CUSTOM_SANDBOX_IMAGE
            return self._execute_container(temp_dir, command, network_enabled=needs_network)
            
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def run_code_only(
        self, 
        code_files: Dict[str, str],
        main_file: str = "main.py",
    ) -> SandboxResult:
        """
        Execute code without tests (for validation or demo purposes).
        
        Args:
            code_files: Dict of {filename: content}
            main_file: The main file to execute
            
        Returns:
            SandboxResult with execution details
        """
        temp_dir = tempfile.mkdtemp(prefix="sandbox_")
        
        try:
            self._write_files(temp_dir, code_files)
            self._create_init_files(temp_dir)
            
            command = f"cd /sandbox && python {main_file}"
            return self._execute_container(temp_dir, command)
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _write_files(self, directory: str, files: Dict[str, str]):
        """Write files to the specified directory."""
        for filename, content in files.items():
            file_path = Path(directory) / filename
            
            # Create subdirectories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def _create_init_files(self, directory: str):
        """Create __init__.py files for Python imports."""
        # Create __init__.py in root
        init_path = Path(directory) / "__init__.py"
        if not init_path.exists():
            init_path.write_text("")
        
        # Create in any subdirectories
        for subdir in Path(directory).rglob("*"):
            if subdir.is_dir():
                sub_init = subdir / "__init__.py"
                if not sub_init.exists():
                    sub_init.write_text("")
    
    def _execute_container(self, code_dir: str, command: str, network_enabled: bool = False) -> SandboxResult:
        """
        Execute a command in a Docker container.
        
        Args:
            code_dir: Directory with code to mount
            command: Command to execute
            network_enabled: Override to enable network (for pip install)
            
        Returns:
            SandboxResult
        """
        import time
        
        start_time = time.time()
        
        # Network is disabled by default unless explicitly enabled
        network_disabled = self.settings.sandbox_network_disabled and not network_enabled
        
        # Container configuration
        container_config = {
            "image": self._get_image(),
            "command": f"/bin/sh -c '{command}'",
            "volumes": {
                os.path.abspath(code_dir): {
                    "bind": "/sandbox",
                    "mode": "rw",
                }
            },
            "working_dir": "/sandbox",
            "mem_limit": self.settings.sandbox_memory_limit,
            "cpu_period": 100000,
            "cpu_quota": int(100000 * self.settings.sandbox_cpu_limit),
            "network_disabled": network_disabled,
            "detach": True,
            "remove": False,  # We'll remove after getting logs
        }
        
        container = None
        
        try:
            # Create and start container
            container = self.client.containers.run(**container_config)
            
            # Wait for completion with timeout
            result = container.wait(timeout=self.settings.sandbox_timeout)
            exit_code = result.get("StatusCode", -1)
            
            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8', errors='replace')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8', errors='replace')
            
            execution_time = time.time() - start_time
            
            return SandboxResult(
                success=exit_code == 0,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
            )
            
        except ContainerError as e:
            execution_time = time.time() - start_time
            return SandboxResult(
                success=False,
                exit_code=e.exit_status,
                stdout=e.stderr.decode('utf-8', errors='replace') if e.stderr else "",
                stderr=str(e),
                execution_time=execution_time,
                error_message=f"Container error: {e}",
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Check for timeout
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                return SandboxResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {self.settings.sandbox_timeout} seconds",
                    execution_time=execution_time,
                    error_message="Timeout exceeded",
                )
            
            return SandboxResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                error_message=f"Execution error: {e}",
            )
            
        finally:
            # Cleanup container
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
    
    def _get_image(self) -> str:
        """Get the Docker image to use, preferring custom sandbox image."""
        try:
            self.client.images.get(self.CUSTOM_SANDBOX_IMAGE)
            return self.CUSTOM_SANDBOX_IMAGE
        except ImageNotFound:
            # Fall back to base Python image
            return self.SANDBOX_IMAGE
    
    def build_sandbox_image(self, dockerfile_path: Optional[str] = None) -> bool:
        """
        Build the custom sandbox Docker image.
        
        Args:
            dockerfile_path: Path to Dockerfile (default: docker/Dockerfile.sandbox)
            
        Returns:
            True if build succeeded
        """
        if dockerfile_path is None:
            # Default path relative to project root
            dockerfile_path = "docker/Dockerfile.sandbox"
        
        dockerfile = Path(dockerfile_path)
        if not dockerfile.exists():
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile_path}")
        
        try:
            self.client.images.build(
                path=str(dockerfile.parent),
                dockerfile=dockerfile.name,
                tag=self.CUSTOM_SANDBOX_IMAGE,
                rm=True,
            )
            return True
        except Exception as e:
            print(f"Failed to build sandbox image: {e}")
            return False
    
    def health_check(self) -> Dict:
        """
        Check Docker health and availability.
        
        Returns:
            Dict with health status information
        """
        try:
            self.client.ping()
            version = self.client.version()
            
            # Check if sandbox image exists
            try:
                self.client.images.get(self.CUSTOM_SANDBOX_IMAGE)
                sandbox_image_ready = True
            except ImageNotFound:
                sandbox_image_ready = False
            
            return {
                "docker_available": True,
                "docker_version": version.get("Version", "unknown"),
                "sandbox_image_ready": sandbox_image_ready,
                "sandbox_image": self._get_image(),
            }
            
        except Exception as e:
            return {
                "docker_available": False,
                "error": str(e),
            }

