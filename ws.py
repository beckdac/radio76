import asyncio
from aiohttp import web
import socketio

# Create an Async Socket.IO server
sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

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


async def led_task():
    print("Doing work...")
    data = { 'type': 'led', 'value': False }
    try:
        while True:
            await asyncio.sleep(2)  # Run every 2 seconds
            print(f'sending update: {data}')
            await sio.emit('gateway_heartbeat', data)
            data['value'] = not data['value']
    except asyncio.CancelledError:
        print("Background task cancelled")

async def start_background_tasks(app):
    app['led'] = asyncio.create_task(led_task())

async def cleanup_background_tasks(app):
    app['led'].cancel()
    await app['led']

# Register the startup and cleanup signals
app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)


if __name__ == '__main__':
    web.run_app(app, port=5000)
