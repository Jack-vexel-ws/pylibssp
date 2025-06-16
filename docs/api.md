# PyLibSSP API Documentation

## SspClient Class

The `SspClient` class provides a Python interface for SSP communication with Z CAM cameras.

### Initialization

```python
from libssp import SspClient

client = SspClient(ip, buf_size, port=9999, stream_style=STREAM_DEFAULT)
```

**Parameters:**
- `ip` (str): Camera IP address
- `buf_size` (int): Receive buffer size (recommended: 0x400000, 4MB)
- `port` (int, optional): SSP server port, defaults to 9999
- `stream_style` (int, optional): Stream type, options:
  - `STREAM_MAIN`: Main stream (Stream0)
  - `STREAM_DEFAULT`: Default stream (Stream1)

### Basic Operations

#### Start and Stop

```python
# Start the client
client.start()

# Stop the client
client.stop()

# Using context manager
with SspClient(ip, buf_size) as client:
    # Client will start automatically
    pass
# Client will stop automatically when exiting the context
```

### Callbacks

#### Video Data Callback

```python
def on_h264_data(data_dict):
    """
    Handle H264 video data
    
    Parameters:
        data_dict (dict): Dictionary containing:
            - data (bytes): H264 data
            - len (int): Data length
            - pts (int): Presentation timestamp
            - ntp_timestamp (int): NTP timestamp
            - frm_no (int): Frame number
            - type (int): Frame type (I or P)
    """
    pass

client.on_h264_data = on_h264_data
```

#### Audio Data Callback

```python
def on_audio_data(data_dict):
    """
    Handle audio data
    
    Parameters:
        data_dict (dict): Dictionary containing:
            - data (bytes): Audio data
            - len (int): Data length
            - pts (int): Presentation timestamp
            - ntp_timestamp (int): NTP timestamp
    """
    pass

client.on_audio_data = on_audio_data
```

#### Metadata Callback

```python
def on_meta(video_meta, audio_meta, meta):
    """
    Handle metadata
    
    Parameters:
        video_meta (dict): Video metadata
        audio_meta (dict): Audio metadata
        meta (dict): General metadata
    """
    pass

client.on_meta = on_meta
```

#### Connection Status Callbacks

```python
def on_connected():
    """Callback when connection is established"""
    pass

def on_disconnected():
    """Callback when connection is lost"""
    pass

client.on_connected = on_connected
client.on_disconnected = on_disconnected
```

#### Exception Callback

```python
def on_exception(code, description):
    """
    Handle exceptions
    
    Parameters:
        code (int): Error code
        description (str): Error description
    """
    pass

client.on_exception = on_exception
```

#### Buffer Full Callback

```python
def on_recv_buffer_full():
    """Callback when receive buffer is full"""
    pass

client.on_recv_buffer_full = on_recv_buffer_full
```

### Additional Features

#### HLG Mode

```python
# Get HLG mode status
is_hlg = client.is_hlg

# Set HLG mode
client.is_hlg = True  # Enable HLG mode
client.is_hlg = False  # Disable HLG mode
```

#### Client Capability

```python
from libssp import SSP_CAPABILITY_IGNORE_HEARTBEAT_DISABLE_ENC

# Set client capability
client.set_capability(SSP_CAPABILITY_IGNORE_HEARTBEAT_DISABLE_ENC)
```

#### Debug Print

```python
# Enable debug print
client.set_debug_print(True)

# Disable debug print
client.set_debug_print(False)
```

### Constants

#### Stream Types
```python
from libssp import (
    STREAM_DEFAULT,  # Default stream (Stream1)
    STREAM_MAIN,     # Main stream (Stream0)
    STREAM_SEC       # Secondary stream
)
```

#### Video Encoders
```python
from libssp import (
    VIDEO_ENCODER_UNKNOWN,
    VIDEO_ENCODER_H264,
    VIDEO_ENCODER_H265
)
```

#### Audio Encoders
```python
from libssp import (
    AUDIO_ENCODER_UNKNOWN,
    AUDIO_ENCODER_AAC,
    AUDIO_ENCODER_PCM
)
```

#### Error Codes
```python
from libssp import (
    ERROR_SSP_PROTOCOL_VERSION_GT_SERVER,
    ERROR_SSP_PROTOCOL_VERSION_LT_SERVER,
    ERROR_SSP_CONNECTION_FAILED,
    ERROR_SSP_CONNECTION_EXIST
)
```

#### Capability Flags
```python
from libssp import SSP_CAPABILITY_IGNORE_HEARTBEAT_DISABLE_ENC
```

### Usage Example

```python
from libssp import SspClient, STREAM_MAIN

def on_h264_data(data_dict):
    # Handle video data
    print(f"Received H264 frame: {data_dict['frm_no']}")

def on_audio_data(data_dict):
    # Handle audio data
    print(f"Received audio data: {data_dict['len']} bytes")

def on_meta(video_meta, audio_meta, meta):
    # Handle metadata
    print("Received metadata")

# Create client
client = SspClient("192.168.1.84", 0x400000, stream_style=STREAM_MAIN)

# Set callbacks
client.on_h264_data = on_h264_data
client.on_audio_data = on_audio_data
client.on_meta = on_meta

# Enable debug print
client.set_debug_print(True)

# Start client
client.start()

# ... Process data ...

# Stop client
client.stop()
```

### Important Notes

1. Ensure the camera IP address is correct and accessible
2. Recommended buffer size is 4MB (0x400000)
3. Use context manager (with statement) to ensure proper resource cleanup
4. All callback functions should return quickly to avoid blocking the main thread
5. Ensure all data processing is complete before stopping the client 