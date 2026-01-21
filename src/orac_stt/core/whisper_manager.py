"""Whisper-server process manager with health monitoring and auto-restart."""

import asyncio
import os
import signal
import subprocess
import time
from datetime import datetime
from typing import Optional

import requests

from ..utils.logging import get_logger

logger = get_logger(__name__)


class WhisperServerManager:
    """Manages the whisper-server subprocess with health monitoring."""

    # Whisper-server configuration (matches entrypoint.sh)
    WHISPER_SERVER_BIN = "/app/third_party/whisper_cpp/bin/whisper-server"
    WHISPER_MODELS_DIR = "/app/models/whisper_cpp/whisper"
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8080

    MODEL_MAP = {
        "whisper-tiny": "ggml-tiny.bin",
        "whisper-base": "ggml-base.bin",
        "whisper-small": "ggml-small.bin",
        "whisper-medium": "ggml-medium.bin",
        "whisper-large": "ggml-large-v3.bin",
        "whisper-large-v3": "ggml-large-v3.bin",
    }

    def __init__(
        self,
        host: str = None,
        port: int = None,
        model_name: str = None,
        prompt: str = None,
        health_check_interval: float = 60.0,
        health_check_timeout: float = 5.0,
        max_consecutive_failures: int = 2,
    ):
        """Initialize whisper-server manager.

        Args:
            host: Server host (default from env or 127.0.0.1)
            port: Server port (default from env or 8080)
            model_name: Model name (default from env or whisper-base)
            prompt: Whisper prompt for biasing (default from env)
            health_check_interval: Seconds between health checks
            health_check_timeout: Timeout for health check requests
            max_consecutive_failures: Failures before restart
        """
        self.host = host or os.environ.get("WHISPER_SERVER_HOST", self.DEFAULT_HOST)
        self.port = port or int(os.environ.get("WHISPER_SERVER_PORT", self.DEFAULT_PORT))
        self.model_name = model_name or os.environ.get("MODEL_NAME", "whisper-base")
        self.prompt = prompt or os.environ.get(
            "WHISPER_PROMPT",
            "lounge cabinet lights kitchen bedroom bathroom office"
        )

        self.server_url = f"http://{self.host}:{self.port}"
        self.health_check_interval = health_check_interval
        self.health_check_timeout = health_check_timeout
        self.max_consecutive_failures = max_consecutive_failures

        # State tracking
        self._process: Optional[subprocess.Popen] = None
        self._restart_count = 0
        self._consecutive_failures = 0
        self._last_health_check: Optional[datetime] = None
        self._last_healthy: Optional[datetime] = None
        self._running = False
        self._watchdog_task: Optional[asyncio.Task] = None
        self._session = requests.Session()

        logger.info(
            f"WhisperServerManager initialized: {self.server_url}, "
            f"model={self.model_name}, check_interval={health_check_interval}s"
        )

    @property
    def model_path(self) -> str:
        """Get full path to the whisper model file."""
        model_file = self.MODEL_MAP.get(self.model_name, "ggml-base.bin")
        return os.path.join(self.WHISPER_MODELS_DIR, model_file)

    def is_healthy(self) -> bool:
        """Check if whisper-server is responding to requests.

        Returns:
            True if server responds, False otherwise
        """
        try:
            response = self._session.get(
                self.server_url,
                timeout=self.health_check_timeout
            )
            healthy = response.status_code == 200

            if healthy:
                self._last_healthy = datetime.utcnow()
                self._consecutive_failures = 0

            return healthy

        except requests.exceptions.Timeout:
            logger.warning(f"Whisper-server health check timed out after {self.health_check_timeout}s")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning(f"Whisper-server not reachable at {self.server_url}")
            return False
        except Exception as e:
            logger.warning(f"Whisper-server health check failed: {e}")
            return False

    def _find_existing_process(self) -> Optional[int]:
        """Find PID of existing whisper-server process.

        Returns:
            PID if found, None otherwise
        """
        try:
            result = subprocess.run(
                ["pgrep", "-f", "whisper-server.*--port"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                if pids and pids[0]:
                    return int(pids[0])
        except Exception as e:
            logger.warning(f"Failed to find whisper-server process: {e}")
        return None

    def _kill_existing(self) -> bool:
        """Kill any existing whisper-server process.

        Returns:
            True if a process was killed, False otherwise
        """
        pid = self._find_existing_process()
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to whisper-server (PID {pid})")

                # Wait for process to terminate
                for _ in range(10):
                    time.sleep(0.5)
                    try:
                        os.kill(pid, 0)  # Check if still running
                    except OSError:
                        logger.info(f"whisper-server (PID {pid}) terminated")
                        return True

                # Force kill if still running
                logger.warning(f"whisper-server (PID {pid}) didn't terminate, sending SIGKILL")
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)
                return True

            except ProcessLookupError:
                logger.info(f"whisper-server (PID {pid}) already terminated")
                return True
            except Exception as e:
                logger.error(f"Failed to kill whisper-server (PID {pid}): {e}")
        return False

    def start(self) -> bool:
        """Start the whisper-server subprocess.

        Returns:
            True if started successfully, False otherwise
        """
        if not os.path.exists(self.WHISPER_SERVER_BIN):
            logger.error(f"whisper-server binary not found: {self.WHISPER_SERVER_BIN}")
            return False

        if not os.path.exists(self.model_path):
            logger.error(f"Whisper model not found: {self.model_path}")
            return False

        # Kill any existing process first
        self._kill_existing()

        try:
            cmd = [
                self.WHISPER_SERVER_BIN,
                "--model", self.model_path,
                "--host", self.host,
                "--port", str(self.port),
                "--no-timestamps",
                "--language", "en",
                "--prompt", self.prompt,
            ]

            logger.info(f"Starting whisper-server: {' '.join(cmd)}")

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            logger.info(f"whisper-server started with PID {self._process.pid}")

            # Wait for server to be ready
            return self._wait_for_ready()

        except Exception as e:
            logger.error(f"Failed to start whisper-server: {e}")
            return False

    def _wait_for_ready(self, timeout: float = 60.0) -> bool:
        """Wait for whisper-server to become ready.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if server became ready, False if timeout
        """
        start = time.time()
        check_interval = 1.0

        logger.info(f"Waiting for whisper-server to be ready (timeout={timeout}s)...")

        while time.time() - start < timeout:
            if self.is_healthy():
                elapsed = time.time() - start
                logger.info(f"whisper-server ready after {elapsed:.1f}s")
                return True
            time.sleep(check_interval)

        logger.error(f"whisper-server not ready after {timeout}s")
        return False

    def stop(self) -> bool:
        """Stop the whisper-server subprocess.

        Returns:
            True if stopped successfully
        """
        self._running = False

        # Cancel watchdog task
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()

        # Kill the process
        return self._kill_existing()

    def restart(self) -> bool:
        """Restart the whisper-server subprocess.

        Returns:
            True if restarted successfully
        """
        self._restart_count += 1
        logger.info(f"Restarting whisper-server (restart #{self._restart_count})...")

        self.stop()
        time.sleep(0.5)  # Brief pause

        success = self.start()

        if success:
            logger.info(f"whisper-server restarted successfully (restart #{self._restart_count})")
        else:
            logger.error(f"Failed to restart whisper-server (attempt #{self._restart_count})")

        return success

    async def start_watchdog(self):
        """Start the background health monitoring task."""
        if self._running:
            logger.warning("Watchdog already running")
            return

        self._running = True
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        logger.info(f"Whisper watchdog started (interval={self.health_check_interval}s)")

    async def _watchdog_loop(self):
        """Background loop that monitors whisper-server health."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)

                if not self._running:
                    break

                self._last_health_check = datetime.utcnow()
                healthy = self.is_healthy()

                if not healthy:
                    self._consecutive_failures += 1
                    logger.warning(
                        f"Whisper-server unhealthy "
                        f"({self._consecutive_failures}/{self.max_consecutive_failures})"
                    )

                    if self._consecutive_failures >= self.max_consecutive_failures:
                        logger.error(
                            f"Whisper-server unresponsive for "
                            f"{self._consecutive_failures} consecutive checks, restarting..."
                        )

                        # Run restart in executor to avoid blocking
                        loop = asyncio.get_event_loop()
                        success = await loop.run_in_executor(None, self.restart)

                        if not success:
                            logger.error(
                                "Failed to restart whisper-server, "
                                "exiting to trigger container restart"
                            )
                            os._exit(1)

                        self._consecutive_failures = 0
                else:
                    if self._consecutive_failures > 0:
                        logger.info("Whisper-server recovered")
                    self._consecutive_failures = 0

            except asyncio.CancelledError:
                logger.info("Whisper watchdog cancelled")
                break
            except Exception as e:
                logger.error(f"Whisper watchdog error: {e}")

    def get_status(self) -> dict:
        """Get current whisper-server status.

        Returns:
            Status dictionary
        """
        return {
            "server_url": self.server_url,
            "model_name": self.model_name,
            "is_healthy": self.is_healthy(),
            "restart_count": self._restart_count,
            "consecutive_failures": self._consecutive_failures,
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "last_healthy": self._last_healthy.isoformat() if self._last_healthy else None,
            "watchdog_running": self._running,
        }


# Global instance
_whisper_manager: Optional[WhisperServerManager] = None


def get_whisper_manager() -> WhisperServerManager:
    """Get or create the global WhisperServerManager instance."""
    global _whisper_manager
    if _whisper_manager is None:
        _whisper_manager = WhisperServerManager()
    return _whisper_manager
