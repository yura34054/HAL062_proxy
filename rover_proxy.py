import asyncio
import serial_asyncio
import sys

MESSAGE_WIDTH = 19
SERIAL_PORT = '/dev/serial0'
SERIAL_BAUDRATE = 115200
LISTEN_PORTS = [8888, 8889]


# Store connected clients
client_writers = {}
uart_write_queue = asyncio.Queue()
uart_read_queue = asyncio.Queue()

# ===== UART HANDLERS =====
class UARTProtocol(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport
        print(f"UART connected: {SERIAL_PORT} @ {SERIAL_BAUDRATE}")

    def data_received(self, data):
        asyncio.create_task(uart_read_queue.put(data))

    def connection_lost(self, exc):
        print("UART connection lost")
        sys.exit(1)


async def uart_writer_task(uart_transport):
    while True:
        data = await uart_write_queue.get()
        print(f"sending {data}")
        uart_transport.write(data)

async def uart_reader_task():
    while True:
        data = await uart_read_queue.get()
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

            if (data[0] != b'#') or (data.len() != MESSAGE_WIDTH):
                print("wrong message format recived")
                continue

            await uart_write_queue.put(data)

    finally:
        writer.close()
        await writer.wait_closed()

        print(f"Client {client_address} disconnected")
        del client_writers[client_address]


async def start_servers():
    # Start UART connection
    loop = asyncio.get_running_loop()
    transport, protocol = await serial_asyncio.create_serial_connection(
        loop, UARTProtocol, SERIAL_PORT, SERIAL_BAUDRATE
    )

    asyncio.create_task(uart_writer_task(transport))
    asyncio.create_task(uart_reader_task())

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

        
