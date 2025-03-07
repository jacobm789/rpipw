import network
import time
import ntptime
import socket
import uselect
import machine
import credentials

hostname = credentials.HOSTNAME
ssid = credentials.SSID
password = credentials.PASSWORD

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

fans = machine.Pin(16, machine.Pin.OUT)

def get_time():
    ntptime.settime()
    rtc = machine.RTC()
    utc_time = rtc.datetime()
    timezone_offset_hours = -8
    timezone_offset_seconds = timezone_offset_hours * 3600
    year, month, day, weekday, hour, minute, second, _ = utc_time
    seconds = time.mktime((year, month, day, hour, minute, second, weekday, 0))
    local_seconds = seconds + timezone_offset_seconds
    local_time = time.localtime(local_seconds)
    rtc.datetime((local_time[0], local_time[1], local_time[2], local_time[6], local_time[3], local_time[4], local_time[5], 0))

def connect_wifi():
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        wlan.config(hostname=hostname)

        timeout = 10
        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                return False
            time.sleep(1)

        print("Connected! IP:", wlan.ifconfig()[0])
        get_time()
        return True
    return True

def status(session):
    fans_status = "ON" if fans.value() else "OFF"
    session.sendall(f"Fans are currently {fans_status}\n".encode())
    session.sendall(f"The time is {time.localtime()[3]}:{time.localtime()[4]}:{time.localtime()[5]}\n")

def process_command(session, cmd):
    """Executes the given command."""
    if cmd == "?":
        session.sendall(f'Available commands are "fans on", "fans off", "status", "reboot", and "?"\n')
        session.sendall(f'Use ctrl+c to exit.\n')
    elif cmd == "fans on":
        fans.value(1)
        session.sendall(b"Fans are now ON\n")
    elif cmd == "fans off":
        fans.value(0)
        session.sendall(b"Fans are now OFF\n")
    elif cmd == "status":
        status(session)
    elif cmd == "reboot":
        session.sendall(b"Rebooting...\n")
        machine.reset()
    else:
        session.sendall(b"Unknown command\n")

def handle_input(session):
    cmd_buffer = ""

    session.sendall(b"Welcome to Pico W Server!\n")
    session.sendall(f'Available commands are "fans on", "fans off", "status", "reboot", and "?"\n')
    status(session)
    session.sendall(f'Use ctrl+c to exit.\n>>> ')

    start_time = time.time()

    poller = uselect.poll()
    poller.register(session, uselect.POLLIN)

    while True:
        if time.time() - start_time > 60*3:
            session.sendall(b"\nConnection timed out. Closing.\n")
            break

        events = poller.poll(1000)
        if not events:
            continue

        data = session.recv(1)

        if not data:
            break

        char = data.decode()

        if char == "\n":
            if cmd_buffer.strip():
                process_command(session, cmd_buffer.strip())
            cmd_buffer = ""
            session.sendall(b">>> ")

        else:
            cmd_buffer += char

    session.close()

def shell_server():
    addr = ("0.0.0.0", 23)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(addr)
    s.listen(1)

    start = time.time()

    while True:
        if time.time() - start > 7*24*60*60:
            get_time()
            start = time.time()
        if not wlan.isconnected():
            connect_wifi()

        try:
            if time.localtime()[3:5] == (6, 15):
                fans.value(1)
            elif time.localtime()[3:5] == (16, 00):
                fans.value(0)
            s.settimeout(10)
            session, addr = s.accept()
            handle_input(session)
        except OSError:
            pass

connect_wifi()

shell_server()
