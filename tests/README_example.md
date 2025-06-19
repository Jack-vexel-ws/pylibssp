# Example.py - Z CAM Camera Streaming Client

## Overview

`example.py` demonstrates how to use the `pylibssp` library to connect to a Z CAM camera and receive real-time video and audio streams. It shows streaming connection, data handling, and optional file recording.

## Features

- **Camera Connection**: Connect to Z CAM cameras via network
- **Stream Selection**: Choose between Stream0 (STREAM_MAIN) and Stream1 (STREAM_DEFAULT)
- **Real-time Streaming**: Receive live video and audio data
- **Status Monitoring**: Real-time display of stream statistics
- **Optional Recording**: Save H.264/H.265 stream data to file
- **Error Handling**: Comprehensive error handling and connection management

## Usage

### Basic Usage

1. **Run the script**:
   ```bash
   python example.py
   ```

2. **Enter camera IP address**:
   ```
   Please input z-cam camera IP (default: 192.168.1.84):
   ```

3. **Select stream index**:
   ```
   Please select stream index:
   0. Stream0 (STREAM_MAIN)
   1. Stream1 (STREAM_DEFAULT)
   Enter your choice (0 or 1):
   ```

4. **Choose recording option**:
   ```
   Do you want to dump H.264/H.265 stream data to file? (y/n):
   ```

## Key Functions

### Stream Settings

- `query_stream_settings(ip, stream_index)`: Query camera stream settings
- `sent_stream_index(ip, stream_index)`: Send stream selection command to camera

### Callback Functions

- `on_h264_data(data)`: Handle H.264 video data
- `on_audio_data(data)`: Handle audio data
- `on_meta(video_meta, audio_meta, meta)`: Handle stream metadata
- `on_connected()`: Connection established
- `on_disconnected()`: Connection lost

## Configuration

### Camera Settings

- **Default IP**: 192.168.1.84, you can change it by entering your camera IP 
- **Buffer Size**: 4MB (0x400000)
- **Port**: default 9999
- **Stream Styles**: Stream0 (STREAM_MAIN), Stream1 (STREAM_DEFAULT), default is stream1

### Recording Options

When recording is enabled:
- Files saved to `tests/dump/` directory as default
- Filename: `camera_{IP}_stream{INDEX}_{TIMESTAMP}.{CODEC}`
- Supported: H.264, H.265

## Threading Model

- **Main Thread**: User interaction and status display
- **Client Thread**: Camera connection and SspClient lifecycle
- **Dumph26x Thread**: File writing operations (if recording)

## Output Files



### Recorded Streams
- **[`Dumph26x`](tests/dump_h26x.py)**: class for recording H.264/H.265 streams to raw video files, please refer to **[README_dumph26x](tests/README_dumph26x.py)** for more details
- **Location**: example use `tests/dump/` as default dump directory, you can change `DUMP_FOLDER_NAME` to your wanted directory in `example.py`
- **Format**: Raw H.264/H.265 video stream
- **Playback**: VLC can play raw video stream files directly

### Example filenames
```
camera_192.168.1.84_stream1_20231201_143022.h264
camera_192.168.1.84_stream0_20231201_143022.h265
```
### **Convert to MP4**

To convert the raw H.264/H.265 files to MP4 format, you can use the following **`ffmpeg`** command:

```bash
ffmpeg -i -r 30000/1001 source_file.h264 -c copy dest_file.mp4
```
>**NOTE**: '-r 30000/1001` is the frame rate of your H.264/H.265 raw streams. 30000/1001 means frame rate 29.97.If your streaming is a different rate, you may need to adjust the frame rate accordingly. **THIS IS CRITICAL FOR PLAYBACK**.

## Integration

### Using in Your Own Code

```python
import libssp
from dump_h26x import Dumph26x

# Create client
client = libssp.SspClient(camera_ip, buffer_size, port, stream_style)

# Set callbacks
client.on_h264_data = your_h264_handler
client.on_audio_data = your_audio_handler
client.on_meta = your_meta_handler

# Start streaming
client.start()

# Optional recording
dump = Dumph26x("output.h264")
dump.start()
```

## Common Issues

1. **Camera not found**: Check network connectivity and IP address, please make sure camera be in same LocalLAN with your computer
2. **Stream not available**: Verify your selected stream(0 or 1) is **`idle`** , if selected stream is in use, streaming will failed
3. **Stream Settings**: Please use Z CAM offical **[HTTP API command](https://github.com/imaginevision/Z-Camera-Doc/blob/master/E2/protocol/http/http.md)** to config your `stream1` settings - resolution, gop, bitrate, encoder, etc. `stream0` basic settings is same with your camera shoot format.