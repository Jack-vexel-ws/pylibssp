# Preview.py - H.264/H.265 Video Preview Module

## Overview

`preview.py` provides two classes for H.264/H.265 video stream decoding and display:
- `DecodeH26x`: Video decoder using av package
- `PreviewH26xWnd`: Qt widget for video display

## Features

- **Hardware/Software Decoding**: Supports H.264 and H.265 codecs
- **Thread-safe**: Separate threads for decoding and display
- **Queue-based**: Buffered frame processing
- **Qt Integration**: Native Qt widget for display
- **Real-time Preview**: Live video stream display

## Classes

### DecodeH26x

H.264/H.265 video decoder with thread-safe queue processing.

#### Methods

- `__init__(queue_size=30)`: Initialize decoder with queue size
- `start()`: Start decode thread
- `stop()`: Stop decode thread
- `push_frame(frame_type, frame_raw_data)`: Add frame to decode queue

#### Signals

- `frame_decoded(frame)`: Emitted when frame is decoded

### PreviewH26xWnd

Qt widget for displaying decoded video streams.

#### Methods

- `__init__(parent=None)`: Initialize preview widget
- `start()`: Start preview (decoder + display)
- `stop()`: Stop preview
- `push_frame(frame_type, frame_raw_data)`: Send frame to decoder

## Usage

### Basic Usage

```python
from preview import PreviewH26xWnd
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout

# Create Qt application
app = QApplication(sys.argv)

# Create main window
window = QMainWindow()
central_widget = QWidget()
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)

# Create preview widget
preview = PreviewH26xWnd()
layout.addWidget(preview)

# Start preview
preview.start()

# Show window
window.show()

# Run application
app.exec()
```

### Integration with example.py

```python
from preview import PreviewH26xWnd

# Create preview widget
preview_widget = PreviewH26xWnd()

# In on_h264_data callback
def on_h264_data(data):
    if preview_widget:
        preview_widget.push_frame(data['type'], data['data'])

# Start preview
preview_widget.start()

# Stop preview
preview_widget.stop()
```

## Dependencies

- `av`: Video decoding
- `PySide6`: Qt GUI framework
- `numpy`: Array operations
- `threading`: Thread management
- `queue`: Thread-safe queues

## Performance

- **Decode Queue**: Configurable size (default: 30 frames)
- **Display Queue**: Limited to 3 frames
- **Display Rate**: ~60 FPS (16ms timer)
- **Thread Safety**: All operations are thread-safe

## Error Handling

- Queue overflow protection
- Decode error recovery
- Thread cleanup on stop
- Graceful degradation

## Example

See `example_with_preview.py` for complete integration example with Z CAM camera streaming. 