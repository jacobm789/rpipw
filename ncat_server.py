import network
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

history = []
history_index = -1
cmd_buffer = ""
cursor_pos = 0

commands = ["led on", "led off", "led2 on", "led2 off", "status", "reboot"]
tab_index = 0

def handle_input(conn):
    global history, history_index, cmd_buffer, cursor_pos, tab_index

    conn.sendall(b"Welcome to Pico W Shell!\n>>> ")

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
            conn.sendall(b"\n")
            if cmd_buffer.strip():
                history.append(cmd_buffer)
                history_index = len(history)
                process_command(conn, cmd_buffer.strip())
            cmd_buffer = ""
            cursor_pos = 0
            tab_index = 0
            conn.sendall(b">>> ")

        elif char == "\t":
            matches = [cmd for cmd in commands if cmd.startswith(cmd_buffer.upper())]
            if matches:
                cmd_buffer = matches[tab_index]
                cursor_pos = len(cmd_buffer)
                tab_index = (tab_index + 1) % len(matches)
                conn.sendall(b"\n" + b"\n".join(cmd.encode() for cmd in matches) + b"\n>>> " + cmd_buffer.encode() + b" ")

        elif char == "\x7f":
            if cursor_pos > 0:
                cmd_buffer = cmd_buffer[:cursor_pos - 1] + cmd_buffer[cursor_pos:]
                cursor_pos -= 1
                tab_index = 0
                conn.sendall(b"\b \b")

        else:
            cmd_buffer = cmd_buffer[:cursor_pos] + char + cmd_buffer[cursor_pos:]
            cursor_pos += 1
            tab_index = 0
            conn.sendall(char.encode())

    conn.close()

def process_command(conn, cmd):
    """Executes the given command."""
    if cmd == "led on":
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
