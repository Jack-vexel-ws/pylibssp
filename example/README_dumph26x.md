# Dumph26x Class

## Overview

`Dumph26x` is a simple Python class for saving H.264/H.265 video stream data to files directly. It uses a separate thread for file writing to avoid blocking the main thread.

## Features

- **Thread-safe**: Non-blocking file writing
- **Queue-based**: Buffers frame data using `queue.Queue`
- **Auto-cleanup**: Writes remaining data when stopping
- **Progress monitoring**: Reports progress every 100 frames

## Basic Usage

```python
from dump_h26x import Dumph26x

# Create instance
dump = Dumph26x("output.h264")

# Start dumping
dump.start()

# Write frame data
dump.write_frame(h264_frame_data)

# Stop dumping
dump.stop()
```

## Integration with example.py

```python
# Global variable
h264_dump = None

# Initialize in run_client()
def run_client():
    global h264_dump
    h264_dump = Dumph26x("camera_stream.h264")
    h264_dump.start()
    # ... other code ...
    if h264_dump:
        h264_dump.stop()

# Use in callback
def on_h264_data(data):
    if h264_dump and h264_dump.is_running:
        h264_dump.write_frame(data['data'])
```

## Methods

- `__init__(file_path)`: Initialize with output file path
- `start()`: Start the dump thread
- `stop()`: Stop and close file
- `write_frame(frame_data)`: Add frame data to queue

## Thread Safety

- `write_frame()` is thread-safe
- Uses `queue.Queue` for data transmission
- Waits for all data to be written when stopping

## Error Handling

- Drops frames if queue is full
- Drops frames if not running
- Catches file write errors
- Auto-cleanup on stop

## File Format

Standard H.264/H.265 raw stream file with NAL units. Can be played with VLC, etc.
If you want to convert to MP4, use ffmpeg like this:
```bash
ffmpeg -i -r 30000/1001 input.h264 -c copy output.mp4
# or
ffmpeg -i -r 50 input.h264 -c copy output.mp4
``` 
>**NOTE**: '-r 30000/1001` is the frame rate of your H.264/H.265 raw streams. 30000/1001 means frame rate 29.97.If your streaming is a different rate, you may need to adjust the frame rate accordingly.
**THIS IS CRITICAL FOR PLAYBACK**.
