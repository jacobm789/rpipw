import network
import struct
import time
import socket
import uselect
import machine
import credentials

hostname = credentials.HOSTNAME
ssid = credentials.SSID
password = credentials.PASSWORD

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

def connect_wifi():
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(ssid, password)
        wlan.config(hostname=hostname)

        timeout = 10
        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                print("WiFi connection failed. Retrying...")
                return False
            time.sleep(1)

        print("Connected! IP:", wlan.ifconfig()[0])
        return True
    return True

connect_wifi()

led = machine.Pin("LED", machine.Pin.OUT)
led2 = machine.Pin(16, machine.Pin.OUT)


commands = ["led on", "led off", "led2 on", "led2 off", "status", "exit", "reboot"]

def handle_input(conn):
    cmd_buffer = ""

    conn.sendall(b"Welcome to Pico W Server!\n")
    status = "ON" if led.value() else "OFF"
    status2 = "ON" if led2.value() else "OFF"
    conn.sendall(f"LED is currently {status}\n".encode())
    conn.sendall(f"LED2 is currently {status2}\n".encode())
    conn.sendall(f'Available commands are "{'", "'.join(str(i) for i in commands)}", and "?"\n')
    conn.sendall(f'Use ctrl+c to exit.\n>>> ')

    start_time = time.time()

    poller = uselect.poll()
    poller.register(conn, uselect.POLLIN)

    while True:
        if time.time() - start_time > 60*3:
            conn.sendall(b"\nConnection timed out. Closing.\n")
            break

        events = poller.poll(1000)
        if not events:
            continue

        data = conn.recv(1)

        if not data:
            break

        char = data.decode()

        if char == "\n":
            if cmd_buffer.strip():
                process_command(conn, cmd_buffer.strip())
            cmd_buffer = ""
            conn.sendall(b">>> ")

        else:
            cmd_buffer += char

    conn.close()

def process_command(conn, cmd):
    """Executes the given command."""
    if cmd == "?":
        conn.sendall(f'Available commands are "{'", "'.join(str(i) for i in commands)}", and "?"\n')
        conn.sendall(f'Use ctrl+c to exit.\n')
    elif cmd == "led on":
        led.value(1)
        conn.sendall(b"LED is now ON\n")
    elif cmd == "led off":
        led.value(0)
        conn.sendall(b"LED is now OFF\n")
    elif cmd == "led2 on":
        led2.value(1)
        conn.sendall(b"LED2 is now ON\n")
    elif cmd == "led2 off":
        led2.value(0)
        conn.sendall(b"LED2 is now OFF\n")
    elif cmd == "status":
        status = "ON" if led.value() else "OFF"
        status2 = "ON" if led2.value() else "OFF"
        conn.sendall(f"LED is currently {status}\n".encode())
        conn.sendall(f"LED2 is currently {status2}\n".encode())
    elif cmd == "reboot":
        conn.sendall(b"Rebooting...\n")
        machine.reset()
    else:
        conn.sendall(b"Unknown command\n")

def shell_server():
    """Starts the Pico W shell server."""
    addr = ("0.0.0.0", 23)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(addr)
    s.listen(1)
    print(f"Listening on {addr}")

    while True:
        if not wlan.isconnected():
            print("WiFi lost. Reconnecting...")
            connect_wifi()

        try:
            s.settimeout(10)
            conn, addr = s.accept()
            print(f"Connected by {addr}")
            handle_input(conn)
        except OSError:
            pass

shell_server()
