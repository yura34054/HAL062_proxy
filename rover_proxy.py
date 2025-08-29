import asyncio
import serial_asyncio
import sys

MESSAGE_WIDTH = 19
SERIAL_PORT = '/dev/serial0'
SERIAL_BAUDRATE = 115200
LISTEN_PORTS = [8888, 8889, 8890, 8891]


# Store connected clients
client_writers = {}
uart_write_queue = asyncio.Queue()
uart_read_queue = asyncio.Queue()


async def uart_writer_task(uart_writer):
   while True:
        data = await uart_write_queue.get()
        uart_writer.write(data)
        await uart_writer.drain()


async def uart_reader_task(uart_reader):
    while True:
        data = await uart_reader.readexactly(MESSAGE_WIDTH)
        # Przekazanie danych do wszystkich klientów TCP
        writers = list(client_writers.values())
        for writer in writers:
            writer.write(data)
        await asyncio.gather(*[writer.drain() for writer in writers])


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client_address = writer.get_extra_info("peername")
    port = writer.get_extra_info("sockname")

    print(f"Client {client_address} connected on port {port}")

    client_writers[client_address] = writer

    try:
        while True:
            data = await reader.read(MESSAGE_WIDTH)
            if not data: break

            await uart_write_queue.put(data)

    finally:
        writer.close()
        await writer.wait_closed()

        print(f"Client {client_address} disconnected")
        del client_writers[client_address]


async def start_servers():
    # Start UART connection
    loop = asyncio.get_running_loop()
    reader, writer = await serial_asyncio.open_serial_connection(url=SERIAL_PORT, baudrate=SERIAL_BAUDRATE)

    asyncio.create_task(uart_writer_task(writer))
    asyncio.create_task(uart_reader_task(reader))

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

