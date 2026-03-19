import asyncio
from datetime import datetime

from aiohttp import web
import socketio

# Create an Async Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

# --- Routes ---
async def index(request):
    """Serves the index.html file."""
    return web.FileResponse('index.html')

app.router.add_get('/', index)

@sio.event
async def connect(sid, environ):
    print(f'Client connected: {sid}')

@sio.event
async def update_control(sid, data):
    """
    Receives updates and broadcasts them asynchronously.
    """
    print(f"Update from {sid}: {data}")
    # Broadcast to all OTHER clients
    await sio.emit('control_update', data, skip_sid=sid)

@sio.event
async def disconnect(sid):
    print(f'Client disconnected: {sid}')


async def heartbeat_task():
    data = { }
    try:
        while True:
            await asyncio.sleep(2)  # Run every 2 seconds
            now = datetime.now()
            data['time'] = now.strftime("%Y-%m-%d %H:%M:%S")
            await sio.emit('gateway_heartbeat', data)
    except asyncio.CancelledError:
        print("Heartbeat task cancelled")

async def start_background_tasks(app):
    app['heartbeat'] = asyncio.create_task(heartbeat_task())

async def cleanup_background_tasks(app):
    app['heartbeat'].cancel()
    await app['heartbeat']

# Register the startup and cleanup signals
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)


if __name__ == '__main__':
    web.run_app(app, port=5000)
