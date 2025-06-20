"""
Example script demonstrating how to use the pyssp library to connect to a Z CAM camera
and receive video and audio streams from SspClient
"""

import time
import sys
import threading
import requests
import json
import os

import libssp
from dump_h26x import Dumph26x
from preview import PreviewH26xWnd

# Qt imports for GUI
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QRadioButton, QButtonGroup, QCheckBox
from PySide6.QtCore import Qt, QMetaObject, Q_ARG
from PySide6.QtGui import QPalette, QColor


# default camera ip address, you could change it to your camera ip address
DEFAULT_CAMERA_IP = "192.168.1.84"

# Camera IP address
camera_ip = None
stream_index = 1

# Status line for video and audio
video_status = ""
audio_status = ""

# Timestamp of the last video frame
last_pts = 0

# Global event for stopping the client thread
stop_event = threading.Event()

# Global Dumph26x instance for saving H.264 data
DUMP_FOLDER_NAME = "dump"
h264_dump = None

# Global preview widget instance
preview_widget = None

# query stream status and if it is not idle, return False
def query_stream_settings(ip, stream_index):
    """
    query stream settings
    :param ip: camera IP address
    :param stream_index: stream index (0 for stream0, 1 for stream1)
    :return: (bool, dict, str) - (success, stream settings, error message)
    """
    try:
        url = f"http://{ip}/ctrl/stream_setting?index=stream{stream_index}&action=query"
        print(f"\nQuerying {ip} Stream{stream_index} settings with: {url}")
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        print(f"\n{ip} Stream{stream_index} Settings:")
        print(f"  Stream Index: {result.get('streamIndex', 'N/A')}")
        print(f"  Encoder Type: {result.get('encoderType', 'N/A')}")
        print(f"  Bit Width: {result.get('bitwidth', 'N/A')}")
        print(f"  Resolution: {result.get('width', 'N/A')}x{result.get('height', 'N/A')}")
        print(f"  FPS: {result.get('fps', 'N/A')}")
        print(f"  Sample Unit: {result.get('sample_unit', 'N/A')}")
        print(f"  Bitrate: {result.get('bitrate', 'N/A')} kbps")
        print(f"  GOP: {result.get('gop_n', 'N/A')}")
        print(f"  Rotation: {result.get('rotation', 'N/A')}")
        print(f"  Split Duration: {result.get('splitDuration', 'N/A')} seconds")
        print(f"  Status: {result.get('status', 'N/A')}")
        
        if result.get('status') == 'idle':
            print(f"  {ip} Stream{stream_index} is idle...")
            return True, result, ""
        else:
            return False, result, f"Stream is not idle, current status: {result.get('status')}"
            
    except requests.exceptions.RequestException as e:
        return False, None, f"HTTP request failed: {str(e)}"
    except json.JSONDecodeError:
        return False, None, "Invalid JSON response"
    except Exception as e:
        return False, None, f"Unexpected error: {str(e)}"

def sent_stream_index(ip, stream_index):
    """
    send stream index to camera
    :param ip: camera IP address
    :param stream_index: stream index (0 for stream0, 1 for stream1)
    :return: (bool, str) - (success, error message)
    """
    try:
        url = f"http://{ip}/ctrl/set?send_stream=Stream{stream_index}"
        print(f"\nSending request to set Stream{stream_index} with: {url}")
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('code') == 0:
            print(f"{ip} Stream{stream_index} set successfully, response: {result}")
            return True, ""
        else:
            return False, f"Error code: {result.get('code')}, message: {result.get('msg')}"
            
    except requests.exceptions.RequestException as e:
        return False, f"HTTP request failed: {str(e)}"
    except json.JSONDecodeError:
        return False, "Invalid JSON response"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def get_video_encoder_name(encoder_type):
    """
    Convert video encoder type to readable string
    """
    if encoder_type == libssp.VIDEO_ENCODER_H264:
        return "H.264"
    elif encoder_type == libssp.VIDEO_ENCODER_H265:
        return "H.265"
    else:
        return "Unknown"

def get_audio_encoder_name(encoder_type):
    """
    Convert audio encoder type to readable string
    """
    if encoder_type == libssp.AUDIO_ENCODER_AAC:
        return "AAC"
    elif encoder_type == libssp.AUDIO_ENCODER_PCM:
        return "PCM"
    else:
        return "Unknown"

def update_status():
    """
    Update and print the status line
    """
    # Move cursor up two lines
    sys.stdout.write('\033[2A')
    # Clear the two lines
    sys.stdout.write('\033[2K')
    # Print new status
    print(video_status)
    print(audio_status)
    sys.stdout.flush()

def on_h264_data(data):
    """
    Callback function for processing H264 video data
    """
    global last_pts, video_status, h264_dump
    
    # Calculate frame interval (ns)
    duration = 0
    if last_pts > 0:
        duration = data["pts"] - last_pts
    last_pts = data["pts"]
    
    # Update video status
    video_status = f"Video: frm_no = {data['frm_no']}, PTS={data['pts']}, interval={duration}ns, type={data['type']}, size={data['len']} bytes, NTP={data['ntp_timestamp']}"
    update_status()
    
    # Write H.264 data to file using Dumph26x
    if h264_dump and h264_dump.is_running:
        h264_dump.write_frame(data['data'])

    # Send frame to preview widget
    if preview_widget:
        preview_widget.push_frame(data['type'], data['data'])

def on_audio_data(data):
    """
    Callback function for processing audio data
    """
    global audio_status
    audio_status = f"Audio: PTS={data['pts']}, size={data['len']} bytes, NTP={data['ntp_timestamp']}"
    update_status()

def on_meta(video_meta, audio_meta, meta):
    """
    Callback function for processing metadata
    """
    print("\nReceived metadata:")
    print(f"  Wall clock: {meta['pts_is_wall_clock']}")
    print(f"  Video: {video_meta['width']}x{video_meta['height']} timescale={video_meta['timescale']}/{video_meta['unit']}")
    print(f"  Video: gop = {video_meta['gop']}, encoder = {get_video_encoder_name(video_meta['encoder'])}")
    print(f"  Audio: sample rate={audio_meta['sample_rate']}Hz, channel={audio_meta['channel']}")
    print(f"  Audio: bits per sample={8 * audio_meta['sample_size']/audio_meta['unit']} bits, encoder = {get_audio_encoder_name(audio_meta['encoder'])}, bitrate = {audio_meta['bitrate']}")
    # Add two empty lines for status display
    print("\n\n")

def on_disconnected():
    """
    Callback function for disconnection
    """
    print("\nConnection disconnected")
    
    # Set the stop event to break run_client thread
    print("\nrun_client thread will be closed by stop_event")
    stop_event.set()
    
def on_connected():
    """
    Callback function for connection establishment
    """
    print("\nConnection established")
    # Add two empty lines for status display
    print("\n\n")

def on_exception(code, description):
    """
    Callback function for exception handling
    """
    print(f"\nException occurred: code={code}, description={description}")

def on_recv_buffer_full():
    """
    Callback function for receive buffer full
    """
    print("\nReceive buffer is full")

def run_client():
    global h264_dump, preview_widget
    
    if camera_ip is None:
        print("\nNo invalid camera IP, exit")
        return
    
    if stream_index != 0 and stream_index != 1:
        print(f"\nInvalid stream index {stream_index}, exit")
        return
    
    client = None
    
    try:
        # dump h264 data to file using Dumph26x
        if h264_dump is not None:
            h264_dump.start()
        
        # Start preview widget
        if preview_widget:
            preview_widget.start()
        
        # Start the client
        print(f"\nConnecting to camera {camera_ip}...")
        
        # Create SSP client
        # Buffer size set to 4MB, streaming style use STREAM_DEFAULT, it is streaming index 1 by default
        stream_style = libssp.STREAM_MAIN if stream_index == 0 else libssp.STREAM_DEFAULT
        client = libssp.SspClient(camera_ip, 0x400000, 9999, stream_style)
        
        # Enable debug print
        client.set_debug_print(False)
        
        # Set callback functions
        client.on_h264_data = on_h264_data
        client.on_audio_data = on_audio_data
        client.on_meta = on_meta
        client.on_disconnected = on_disconnected
        client.on_connected = on_connected
        client.on_exception = on_exception
        client.on_recv_buffer_full = on_recv_buffer_full
        
        # Set HLG mode
        # client.is_hlg = False
        # client.set_capability(libssp.SSP_CAPABILITY_IGNORE_HEARTBEAT_DISABLE_ENC)
        
        print(f"Starting client...")
        client.start()
        
        # Run until stop signal is received
        while not stop_event.is_set():
            time.sleep(1)
            
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        if client:
            print(f"Stopping client...")
            client.stop()
            print(f"Client stopped...")
            
            print(f"Set Client to None, release sspclient resources")
            client = None
        
        # Stop Dumph26x
        if h264_dump:
            print(f"Stopping H.26x dump...")
            h264_dump.stop()
            h264_dump = None
            
        # Stop preview widget
        if preview_widget:
            print(f"Stopping preview...")
            preview_widget.stop()
            
        print(f"run_client thread closed")
        
# GUI main window class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Z CAM Camera Streaming Example")
        self.resize(1280, 720)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create control panel
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        # Create a grid layout for better alignment
        grid_widget = QWidget()
        grid_layout = QHBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create left side for labels (right-aligned)
        labels_widget = QWidget()
        labels_layout = QVBoxLayout(labels_widget)
        labels_layout.setContentsMargins(0, 0, 10, 0)  # Add right margin for spacing
        
        # Camera IP label
        ip_label = QLabel("Camera IP:")
        ip_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ip_label.setMinimumHeight(26)
        labels_layout.addWidget(ip_label)
        
        # Stream Index label
        stream_label = QLabel("Stream Index:")
        stream_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        stream_label.setMinimumHeight(26)
        labels_layout.addWidget(stream_label)
        
        # Empty label for Record row (to maintain alignment)
        record_label = QLabel("")
        record_label.setMinimumHeight(26)
        labels_layout.addWidget(record_label)
        
        grid_layout.addWidget(labels_widget)
        
        # Create right side for controls (left-aligned)
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Camera IP input and Connect button (first row)
        ip_row = QWidget()
        ip_layout = QHBoxLayout(ip_row)
        ip_layout.setContentsMargins(0, 0, 0, 0)
        
        self.ip_input = QLineEdit(DEFAULT_CAMERA_IP)
        self.ip_input.setMinimumWidth(360)
        self.ip_input.setMinimumHeight(26)
        
        # Create connect button with custom styling
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setMinimumWidth(120)
        self.connect_btn.setMinimumHeight(26)
        
        # Set button styles
        self._update_connect_button_style(False)  # False = not connected (green)
        
        ip_layout.addWidget(self.ip_input)
        ip_layout.addWidget(self.connect_btn)
        ip_layout.addStretch()  # Add stretch to push controls to the left
        controls_layout.addWidget(ip_row)
        
        # Stream index selection (second row) - Radio buttons
        stream_row = QWidget()
        stream_layout = QHBoxLayout(stream_row)
        stream_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create radio buttons for stream selection
        self.stream0_radio = QRadioButton("Stream0 (STREAM_MAIN)")
        self.stream1_radio = QRadioButton("Stream1 (STREAM_DEFAULT/STREAM_SECONDARY)")
        self.stream1_radio.setChecked(True)  # Default to Stream1
        
        # Create button group to ensure only one is selected
        self.stream_group = QButtonGroup()
        self.stream_group.addButton(self.stream0_radio, 0)
        self.stream_group.addButton(self.stream1_radio, 1)
        
        stream_layout.addWidget(self.stream0_radio)
        stream_layout.addWidget(self.stream1_radio)
        stream_layout.addStretch()  # Add stretch to push buttons to the left
        controls_layout.addWidget(stream_row)
        
        # Recording option (third row) - Checkbox
        record_row = QWidget()
        record_layout = QHBoxLayout(record_row)
        record_layout.setContentsMargins(0, 0, 0, 0)
        
        self.record_checkbox = QCheckBox("Record video raw stream to file (store file in `./dump` folder)")
        self.record_checkbox.setChecked(False)  # Default to not recording
        record_layout.addWidget(self.record_checkbox)
        record_layout.addStretch()  # Add stretch to push checkbox to the left
        controls_layout.addWidget(record_row)
        
        grid_layout.addWidget(controls_widget)
        
        control_layout.addWidget(grid_widget)
        layout.addWidget(control_panel)
        
        # Create preview widget
        global preview_widget
        preview_widget = PreviewH26xWnd()
        layout.addWidget(preview_widget)
        
        # Initialize client thread
        self.client_thread = None
        
    def _connect_camera(self):
        """
        Connect to camera
        """
        # Start connection
        global camera_ip, stream_index, h264_dump
        
        # Get camera IP
        camera_ip = self.ip_input.text()
        if not camera_ip:
            QMessageBox.warning(self, "Warning", "Please enter camera IP")
            return
        
        # Get stream index
        try:
            stream_index = self.stream_group.checkedId()
            if stream_index not in [0, 1]:
                raise ValueError("Invalid stream index")
        except ValueError:
            QMessageBox.warning(self, "Warning", "Stream index must be 0 or 1")
            return
        
        # Query stream settings
        success, stream_info, error_msg = query_stream_settings(camera_ip, stream_index)
        if not success:
            QMessageBox.warning(self, "Error", f"Streaming failed: {error_msg}")
            return
        
        # Send stream index
        success, error_msg = sent_stream_index(camera_ip, stream_index)
        if not success:
            QMessageBox.warning(self, "Error", f"Failed to send stream index: {error_msg}")
            return
        
        # get stream encoder type from streaming info
        dump_encoder_type = stream_info.get('encoderType', 'N/A')
        
        # Check recording option
        record_option = self.record_checkbox.isChecked()
        if record_option:
            # dump stream data to file using Dumph26x
            # file extension is the same as encoder type, so VLC can play it
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dump_file_name = os.path.join(os.path.dirname(__file__), DUMP_FOLDER_NAME, f"camera_{camera_ip}_stream{stream_index}_{timestamp}.{dump_encoder_type}")
            
            if not os.path.exists(os.path.dirname(dump_file_name)):
                os.makedirs(os.path.dirname(dump_file_name))
            if os.path.exists(dump_file_name):
                os.remove(dump_file_name)
            
            h264_dump = Dumph26x(dump_file_name)
            print(f"\nRecording {dump_encoder_type} data to: {dump_file_name}")
        else:
            h264_dump = None
        
        # Start client thread
        stop_event.clear()
        self.client_thread = threading.Thread(target=run_client)
        self.client_thread.daemon = True
        self.client_thread.start()
        
        # Update UI
        self._update_connect_button_style(True)
        self.ip_input.setEnabled(False)
        self.stream0_radio.setEnabled(False)
        self.stream1_radio.setEnabled(False)
        self.record_checkbox.setEnabled(False)
            
    def _disconnect_camera(self):
        """
        Disconnect from camera
        """
        stop_event.set()
        
        if self.client_thread and self.client_thread.is_alive():
            self.client_thread.join(timeout=10)
        
        # Update UI
        self._update_connect_button_style(False)
        self.ip_input.setEnabled(True)
        self.stream0_radio.setEnabled(True)
        self.stream1_radio.setEnabled(True)
        self.record_checkbox.setEnabled(True)
        
    def toggle_connection(self):
        if self.connect_btn.text() == "Connect":
            self._connect_camera()
        else:
            self._disconnect_camera()
           
    def closeEvent(self, event):
        """
        Callback function for closing the window
        """
        print("Closing window...")
        stop_event.set()
        
        if self.client_thread and self.client_thread.is_alive():
            self.client_thread.join(timeout=10)
        
        # Update UI
        self._update_connect_button_style(False)
        self.ip_input.setEnabled(True)
        self.stream0_radio.setEnabled(True)
        self.stream1_radio.setEnabled(True)
        self.record_checkbox.setEnabled(True)
        
        event.accept()

    def keyPressEvent(self, event):
        """
        Callback function for key press event
        """
        if event.key() == Qt.Key_Escape:
            self.close()
            
    def _update_connect_button_style(self, connected):
        """
        Update the connect button style based on connection status
        """
        if connected:
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    border: 2px solid #b71c1c;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #f44336;
                    border-color: #d32f2f;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                    border-color: #8e0000;
                }
            """)
        else:
            self.connect_btn.setText("Connect")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4caf50;
                    color: white;
                    border: 2px solid #388e3c;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #66bb6a;
                    border-color: #4caf50;
                }
                QPushButton:pressed {
                    background-color: #388e3c;
                    border-color: #2e7d32;
                }
            """)

# run example with Qt GUI window           
def run_main_gui():
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create main window
    window = MainWindow()
    window.show()
    
    # Run application
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("Received Ctrl+C, stopping...")
        stop_event.set() 
        
# run example with command line
def run_main_cli():
    global camera_ip, stream_index, h264_dump
    print(f"Please input z-cam camera IP (default: {DEFAULT_CAMERA_IP}):")
    
    # get camera IP from user input
    camera_ip = input()
    if not camera_ip:
        print(f"No invalid camera IP, use default IP {DEFAULT_CAMERA_IP}")
        camera_ip = DEFAULT_CAMERA_IP
    
    # get stream index from user input
    print("\nPlease select stream index:")
    print("0. Stream0 (STREAM_MAIN)")
    print("1. Stream1 (STREAM_DEFAULT)")
    # stream_index = int(input("Enter your choice (0 or 1): "))
    stream_index = 1
    stream_choice = input("Enter your choice (1 or 0): ")
    if not stream_choice and stream_choice == "0":
        stream_index = 0
    
    # query stream settings, if stream is not idle, exit
    success, stream_info, error_msg = query_stream_settings(camera_ip, stream_index)
    if not success:
        print(f"Streaming Failed: {error_msg}")
        sys.exit(1)
    
    # send stream index to camera, so SspClient can do streaming for specified stream
    success, error_msg = sent_stream_index(camera_ip, stream_index)
    if not success:
        print(f"Failed to send stream index {stream_index}: {error_msg}")
        sys.exit(1)
    
    # get stream encoder type from streaming info
    dump_encoder_type = stream_info.get('encoderType', 'N/A')
    
    # get user input to dump stream data to file or not
    print(f"\nDo you want to dump {dump_encoder_type} stream data to file? (y/n):")
    dump_h264 = input()
    if dump_h264 is not None and (dump_h264 == "y" or dump_h264 == "Y"):
        # dump stream data to file using Dumph26x
        # file extension is the same as encoder type, so VLC can play it
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        dump_file_name = os.path.join(os.path.dirname(__file__), DUMP_FOLDER_NAME, f"camera_{camera_ip}_stream{stream_index}_{timestamp}.{dump_encoder_type}")
        if not os.path.exists(os.path.dirname(dump_file_name)):
            os.makedirs(os.path.dirname(dump_file_name))   
        if os.path.exists(dump_file_name):
            os.remove(dump_file_name)
        
        h264_dump = Dumph26x(dump_file_name)
        print(f"\nDumping {dump_encoder_type} data to file: {dump_file_name}")
    else:
        h264_dump = None

    # Create a thread to run ssp client
    client_thread = threading.Thread(target=run_client)
    client_thread.daemon = True
    client_thread.start()
    
    try:
        # Add two empty lines for status display
        print("\n\n")
        
        # Main thread wait
        while client_thread.is_alive():
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Received Ctrl+C, stopping...")
        stop_event.set()
        
        if client_thread.is_alive():
            print(f"Waiting for client thread to end (timeout 10 seconds)...")
            client_thread.join(timeout=10)  
            print(f"Client thread ended")

if __name__ == "__main__":
    # if argument is provided, run as gui or cli
    print("Usage: python example.py [-cli|-gui]")
    print("If '-cli' is provided, run as command line, otherwise run as Qt gui window")
    
    if len(sys.argv) > 1 and (sys.argv[1] == "-cli" or sys.argv[1] == "--cli"):
        run_main_cli()
    else:
        run_main_gui()


        
        