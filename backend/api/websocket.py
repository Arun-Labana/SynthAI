"""
WebSocket handler for real-time task updates.

Provides live streaming of workflow progress to the frontend.
"""

import asyncio
import json
from typing import Dict, Set
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from backend.graph.state import WorkflowStatus


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    
    Supports:
    - Multiple clients per task
    - Broadcasting updates to all subscribers
    - Graceful disconnect handling
    """
    
    def __init__(self):
        # Map of task_id -> set of connected websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Map of websocket -> task_id for reverse lookup
        self.connection_tasks: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept a new WebSocket connection for a task."""
        await websocket.accept()
        
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        
        self.active_connections[task_id].add(websocket)
        self.connection_tasks[websocket] = task_id
        
        # Send initial connection confirmation
        await self._send_message(websocket, {
            "type": "connected",
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        task_id = self.connection_tasks.get(websocket)
        
        if task_id and task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            
            # Clean up empty task entries
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        
        if websocket in self.connection_tasks:
            del self.connection_tasks[websocket]
    
    async def broadcast_to_task(self, task_id: str, message: dict):
        """Broadcast a message to all clients subscribed to a task."""
        if task_id not in self.active_connections:
            return
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        
        # Send to all connected clients
        disconnected = set()
        for websocket in self.active_connections[task_id]:
            try:
                await self._send_message(websocket, message)
            except Exception:
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def send_status_update(self, task_id: str, state: dict):
        """Send a formatted status update to all task subscribers."""
        await self.broadcast_to_task(task_id, {
            "type": "status_update",
            "task_id": task_id,
            "status": state.get("status"),
            "iteration_count": state.get("iteration_count", 0),
            "is_tests_passing": state.get("is_tests_passing", False),
            "message_count": len(state.get("messages", [])),
        })
    
    async def send_agent_message(self, task_id: str, agent: str, content: str):
        """Send an agent message to all task subscribers."""
        await self.broadcast_to_task(task_id, {
            "type": "agent_message",
            "task_id": task_id,
            "agent": agent,
            "content": content,
        })
    
    async def send_code_update(self, task_id: str, files: list):
        """Send a code files update."""
        await self.broadcast_to_task(task_id, {
            "type": "code_update",
            "task_id": task_id,
            "files": files,
        })
    
    async def send_error(self, task_id: str, error: str):
        """Send an error message."""
        await self.broadcast_to_task(task_id, {
            "type": "error",
            "task_id": task_id,
            "error": error,
        })
    
    async def send_completion(self, task_id: str, result: dict):
        """Send workflow completion notification."""
        await self.broadcast_to_task(task_id, {
            "type": "completed",
            "task_id": task_id,
            "status": result.get("status"),
            "pr_url": result.get("pr_url"),
        })
    
    async def _send_message(self, websocket: WebSocket, message: dict):
        """Send a JSON message through WebSocket."""
        await websocket.send_json(message)
    
    def get_connection_count(self, task_id: str) -> int:
        """Get the number of active connections for a task."""
        return len(self.active_connections.get(task_id, set()))
    
    def get_all_tasks(self) -> list:
        """Get list of all tasks with active connections."""
        return list(self.active_connections.keys())


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint handler.
    
    Usage:
        ws://localhost:8000/ws/{task_id}
    
    Message types received:
        - ping: Keep-alive
        - subscribe: Subscribe to additional updates
    
    Message types sent:
        - connected: Initial connection confirmation
        - status_update: Task status changed
        - agent_message: Message from an agent
        - code_update: Code files updated
        - error: Error occurred
        - completed: Workflow completed
        - pong: Response to ping
    """
    await manager.connect(websocket, task_id)
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type", "")
                
                if message_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                
                elif message_type == "get_status":
                    # Client requesting current status
                    from backend.api.routes import _task_states
                    
                    if task_id in _task_states:
                        state = _task_states[task_id]
                        await manager.send_status_update(task_id, state)
                    else:
                        await manager.send_error(task_id, "Task not found")
                
            except json.JSONDecodeError:
                await manager.send_error(task_id, "Invalid JSON message")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)


class WorkflowProgressReporter:
    """
    Helper class for reporting workflow progress via WebSocket.
    
    Use this in workflow nodes to send real-time updates.
    """
    
    def __init__(self, task_id: str):
        self.task_id = task_id
    
    async def report_status(self, state: dict):
        """Report a status update."""
        await manager.send_status_update(self.task_id, state)
    
    async def report_agent_message(self, agent: str, content: str):
        """Report a message from an agent."""
        await manager.send_agent_message(self.task_id, agent, content)
    
    async def report_code_generated(self, files: list):
        """Report that code files were generated."""
        await manager.send_code_update(self.task_id, files)
    
    async def report_error(self, error: str):
        """Report an error."""
        await manager.send_error(self.task_id, error)
    
    async def report_completion(self, result: dict):
        """Report workflow completion."""
        await manager.send_completion(self.task_id, result)

