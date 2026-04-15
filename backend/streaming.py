"""
Ombra Streaming Engine
======================
Real-time SSE streaming of tool execution output.
Provides progressive output as tools run, with event batching
and backpressure support.
"""

import json
import asyncio
import time
import uuid
from typing import AsyncGenerator, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class StreamEventType(str, Enum):
    TOOL_START = "tool_start"
    TOOL_PROGRESS = "tool_progress"
    TOOL_OUTPUT = "tool_output"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"
    TEXT_CHUNK = "text_chunk"
    AGENT_THINK = "agent_think"
    SUB_AGENT_START = "sub_agent_start"
    SUB_AGENT_END = "sub_agent_end"
    HOOK_FIRED = "hook_fired"
    CONTEXT_UPDATE = "context_update"
    DONE = "done"


@dataclass
class StreamEvent:
    """A single streaming event."""
    type: StreamEventType
    data: dict
    timestamp: str = ""
    id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.id:
            self.id = uuid.uuid4().hex[:8]

    def to_sse(self) -> str:
        """Format as SSE event string."""
        payload = {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "id": self.id,
        }
        return f"data: {json.dumps(payload)}\n\n"


class StreamChannel:
    """
    A streaming channel that tools can write to and clients can read from.
    Supports multiple consumers via asyncio.Queue.
    """

    def __init__(self, channel_id: str = None, max_buffer: int = 500):
        self.id = channel_id or uuid.uuid4().hex[:12]
        self._queues: list[asyncio.Queue] = []
        self._history: list[StreamEvent] = []
        self._max_buffer = max_buffer
        self._closed = False
        self._created_at = datetime.now(timezone.utc).isoformat()

    def subscribe(self) -> asyncio.Queue:
        """Create a new subscriber queue."""
        q = asyncio.Queue(maxsize=self._max_buffer)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """Remove a subscriber queue."""
        if q in self._queues:
            self._queues.remove(q)

    async def emit(self, event_type: StreamEventType, data: dict):
        """Emit an event to all subscribers."""
        if self._closed:
            return
        event = StreamEvent(type=event_type, data=data)
        self._history.append(event)
        if len(self._history) > self._max_buffer:
            self._history = self._history[-self._max_buffer:]

        for q in self._queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event for this subscriber
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    async def close(self):
        """Close the channel and signal all subscribers."""
        self._closed = True
        done_event = StreamEvent(type=StreamEventType.DONE, data={"channel": self.id})
        for q in self._queues:
            try:
                q.put_nowait(done_event)
            except asyncio.QueueFull:
                pass

    @property
    def is_closed(self):
        return self._closed


class StreamManager:
    """
    Central manager for streaming channels.
    Creates channels per agent run and routes tool output to the right channel.
    """

    def __init__(self):
        self._channels: dict[str, StreamChannel] = {}

    def create_channel(self, channel_id: str = None) -> StreamChannel:
        """Create a new streaming channel."""
        channel = StreamChannel(channel_id=channel_id)
        self._channels[channel.id] = channel
        return channel

    def get_channel(self, channel_id: str) -> StreamChannel | None:
        return self._channels.get(channel_id)

    async def close_channel(self, channel_id: str):
        channel = self._channels.get(channel_id)
        if channel:
            await channel.close()
            del self._channels[channel_id]

    def list_channels(self) -> list[dict]:
        return [
            {"id": ch.id, "closed": ch.is_closed, "subscribers": len(ch._queues),
             "events": len(ch._history)}
            for ch in self._channels.values()
        ]


class ToolStreamWrapper:
    """
    Wraps tool execution to emit streaming events.
    Use as a context manager around tool calls.
    """

    def __init__(self, channel: StreamChannel, tool_name: str, args: dict):
        self.channel = channel
        self.tool_name = tool_name
        self.args = args
        self._start_time = 0

    async def __aenter__(self):
        self._start_time = time.time()
        await self.channel.emit(StreamEventType.TOOL_START, {
            "tool": self.tool_name,
            "args": {k: str(v)[:200] for k, v in self.args.items()},
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._start_time) * 1000)
        if exc_type:
            await self.channel.emit(StreamEventType.TOOL_ERROR, {
                "tool": self.tool_name,
                "error": str(exc_val),
                "duration_ms": duration_ms,
            })
        else:
            await self.channel.emit(StreamEventType.TOOL_END, {
                "tool": self.tool_name,
                "duration_ms": duration_ms,
            })
        return False  # Don't suppress exceptions

    async def progress(self, message: str, percent: float = None):
        """Emit a progress event during tool execution."""
        data = {"tool": self.tool_name, "message": message}
        if percent is not None:
            data["percent"] = min(max(percent, 0), 100)
        await self.channel.emit(StreamEventType.TOOL_PROGRESS, data)

    async def output(self, content: str):
        """Emit incremental output during tool execution."""
        await self.channel.emit(StreamEventType.TOOL_OUTPUT, {
            "tool": self.tool_name,
            "content": content,
        })


async def sse_generator(channel: StreamChannel) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE events from a channel.
    Use this with FastAPI StreamingResponse.
    """
    queue = channel.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield event.to_sse()
                if event.type == StreamEventType.DONE:
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"
    finally:
        channel.unsubscribe(queue)


# ── Global instance ───────────────────────────────────────────────────────────
stream_manager = StreamManager()
