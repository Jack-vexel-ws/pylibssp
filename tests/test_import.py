"""
Test script demonstrating how to import the pyssp library
"""
import libssp

# default camera ip address, you could change it to your camera ip address
camera_ip = "192.168.1.84"  # Replace with your camera IP

# Set callback functions
def on_h264_data(data):
    """Handle H.264 video data"""
    print(f"Video: frm_no = {data['frm_no']}, PTS={data['pts']}, type={data['type']}, size={data['len']} bytes, NTP={data['ntp_timestamp']}")

def on_audio_data(data):
    """Handle audio data"""
    print(f"Audio: PTS={data['pts']}, size={data['len']} bytes, NTP={data['ntp_timestamp']}")

def on_meta(video_meta, audio_meta, meta):
    """Handle metadata"""
    print(f"Video metadata: {video_meta}")
    print(f"Audio metadata: {audio_meta}")
    print(f"Other metadata: {meta}")

def on_connected():
    """Connected callback"""
    print("Connected to camera")

def on_disconnected():
    """
    Callback function for disconnection
    """
    print("\nConnection disconnected")


try:
    # Create SspClient instance
    client = libssp.SspClient(camera_ip, 0x400000, 9999, libssp.STREAM_DEFAULT)

    # Set callback functions
    client.on_h264_data = on_h264_data
    client.on_audio_data = on_audio_data
    client.on_meta = on_meta
    client.on_disconnected = on_disconnected
    client.on_connected = on_connected

    # Start client
    client.start()

    # Keep connection for a while
    import time
    time.sleep(5)

    # Stop client
    client.stop()
    
except Exception as e:
    print(f"Error creating SspClient instance: {e}")
    exit(1)
