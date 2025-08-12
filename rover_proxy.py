import asyncio
import sys
from collections import deque


MESSAGE_WIDTH = 19
BACKEND_HOST = 'localhost'
BACKEND_PORT = 5000
LISTEN_PORTS = [8888, 8889]

# Store connected clients
client_writers = {}
backend_queue = asyncio.Queue()
feedback_queue = asyncio.Queue()


async def backend_writer_task(backend_writer: asyncio.StreamWriter):
    while True:
        try:
            data = await backend_queue.get()
            backend_writer.write(data)
            await backend_writer.drain()

        except ConnectionResetError:
            sys.exit("Backend disconnected, stopping.")


async def backend_reader_task(backend_reader):
    while True:
        try:
            data = await backend_reader.read(MESSAGE_WIDTH)
            if not data: break

            await feedback_queue.put(data)

        finally:
            sys.exit("Backend disconnected, stopping.")


async def client_feedback():
    while True:
        try:
            writers = list(client_writers.values())
            data = await feedback_queue.get()

            for writer in writers:
                writer.write(data)

            await asyncio.gather(*[writer.drain() for writer in writers])

        except ConnectionResetError:
            pass


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client_address = writer.get_extra_info("peername")
    port = writer.get_extra_info("sockname")

    print(f"Client {client_address} connected on port {port}")

    client_writers[client_address] = writer

    try:
        while True:
            data = await reader.read(MESSAGE_WIDTH)
            if not data: break 

            await backend_queue.put(data)

    finally:
        writer.close()
        await writer.wait_closed()

        print(f"Client {client_address} disconnected")
        del client_writers[client_address]


async def start_servers():
    # Connect to backend once
    backend_reader, backend_writer = await asyncio.open_connection(BACKEND_HOST, BACKEND_PORT)
    print(f"Connected to backend {BACKEND_HOST}:{BACKEND_PORT}")

    # Start backend handler tasks
    asyncio.create_task(backend_writer_task(backend_writer))
    asyncio.create_task(backend_reader_task(backend_reader))
    asyncio.create_task(client_feedback())

    # Listen on multiple ports
    for port in LISTEN_PORTS:
        server = await asyncio.start_server(handle_client, '0.0.0.0', port)
        print(f"Listening on 0.0.0.0:{port}")
        asyncio.create_task(server.serve_forever())

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        print("\nProxy stopped.")

