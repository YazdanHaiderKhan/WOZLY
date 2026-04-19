"""WebSocket manager — live dashboard updates.

Maintains a connection pool per user_id.
Server pushes: roadmap_updated | mastery_updated | quiz_ready
"""
import json
from typing import DefaultDict
from collections import defaultdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

# user_id → set of active WebSocket connections
_connections: DefaultDict[str, set[WebSocket]] = defaultdict(set)


async def broadcast_event(user_id: str, event_type: str, payload: dict) -> None:
    """Push a typed event to all active connections for a user."""
    message = json.dumps({"type": event_type, "payload": payload})
    dead: set[WebSocket] = set()
    # Iterate over a snapshot to avoid concurrent modification errors
    for ws in list(_connections.get(user_id, set())):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    # Clean up dead connections
    for ws in dead:
        _connections[user_id].discard(ws)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint — client connects on dashboard load."""
    # AUTH BYPASS: accept all websocket connections without checking tokens
    # (The frontend will connect using the demo guest ID)

    await websocket.accept()
    _connections[user_id].add(websocket)

    try:
        # Keep connection alive — handle ping/pong and client messages
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data) if data else {}
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        _connections[user_id].discard(websocket)
