#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example script demonstrating how to use the pyssp library to connect to a Z CAM camera
and receive video and audio streams from SspClient
"""

import time
import sys
import threading
import libssp

# Camera IP address
camera_ip = None

# Status line for video and audio
video_status = ""
audio_status = ""

# Timestamp of the last video frame
last_pts = 0

# Global event for stopping the client thread
stop_event = threading.Event()

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
    
    client = None
    
    try:
        # Start the client
        print(f"\nConnecting to camera {camera_ip}...")
        
        # Create SSP client
        # Buffer size set to 4MB, streaming style use STREAM_DEFAULT, it is streaming index 1 by default
        client = libssp.SspClient(camera_ip, 0x400000, 9999, libssp.STREAM_DEFAULT)
        
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
    
    camera_ip = input()
    if not camera_ip:
        # print("No invalid camera IP, exit")
        # sys.exit(1)
        camera_ip = "192.168.1.84"
        
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
        
        