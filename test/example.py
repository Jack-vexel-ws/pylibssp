"""
Example script demonstrating how to use the pyssp library to connect to a Z CAM camera
and receive video and audio streams from SspClient
"""

import time
import sys
import threading
import requests
import json

import libssp

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
        print(f"Response: {result}")
        
        if result.get('code') == 0:
            print(f"{ip} Stream{stream_index} set successfully...")
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
    global last_pts, video_status
    
    # Calculate frame interval (ns)
    duration = 0
    if last_pts > 0:
        duration = data["pts"] - last_pts
    last_pts = data["pts"]
    
    # Update video status
    video_status = f"Video: frm_no = {data['frm_no']}, PTS={data['pts']}, interval={duration}ns, type={data['type']}, size={data['len']} bytes, NTP={data['ntp_timestamp']}"
    update_status()
    
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
    
    if camera_ip is None:
        print("\nNo invalid camera IP, exit")
        return
    
    if stream_index != 0 and stream_index != 1:
        print(f"\nInvalid stream index {stream_index}, exit")
        return
    
    client = None
    
    try:
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
            
        print(f"run_client thread closed")
        
if __name__ == "__main__":
    
    print("Please input z-cam camera IP (192.168.1.124):")
    
    # get camera IP from user input
    camera_ip = input()
    DEFAULT_CAMERA_IP = "192.168.1.84"
    if not camera_ip:
        print(f"No invalid camera IP, use default IP {DEFAULT_CAMERA_IP}")
        camera_ip = DEFAULT_CAMERA_IP
    
    # get stream index from user input
    print("\nPlease select stream index:")
    print("0. Stream0 (STREAM_MAIN)")
    print("1. Stream1 (STREAM_DEFAULT)")
    stream_index = int(input("Enter your choice (0 or 1): "))
    
    if stream_index != 0 and stream_index != 1:
        print("Invalid choice, exit")
        sys.exit(1)
    
    # query stream settings, if stream is not idle, exit
    success, stream_info, error_msg = query_stream_settings(camera_ip, stream_index)
    if not success:
        print(f"Failed to query stream settings: {error_msg}")
        sys.exit(1)
    
    input("\nPress Enter to continue...")
    
    # send stream index to camera, so SspClient can do streaming for specified stream
    success, error_msg = sent_stream_index(camera_ip, stream_index)
    if not success:
        print(f"Failed to send stream index {stream_index}: {error_msg}")
        sys.exit(1)
    
    input("\nPress Enter to continue...")
        
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
        
        