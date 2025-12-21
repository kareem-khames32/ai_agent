"""
Logging utility with timestamps for latency tracking
"""
import time
import logging
from typing import Optional
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)-5s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name"""
    return logging.getLogger(name)


class LatencyTracker:
    """Track latency at various pipeline stages"""

    def __init__(self, call_id: str):
        self.call_id = call_id
        self.logger = get_logger(f"latency.{call_id[:8]}")
        self.markers: dict[str, float] = {}

    def mark(self, event: str):
        """Mark a timestamp for an event"""
        self.markers[event] = time.time()
        self.logger.debug(f"MARK: {event}")

    def measure(self, start_event: str, end_event: str) -> Optional[float]:
        """Measure time between two events in milliseconds"""
        if start_event in self.markers and end_event in self.markers:
            latency_ms = (self.markers[end_event] - self.markers[start_event]) * 1000
            self.logger.info(f"{start_event} -> {end_event}: {latency_ms:.0f}ms")
            return latency_ms
        return None

    def since(self, event: str) -> Optional[float]:
        """Time since an event in milliseconds"""
        if event in self.markers:
            return (time.time() - self.markers[event]) * 1000
        return None

    def report(self):
        """Log a full latency report"""
        self.logger.info("=== Latency Report ===")

        # Key metrics
        metrics = [
            ("speech_end", "first_audio_byte", "E2E Latency"),
            ("speech_end", "stt_final", "STT Latency"),
            ("llm_start", "llm_first_token", "LLM TTFT"),
            ("tts_start", "tts_first_byte", "TTS TTFB"),
            ("bargein_detected", "bargein_handled", "Barge-in"),
        ]

        for start, end, name in metrics:
            latency = self.measure(start, end)
            if latency:
                self.logger.info(f"  {name}: {latency:.0f}ms")


def log_latency(event_name: str):
    """Decorator to log function execution time"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            logger = get_logger(func.__module__)
            logger.debug(f"{event_name}: {elapsed:.1f}ms")
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            logger = get_logger(func.__module__)
            logger.debug(f"{event_name}: {elapsed:.1f}ms")
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


import asyncio  # Import at end to avoid circular
