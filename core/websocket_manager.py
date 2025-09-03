from typing import List, Dict
import asyncio
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[any]] = {}

    async def connect(self, websocket: any, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: any, user_id: str):
        self.active_connections[user_id].remove(websocket)
        if not self.active_connections[user_id]:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: str, websocket: any):
        try:
            await websocket.send_text(message)
        except (ConnectionClosedOK, ConnectionClosedError) as e:
            print(f"WebSocket connection closed for personal message: {e}")

    async def broadcast(self, message: str):
        for user_id in list(self.active_connections.keys()):
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_text(message)
                except (ConnectionClosedOK, ConnectionClosedError) as e:
                    print(f"WebSocket connection closed during broadcast: {e}")
                    self.active_connections[user_id].remove(connection)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]


manager = ConnectionManager()
