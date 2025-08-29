import asyncio
import sys
from collections import deque
from queue import Queue, Empty
import threading
import signal
import readline


MESSAGE_WIDTH = 19

# Target IP and port
BACKEND_HOST = '192.168.1.98'
BACKEND_PORT = 8890

tx_queue = Queue()
rx_queue = deque()


async def backend_writer_task(backend_writer: asyncio.StreamWriter):
    while True:
        if not tx_queue.not_empty:
            await asyncio.sleep(0.1)
            continue

        try:
            data = tx_queue.get(block=True, timeout=0.1)
            print_above(f"sending: {data}")
            backend_writer.write(data.encode('utf-8'))
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


commands = {
        "sensor.tare.1":    "#780001XXXXXXXXXXXX",
        "sensor.tare.2":    "#780002XXXXXXXXXXXX",
        "sensor.tare.3":    "#780003XXXXXXXXXXXX",

        "sensor.lamp.1":    "#7801XXXXXXXXXXXXXX",
        "sensor.lamp.2":    "#7802XXXXXXXXXXXXXX",

        "lab.move.up":      "#CB010000640000XXXX",
        "lab.move.down":    "#CB020000640000XXXX", 
        "lab.drill.up":     "#CB000202005050XXXX",
        "lab.drill.down":   "#CB000102005050XXXX",
        "lab.stop":         "#CB000000000000XXXX",
}


def completer(text, state):
    options = [command for command in list(commands.keys()) if command.startswith(text)]
    return options[state] if state < len(options) else None


def user_input_reader(input_queue):
    readline.parse_and_bind("tab: complete")
    readline.set_auto_history(True)
    readline.set_completer(completer)

    while True:
        inp = input()
        if inp not in commands:
            print_above("> invalid command")
            continue

        input_queue.put(commands[inp])


def print_above(text):
    print(f"\u001B[s\u001B[A\u001B[999D\u001B[S\u001B[L{text}\u001B[u", end="", flush=True)


async def output_writer():
    while True:
        if not rx_queue:
            await asyncio.sleep(0.1)
            continue

        data = rx_queue.popleft()
        
        data = data.decode('utf-8')
        if data[0] != '#' or len(data) != 19:
            print_above("invalid message")
            continue

        id, data = int(data[1:3], 16), data[3:]

        if id in (121, 122, 123):
            data = int(data[2:10], 16)
            data = data if data < 0xdfffffff else data-0xffffffff 

        print_above(f"> {id} | {data}")


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

