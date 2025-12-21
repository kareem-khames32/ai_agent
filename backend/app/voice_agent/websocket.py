"""
WebSocket Server for Voice Agent
Handles real-time audio streaming between client and agent
"""
import json
import asyncio
import base64
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .agent import VoiceAgent, AgentState
from .config import VoiceAgentConfig, get_config
from .utils.logger import get_logger

logger = get_logger(__name__)


class VoiceWebSocketHandler:
    """
    WebSocket handler for voice agent

    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 PCM>"}
    - Client sends: {"type": "config", "system_prompt": "...", "assistant_id": "..."}
    - Server sends: {"type": "audio", "data": "<base64 PCM>"}
    - Server sends: {"type": "transcript", "text": "...", "is_final": true/false}
    - Server sends: {"type": "response", "text": "..."}
    - Server sends: {"type": "state", "state": "listening|processing|speaking"}
    """

    def __init__(self, websocket: WebSocket, config: Optional[VoiceAgentConfig] = None):
        self.websocket = websocket
        self.config = config or get_config()
        self.agent: Optional[VoiceAgent] = None
        self._is_connected = False

    async def handle(self):
        """Main handler loop"""
        await self.websocket.accept()
        self._is_connected = True
        logger.info("🔌 WebSocket connected")

        try:
            # Create agent
            self.agent = VoiceAgent(self.config)

            # Set up callbacks
            self.agent.on_audio_output = self._send_audio
            self.agent.on_transcript = self._send_transcript
            self.agent.on_response = self._send_response
            self.agent.on_state_change = self._send_state

            # Wait for config message before starting
            await self._wait_for_config()

            # Process messages
            await self._message_loop()

        except WebSocketDisconnect:
            logger.info("🔌 WebSocket disconnected by client")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self._cleanup()

    async def _wait_for_config(self):
        """Wait for initial config message"""
        logger.debug("Waiting for config message...")

        while self._is_connected:
            try:
                data = await asyncio.wait_for(
                    self.websocket.receive_json(),
                    timeout=30.0
                )

                if data.get("type") == "config":
                    system_prompt = data.get("system_prompt", "")
                    assistant_id = data.get("assistant_id")

                    logger.info(f"📋 Config received (assistant_id={assistant_id})")

                    # Start agent with system prompt
                    await self.agent.start(system_prompt)

                    # Send ready message
                    await self._send_message({
                        "type": "ready",
                        "call_id": self.agent.call_id
                    })

                    return

                elif data.get("type") == "audio":
                    # Audio before config, start with default
                    await self.agent.start()
                    await self._handle_audio(data)
                    return

            except asyncio.TimeoutError:
                logger.warning("Config timeout, starting with defaults")
                await self.agent.start()
                return

    async def _message_loop(self):
        """Main message processing loop"""
        while self._is_connected and self.websocket.client_state == WebSocketState.CONNECTED:
            try:
                data = await asyncio.wait_for(
                    self.websocket.receive_json(),
                    timeout=60.0
                )

                msg_type = data.get("type")

                if msg_type == "audio":
                    await self._handle_audio(data)
                elif msg_type == "stop":
                    logger.info("Stop requested")
                    break
                elif msg_type == "ping":
                    await self._send_message({"type": "pong"})
                else:
                    logger.warning(f"Unknown message type: {msg_type}")

            except asyncio.TimeoutError:
                # Send keepalive
                await self._send_message({"type": "ping"})
            except WebSocketDisconnect:
                raise
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                logger.error(f"Message loop error: {e}")
                break

    async def _handle_audio(self, data: dict):
        """Handle incoming audio data"""
        audio_b64 = data.get("data")
        if not audio_b64:
            return

        try:
            audio_bytes = base64.b64decode(audio_b64)
            await self.agent.process_audio(audio_bytes)
        except Exception as e:
            logger.error(f"Audio processing error: {e}")

    async def _send_audio(self, audio_chunk: bytes):
        """Send audio to client"""
        if not self._is_connected:
            return

        try:
            audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
            await self._send_message({
                "type": "audio",
                "data": audio_b64
            })
        except Exception as e:
            logger.error(f"Send audio error: {e}")

    async def _send_transcript(self, text: str, is_final: bool):
        """Send transcript to client"""
        if not self._is_connected:
            return

        await self._send_message({
            "type": "transcript",
            "text": text,
            "is_final": is_final
        })

    async def _send_response(self, text: str):
        """Send AI response to client"""
        if not self._is_connected:
            return

        await self._send_message({
            "type": "response",
            "text": text
        })

    async def _send_state(self, state: AgentState):
        """Send state change to client"""
        if not self._is_connected:
            return

        await self._send_message({
            "type": "state",
            "state": state.value
        })

    async def _send_message(self, message: dict):
        """Send JSON message to client"""
        if not self._is_connected:
            return

        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Send message error: {e}")
            self._is_connected = False

    async def _cleanup(self):
        """Clean up resources"""
        self._is_connected = False

        if self.agent:
            await self.agent.stop()

        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.close()
        except Exception:
            pass

        logger.info("🔌 WebSocket cleanup complete")


async def voice_websocket_endpoint(websocket: WebSocket):
    """FastAPI WebSocket endpoint"""
    handler = VoiceWebSocketHandler(websocket)
    await handler.handle()
