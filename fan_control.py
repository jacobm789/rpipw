import network
import time
import ntptime
import socket
import uselect
import machine
import credentials
from ds18x20 import DS18X20
from onewire import OneWire
import uasyncio as asyncio
# TODO: Make temp reading (and everything else working around that) asynchronous

hostname = credentials.HOSTNAME
ssid = credentials.SSID
password = credentials.PASSWORD

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

fans = machine.Pin(16, machine.Pin.OUT)

schedule = 1
schedule_running = 0
thermostat_mode = 1
days_of_the_week = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
months = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
#TODO: add date to status printout

class DS18B20:
    def __init__(self, power_pin, data_pin):
        self.power = machine.Pin(power_pin, machine.Pin.OUT)
        self.power.value(1)

        time.sleep_ms(100)

        self.dat = machine.Pin(data_pin)
        self.ds = DS18X20(OneWire(self.dat))

        self.roms = self.ds.scan()
        if not self.roms:
            # raise RuntimeError("No DS18B20 devices found")
            pass
        # TODO: Handle No thermistor to avoid hangups
        #WARNING: don't use, currently breaks when no thermistor connected

    def read_temps(self):
        self.ds.convert_temp()

        time.sleep_ms(750)

        temp_c = self.ds.read_temp(self.roms[0])
        temp_f = (temp_c * 9/5) + 32

        return temp_f

def get_time():
    ntptime.settime()
    rtc = machine.RTC()
    utc_time = rtc.datetime()
    timezone_offset_hours = -7
    timezone_offset_seconds = timezone_offset_hours * 3600
    year, month, day, weekday, hour, minute, second, _ = utc_time
    seconds = time.mktime((year, month, day, hour, minute, second, weekday, 0))
    local_seconds = seconds + timezone_offset_seconds
    local_time = time.localtime(local_seconds)
    rtc.datetime((local_time[0], local_time[1], local_time[2], local_time[6], local_time[3], local_time[4], local_time[5], 0))

def get_temp(thermistor):
    pass

def toggle_schedule(session):
    global schedule, thermostat_mode
    schedule = (schedule+1) % 2
    session.sendall(f"Schedule is now {"enabled" if schedule else "disabled"}\n")

def toggle_thermostat_mode(session):
    """Runs fans only when too hot upstairs and too cold downstairs"""
    global schedule, thermostat_mode
    thermostat_mode = (thermostat_mode+1) % 2
    session.sendall(f"Thermostat mode is now {"enabled" if thermostat_mode else "disabled"}\n")

def run_schedule():
    global schedule_running
    if time.localtime()[6] in range(5) and time.localtime()[3:5] == (6, 15):
        fans.value(1)
        schedule_running = 1
    elif time.localtime()[6] in range(5) and time.localtime()[3:5] == (16, 00):
        fans.value(0)
        schedule_running = 0

def run_thermostat_mode():
    global schedule_running
    if schedule_running:
        return 0
    else:
        pass

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
    # upstairs_temp = DS18B20(power_pin=14, data_pin=15)
    session.sendall(f"Fans are currently {fans_status}\n".encode())
    session.sendall(f"Schedule is currently {"enabled" if schedule else "disabled"}\n")
    session.sendall(f"Thermostat mode is currently {"enabled" if thermostat_mode else "disabled"}\n")
    if (schedule, thermostat_mode) == (1, 1):
        session.sendall(b"Thermostat mode inactive during scheduled fan time.\n")
    session.sendall(f"The time is {time.localtime()[3]}:{time.localtime()[4]:02}:{time.localtime()[5]:02}\n")
    # session.sendall(f"The upstairs temperature is {upstairs_temp.read_temps()}\n")

def process_command(session, cmd):
    """Executes the given command."""
    if cmd == "fans on":
        fans.value(1)
        session.sendall(b"Fans are now ON\n")
    elif cmd == "fans off":
        fans.value(0)
        session.sendall(b"Fans are now OFF\n")
    elif cmd == "toggle schedule":
        toggle_schedule(session)
    elif cmd == "toggle thermostat mode":
        toggle_thermostat_mode(session)
        session.sendall(b"Warning: future feature.\n")
    elif cmd == "status":
        status(session)
    elif cmd == "reboot":
        session.sendall(b"Rebooting...\n")
        machine.reset()
    elif cmd == "?":
        session.sendall(b'Available commands are "fans on", "fans off", "toggle schedule", "toggle thermostat mode", "status", "reboot", and "?"\n')
        session.sendall(b'Use ctrl+c to exit.\n')
    else:
        session.sendall(b"Unknown command\n")

def handle_input(session):
    cmd_buffer = ""

    session.sendall(b"Welcome to Pico W Server!\n")
    status(session)
    process_command(session, "?")
    session.sendall(b">>> ")

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
            run_schedule() if schedule else None
            run_thermostat_mode() if thermostat_mode else None
            s.settimeout(10)
            session, addr = s.accept()
            handle_input(session)
        except OSError:
            pass

connect_wifi()

shell_server()
