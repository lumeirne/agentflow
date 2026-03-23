"""WebSocket connection manager — broadcasts real-time events to connected clients."""

import json
from fastapi import WebSocket


class WebSocketManager:
    """Manages WebSocket connections per run_id and broadcasts events."""

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        """Accept and register a WebSocket connection for a run."""
        await websocket.accept()
        if run_id not in self._connections:
            self._connections[run_id] = set()
        self._connections[run_id].add(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if run_id in self._connections:
            self._connections[run_id].discard(websocket)
            if not self._connections[run_id]:
                del self._connections[run_id]

    async def broadcast(self, run_id: str, event: dict):
        """Send an event to all connected clients for a run."""
        if run_id not in self._connections:
            return

        dead_connections = set()
        message = json.dumps(event)

        for ws in self._connections[run_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.add(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self._connections[run_id].discard(ws)


# Singleton
ws_manager = WebSocketManager()
