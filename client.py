import asyncio
import sys
from collections import deque
from queue import Queue, Empty
import threading
import signal

MESSAGE_WIDTH = 19

# Target IP and port
BACKEND_HOST = 'localhost'
BACKEND_PORT = 8888
MESSAGE = "#16" + "010101XXXXXXXXXX"

tx_queue = Queue()
rx_queue = deque()


async def backend_writer_task(backend_writer: asyncio.StreamWriter):
    while True:
        if not tx_queue.not_empty:
            await asyncio.sleep(0.1)
            continue

        try:
            data = tx_queue.get(block=True, timeout=0.1).encode('utf-8')
            backend_writer.write(data)
            await backend_writer.drain()

        except Empty:
            await asyncio.sleep(0.1)

        except ConnectionResetError:
            sys.exit("Backend disconnected, stopping.")


async def backend_reader_task(backend_reader):

    try:
        while True:
            data = await backend_reader.read(MESSAGE_WIDTH)
            if not data: break 
            
            rx_queue.append(data)

    finally:
        sys.exit("Backend disconnected, stopping.")


def user_input_reader(input_queue):
    while True:
        input_queue.put(input())


async def output_writer():
    while True:
        if not rx_queue:
            await asyncio.sleep(0.1)
            continue

        print(f"\u001B[s\u001B[A\u001B[999D\u001B[S\u001B[L> {rx_queue.popleft().decode('utf-8')}\u001B[u", end="", flush=True)


async def start_servers():
    # Connect to backend once
    backend_reader, backend_writer = await asyncio.open_connection(BACKEND_HOST, BACKEND_PORT)
    print(f"Connected to backend {BACKEND_HOST}:{BACKEND_PORT}")

    asyncio.create_task(backend_writer_task(backend_writer))
    asyncio.create_task(backend_reader_task(backend_reader))
    asyncio.create_task(output_writer())

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    input_thread = threading.Thread(target=user_input_reader, args=(tx_queue,))
    input_thread.daemon = True
    input_thread.start()

    try:
        asyncio.run(start_servers())
    except KeyboardInterrupt:
        print("Client stopped.")

