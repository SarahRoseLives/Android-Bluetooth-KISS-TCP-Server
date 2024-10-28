import socket
import threading
import os
import signal
from threading import Event
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.list import OneLineListItem
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.clock import Clock

# Bluetooth connection settings
DEVICE_NAMES = ["UV-PRO", "VR-N76", "GA-5WB"]
DATA_CHANNEL_ID = 3  # RFCOMM channel for Bluetooth (not all devices use 1, adjust as needed)

# TCP Server settings
TCP_HOST = '0.0.0.0'
TCP_PORT = 8001

# Create a global shutdown event
shutdown_event = Event()

# Java classes for Bluetooth
from jnius import autoclass
BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
BluetoothSocket = autoclass('android.bluetooth.BluetoothSocket')
UUID = autoclass('java.util.UUID')

KV = '''
MDBoxLayout:
    orientation: "vertical"

    MDTopAppBar:
        title: "Bluetooth TCP Bridge"

    MDLabel:
        id: ip_label
        text: "IP Address: " + app.get_ip_address() + ":8001"  # Display the device's IP address
        halign: "center"
        size_hint_y: None
        height: dp(40)  # Set height for the IP address label

    ScrollView:
        MDList:
            id: log_list  # To hold log messages

    MDRaisedButton:
        text: "Start Bluetooth Server"
        size_hint_y: None
        height: dp(56)
        on_release: app.start_process()  # Trigger the start process when the button is pressed
'''

class BluetoothApp(MDApp):
    def build(self):
        return Builder.load_string(KV)

    def get_ip_address(self):
        """Get the IP address of the device on the local network."""
        try:
            # Create a socket connection to an external service to get the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)  # Set a timeout of 0 seconds to avoid blocking
            s.connect(("10.254.254.254", 1))  # Use an arbitrary address
            ip_address = s.getsockname()[0]  # Get the IP address of the device
        except Exception as e:
            ip_address = "Unable to get IP"
        finally:
            s.close()
        return ip_address

    def update_log(self, message):
        """Update the log messages in the UI."""
        # Schedule the update on the main thread
        Clock.schedule_once(lambda dt: self._add_log(message))

    def _add_log(self, message):
        """Internal method to add a log message."""
        log_item = OneLineListItem(text=message)
        self.root.ids.log_list.add_widget(log_item)

    def start_process(self):
        """Start the Bluetooth and TCP server process."""
        self.update_log("Starting Bluetooth server...")
        # Start the signal handlers only in the main thread
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)

        threading.Thread(target=self.main_process, daemon=True).start()

    def main_process(self):
        """Implement your main process for Bluetooth and TCP here."""
        mac_address = self.find_bluetooth_device()

        if not mac_address:
            self.update_log("Failed to find any Bluetooth device. Exiting...")
            return

        self.bt_socket = self.connect_bluetooth(mac_address, DATA_CHANNEL_ID)
        if not self.bt_socket:
            self.update_log("Failed to connect to Bluetooth device. Exiting...")
            return

        # Create the TCP server socket
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.start_tcp_server()

    def find_bluetooth_device(self):
        """Scan for Bluetooth devices using Android's native Bluetooth API."""
        adapter = BluetoothAdapter.getDefaultAdapter()
        if not adapter.isEnabled():
            self.update_log("Enabling Bluetooth adapter...")
            adapter.enable()

        self.update_log("Scanning for Bluetooth devices...")
        paired_devices = adapter.getBondedDevices().toArray()

        for device in paired_devices:
            device_name = device.getName()
            device_mac = device.getAddress()
            self.update_log(f"Found Bluetooth device: {device_name} - {device_mac}")

            for name in DEVICE_NAMES:
                if name.lower() in device_name.lower():
                    self.update_log(f"Matched device '{device_name}' with {name}.")
                    return device_mac

        self.update_log("No matching Bluetooth devices found.")
        return None

    def connect_bluetooth(self, mac_address, channel):
        """Connect to Bluetooth device using RFCOMM protocol (via Pyjnius)."""
        try:
            adapter = BluetoothAdapter.getDefaultAdapter()
            remote_device = adapter.getRemoteDevice(mac_address)

            # Create an RFCOMM socket to the device
            uuid = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")  # Standard UUID for Serial Port Profile (SPP)
            bt_socket = remote_device.createRfcommSocketToServiceRecord(uuid)
            bt_socket.connect()

            self.update_log(f"Connected to {mac_address} on channel {channel}")
            return bt_socket
        except Exception as e:
            self.update_log(f"Failed to connect to {mac_address}: {e}")
            return None

    def start_tcp_server(self):
        """Start a TCP server that forwards data between TCP clients and Bluetooth socket."""
        try:
            self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse
            self.tcp_socket.bind((TCP_HOST, TCP_PORT))
            self.tcp_socket.listen(1)
            self.update_log(f"TCP server started on port {TCP_PORT}. Waiting for client connection...")

            while not shutdown_event.is_set():
                try:
                    client_sock, client_address = self.tcp_socket.accept()
                    self.update_log(f"Client connected from {client_address}")

                    # Create separate threads to handle Bluetooth <-> TCP data transfer
                    bt_to_tcp_thread = threading.Thread(target=self.handle_bt_to_tcp,
                                                        args=(self.bt_socket, client_sock), daemon=True)
                    tcp_to_bt_thread = threading.Thread(target=self.handle_tcp_to_bt,
                                                        args=(client_sock, self.bt_socket), daemon=True)

                    bt_to_tcp_thread.start()
                    tcp_to_bt_thread.start()
                except socket.timeout:
                    continue  # Timeout occurred, loop again to check for shutdown_event

        except Exception as e:
            self.update_log(f"TCP Server error: {e}")

    def handle_bt_to_tcp(self, bt_sock, client_sock):
        """Forward data from Bluetooth to the TCP client."""
        try:
            while not shutdown_event.is_set():
                try:
                    input_stream = bt_sock.getInputStream()
                    buffer = bytearray(1024)  # Create a buffer for reading
                    bytes_read = input_stream.read(buffer)  # Read into the buffer
                    if bytes_read > 0:
                        data = bytes(buffer[:bytes_read])  # Convert to bytes
                        self.update_log(f"Received from Bluetooth: {data}")
                        client_sock.sendall(data)
                except Exception as e:
                    self.update_log(f"Error reading from Bluetooth: {e}")
                    break
        finally:
            client_sock.close()

    def handle_tcp_to_bt(self, client_sock, bt_sock):
        """Forward data from the TCP client to the Bluetooth device."""
        try:
            while not shutdown_event.is_set():
                try:
                    data = client_sock.recv(1024)  # Read data from TCP client
                    if data:
                        self.update_log(f"Received from TCP client: {data}")
                        bt_sock.getOutputStream().write(data)
                except Exception as e:
                    self.update_log(f"Error reading from TCP client: {e}")
                    break
        finally:
            client_sock.close()

    def graceful_shutdown(self, sig=None, frame=None):
        """Handle graceful shutdown of the application."""
        self.update_log("Shutting down gracefully...")
        shutdown_event.set()
        if hasattr(self, 'bt_socket') and self.bt_socket:
            self.bt_socket.close()
            self.update_log("Bluetooth socket closed.")
        if hasattr(self, 'tcp_socket') and self.tcp_socket:
            self.tcp_socket.close()
            self.update_log("TCP server socket closed.")
        os._exit(0)

if __name__ == '__main__':
    BluetoothApp().run()
