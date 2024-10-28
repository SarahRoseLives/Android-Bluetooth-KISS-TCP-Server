import socket
import threading
import os
import signal
from threading import Event
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from jnius import autoclass
import time

# Bluetooth connection settings
DEVICE_NAMES = ["UV-PRO", "VR-N76", "GA-5WB"]
DATA_CHANNEL_ID = 3  # RFCOMM channel for Bluetooth (adjust as needed)

# Create a global shutdown event
shutdown_event = Event()

# Java classes for Bluetooth
BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
UUID = autoclass('java.util.UUID')

class Example(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Light"
        self.log_messages = ""  # Initialize log messages as an empty string
        return Builder.load_file('main.kv')

    def switch_screen(self, screen_name):
        self.root.ids.screen_manager.current = screen_name
        self.root.ids.nav_drawer.set_state("close")

    def start_bluetooth_server(self):
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)

        threading.Thread(target=self.main_process, daemon=True).start()

    def main_process(self):
        mac_address = self.find_bluetooth_device()

        if not mac_address:
            self.log("Failed to find any Bluetooth device. Exiting...")
            return

        self.bt_socket = self.connect_bluetooth(mac_address, DATA_CHANNEL_ID)
        if not self.bt_socket:
            self.log("Failed to connect to Bluetooth device. Exiting...")
            return

        # Start listening for incoming Bluetooth data
        threading.Thread(target=self.listen_bluetooth, daemon=True).start()

    def send_test_message(self):
        """Send a test message formatted as APRS and encapsulated in a KISS frame when the button is pressed."""
        try:
            # Constructing an APRS message
            aprs_message = b'AD8NT>APRS*:Hello from AD8NT'

            # KISS frame: Frame Start, Command, Data, Frame End
            kiss_frame = b'\xC0\x00' + aprs_message + b'\xC0'  # KISS frame: 0xC0 start/end, 0x00 is a command byte

            self.log(f"Sending APRS message encapsulated in KISS frame: {kiss_frame}")
            output_stream = self.bt_socket.getOutputStream()
            output_stream.write(kiss_frame)
        except Exception as e:
            self.log(f"Error sending test message: {e}")

    def listen_bluetooth(self):
        """Listen for incoming Bluetooth packets and print them to the console."""
        try:
            while not shutdown_event.is_set():
                try:
                    input_stream = self.bt_socket.getInputStream()
                    buffer = bytearray(1024)  # Create a buffer for reading
                    bytes_read = input_stream.read(buffer)
                    if bytes_read > 0:
                        data = bytes(buffer[:bytes_read])
                        self.log(f"Received from Bluetooth: {data}")
                except Exception as e:
                    self.log(f"Error receiving from Bluetooth: {e}")
                    break
        finally:
            if self.bt_socket:
                self.bt_socket.close()

    def find_bluetooth_device(self):
        """Scan for Bluetooth devices using Android's native Bluetooth API."""
        adapter = BluetoothAdapter.getDefaultAdapter()
        if not adapter.isEnabled():
            self.log("Enabling Bluetooth adapter...")
            adapter.enable()

        self.log("Scanning for Bluetooth devices...")
        paired_devices = adapter.getBondedDevices().toArray()

        for device in paired_devices:
            device_name = device.getName()
            device_mac = device.getAddress()
            self.log(f"Found Bluetooth device: {device_name} - {device_mac}")

            for name in DEVICE_NAMES:
                if name.lower() in device_name.lower():
                    self.log(f"Matched device '{device_name}' with {name}.")
                    return device_mac

        self.log("No matching Bluetooth devices found.")
        return None

    def connect_bluetooth(self, mac_address, channel):
        """Connect to Bluetooth device using RFCOMM protocol (via Pyjnius)."""
        try:
            adapter = BluetoothAdapter.getDefaultAdapter()
            remote_device = adapter.getRemoteDevice(mac_address)

            # Create an RFCOMM socket to the device
            uuid = UUID.fromString(
                "00001101-0000-1000-8000-00805F9B34FB")  # Standard UUID for Serial Port Profile (SPP)
            bt_socket = remote_device.createRfcommSocketToServiceRecord(uuid)
            bt_socket.connect()

            self.log(f"Connected to {mac_address} on channel {channel}")
            return bt_socket
        except Exception as e:
            self.log(f"Failed to connect to {mac_address}: {e}")
            return None

    def graceful_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        self.log("Shutting down...")
        shutdown_event.set()
        if self.bt_socket:
            self.bt_socket.close()

    def log(self, message):
        """Append a message to the log and update the label."""
        self.log_messages += message + "\n"
        self.root.ids.log_label.text = self.log_messages  # Update the log label


if __name__ == '__main__':
    Example().run()
