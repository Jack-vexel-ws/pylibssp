#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Preview module for H.264/H.265 video stream decoding and display
Contains DecodeH26x and PreviewH26xWnd classes
"""

import time
import threading
import queue
import av
import numpy as np
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QFont

class DecodeH26x(QObject):
    """
    H.264/H.265 video decoder using av package
    Decodes video raw data and emits decoded frames via Qt signals
    """
    
    # Qt signal for decoded frames
    frame_decoded = Signal(object)  # Emits decoded av.VideoFrame
    
    def __init__(self, queue_size=30):
        """
        Initialize decoder
        
        Args:
            queue_size (int): Maximum size of the frame queue
        """
        super().__init__()
        
        # Initialize decoder
        self.codec = None
        self.running = False
        self.stop_event = threading.Event()
        self.decode_thread = None
        
        # Frame queue for incoming raw data (thread-safe by default)
        self.frame_queue = queue.Queue(maxsize=queue_size)
        
    def _init_codec(self, encoder_type):
        """Initialize H.264/H.265 decoder, prefer hardware decoder if available."""

        # List of hardware decoders to try first
        hw_decoder_map = {
            'h264': ['h264_cuvid', 'h264_qsv', 'h264_dxva2', 'h264_d3d11va', 'h264_vaapi', 'h264_v4l2m2m'],
            'hevc': ['hevc_cuvid', 'hevc_qsv', 'hevc_dxva2', 'hevc_d3d11va', 'hevc_vaapi', 'hevc_v4l2m2m']
        }

        encoder_type_norm = encoder_type.lower()
        if encoder_type_norm in ['h264', 'avc']:
            codec_key = 'h264'
        elif encoder_type_norm in ['h265', 'hevc']:
            codec_key = 'hevc'
        else:
            print(f"Unknown encoder type '{encoder_type}', using H.264 as default")
            codec_key = 'h264'

        # Try hardware decoders
        hw_decoders = hw_decoder_map[codec_key]
        codec_created = False

        for codec_name in hw_decoders:
            try:
                self.codec = av.CodecContext.create(codec_name, 'r')
                self.codec.open()
                print(f"✅ Initialized hardware decoder: {codec_name}")
                codec_created = True
                break
            except av.AVError as e:
                print(f"⚠ Failed to initialize hardware decoder {codec_name}: {e}")
                continue
            except Exception as e:
                print(f"⚠ Unexpected error with {codec_name}: {e}")
                continue

        # If all hardware decoders fail, fall back to software decoder
        if not codec_created:
            try:
                sw_codec_name = codec_key
                self.codec = av.CodecContext.create(sw_codec_name, 'r')

                # Configure software decoder parameters like threads
                self.codec.options.update({
                    'threads': '1',
                    'thread_type': 'slice'
                })

                self.codec.open()
                print(f"✅ Initialized software decoder: {sw_codec_name}")
            except Exception as e:
                print(f"❌ Failed to initialize software decoder {sw_codec_name}: {e}")
                raise
        
    def start(self, encoder_type='h264'):
        """Start the decode thread with specified encoder type"""
        if self.running:
            print("Decoder is already running")
            return
            
        # Initialize codec with specified encoder type
        self._init_codec(encoder_type)
            
        self.running = True
        self.stop_event.clear()
        
        # Create and start decode thread
        self.decode_thread = threading.Thread(target=self._decode_worker, daemon=True)
        self.decode_thread.start()
        print("Decode thread started")
        
    def stop(self):
        """Stop the decode thread"""
        if not self.running:
            print("Decoder is not running")
            return
            
        print("Stopping decoder...")
        self.running = False
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.decode_thread and self.decode_thread.is_alive():
            self.decode_thread.join(timeout=5)
            
        print("Decoder stopped")
        
    def push_frame(self, frame_type, frame_raw_data):
        """
        Push raw frame data to decode queue
        
        Args:
            frame_type (str): Frame type ('I', 'P', etc.)
            frame_raw_data (bytes): Raw H.264/H.265 frame data
        """
        if not self.running:
            print("Warning: Decoder not running, frame dropped")
            return
        
        if frame_raw_data is None or len(frame_raw_data) == 0:
            print("Warning: Invalid frame data, skipping")
            return
        
        try:
            # Create frame info tuple
            frame_info = (frame_type, frame_raw_data)
            self.frame_queue.put(frame_info, timeout=0.1)
        except queue.Full:
            print("Warning: Decode queue full, dropping frame")
            
    def _decode_worker(self):
        """Worker thread for decoding frames"""
        print("Decode worker started")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Get frame data from queue with timeout
                frame_info = self.frame_queue.get(timeout=0.01)
                frame_type, frame_raw_data = frame_info
                
                # Decode the frame
                try:
                    if self.codec and self.running:
                        packets = self.codec.parse(frame_raw_data)
                        for packet in packets:
                            frames = self.codec.decode(packet)
                            for frame in frames:
                                # Emit decoded frame
                                if frame is not None:
                                    self.frame_decoded.emit(frame)
                            
                except Exception as e:
                    print(f"Decode error: {e}")
                    
            except queue.Empty:
                # No data in queue, continue
                continue
            except Exception as e:
                print(f"Decode worker error: {e}")
                
        print("Decode worker stopped")

class OverlayLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # Mouse events pass through
        self.setAttribute(Qt.WA_TranslucentBackground)  # Set transparent background
        self.video_meta = ""
        self.fps = 0
        self.smoothed_fps = 0
        self.frame_times = []  # For calculating frame rate
        self.bitrate = 0
        self.smoothed_bitrate = 0
        self.data_times = []  # For calculating bitrate
        self.data_sizes = []  # For calculating bitrate
        self.alpha = 0.1  # Smoothing factor (0-1), smaller means smoother
        self.setStyleSheet("QLabel { background-color: transparent; color: white; }")  # Set transparent background, white text color

    def set_metadata(self, width, height, frame_rate, encoder_name):
        # Smart frame rate formatting
        if frame_rate == int(frame_rate):
            # Integer frame rate, display as integer
            fps_str = f"{int(frame_rate)}fps"
        else:
            # Float frame rate, display up to 2 decimal places
            fps_str = f"{frame_rate:.2f}fps"
        
        self.video_meta = f"{width}x{height}@{fps_str}, {encoder_name}"
        self.update()

    def update_fps(self):
        current_time = time.time()
        self.frame_times.append(current_time)
        
        # Only keep frame times from the last 5 seconds
        while self.frame_times and current_time - self.frame_times[0] > 5.0:
            self.frame_times.pop(0)
        
        # Calculate frame rate
        if len(self.frame_times) > 1:
            # Calculate actual time interval
            time_duration = self.frame_times[-1] - self.frame_times[0]  # Last time minus first time
            frame_count = len(self.frame_times)
            
            if time_duration > 0:
                self.fps = frame_count / time_duration
            else:
                self.fps = 0
        else:
            self.fps = 0
        
        # Use exponential smoothing
        if self.smoothed_fps == 0:
            self.smoothed_fps = self.fps
        else:
            self.smoothed_fps = self.alpha * self.fps + (1 - self.alpha) * self.smoothed_fps
        
        self.update()

    def update_bitrate(self, data_size):
        current_time = time.time()
        self.data_times.append(current_time)
        self.data_sizes.append(data_size)
        
        # Only keep data from the last 5 seconds
        while self.data_times and current_time - self.data_times[0] > 5.0:
            self.data_times.pop(0)
            self.data_sizes.pop(0)
        
        # Calculate bitrate (bits per second)
        if len(self.data_times) > 1:
            # Calculate actual time interval
            time_duration = self.data_times[-1] - self.data_times[0]  # Last time minus first time
            total_bits = sum(self.data_sizes) * 8  # Convert to bits
            
            if time_duration > 0:
                self.bitrate = total_bits / time_duration / 1000000  # Convert to Mbps
            else:
                self.bitrate = 0
        else:
            self.bitrate = 0
        
        # Use exponential smoothing
        if self.smoothed_bitrate == 0:
            self.smoothed_bitrate = self.bitrate
        else:
            self.smoothed_bitrate = self.alpha * self.bitrate + (1 - self.alpha) * self.smoothed_bitrate
        
        self.update()

    def format_bitrate(self):
        if self.smoothed_bitrate >= 1000:
            return f"{self.smoothed_bitrate/1000:.1f}Gb/s"
        else:
            return f"{self.smoothed_bitrate:.1f}Mb/s"

    def paintEvent(self, event):
        # Don't paint anything if there's no content
        if self.video_meta == "" or self.smoothed_fps == 0 or self.smoothed_bitrate == 0:
            # Clear the background completely
            painter = QPainter(self)
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self.rect(), Qt.transparent)
            return
        
        # Don't call parent's paintEvent, completely custom drawing
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Set font
        font = QFont("Arial", 10)
        painter.setFont(font)
        
        # Calculate text
        meta_text = f"{self.video_meta}"
        
        # Smart frame rate formatting
        if self.smoothed_fps == int(self.smoothed_fps):
            # Integer frame rate, display as integer
            fps_str = f"{int(self.smoothed_fps)}p"
        else:
            # Float frame rate, display up to 2 decimal places
            fps_str = f"{self.smoothed_fps:.2f}p"
        
        real_fps_text = f"{fps_str}, {self.format_bitrate()}"
        
        # Calculate text position (top right corner)
        margin = 6
        
        # Draw shadow
        painter.setPen(QColor(0, 0, 0, 180))  # Semi-transparent black shadow
        # Draw IP address shadow
        painter.drawText(self.width() - margin - painter.fontMetrics().horizontalAdvance(meta_text) + 1, 
                        margin + 16 + 1, meta_text)  # Shadow offset 2 pixels
        # Draw resolution info shadow
        painter.drawText(self.width() - margin - painter.fontMetrics().horizontalAdvance(real_fps_text) + 1, 
                        margin + 32 + 1, real_fps_text)  # Shadow offset 2 pixels
        
        # Draw main text
        painter.setPen(QColor(255, 255, 255, 255))  # White main text
        # Draw IP address
        painter.drawText(self.width() - margin - painter.fontMetrics().horizontalAdvance(meta_text), 
                        margin + 16, meta_text)
        # Draw resolution info
        painter.drawText(self.width() - margin - painter.fontMetrics().horizontalAdvance(real_fps_text), 
                        margin + 32, real_fps_text)

    def clear(self):
        """Clear all overlay content and reset to initial state"""
        self.video_meta = ""
        self.fps = 0
        self.smoothed_fps = 0
        self.bitrate = 0
        self.smoothed_bitrate = 0
        self.frame_times.clear()
        self.data_times.clear()
        self.data_sizes.clear()
        
        # Force immediate repaint to clear overlay
        self.repaint()
        self.update()
        
class PreviewH26xWnd(QWidget):
    """
    Qt widget for displaying H.264/H.265 video streams
    Contains DecodeH26x object and display thread
    """
    
    # Signal for updating display from worker thread
    display_update_signal = Signal(object)  # QImage
    
    # Signal for stopping preview
    stop_preview_signal = Signal()
    
    def __init__(self, parent=None):
        """
        Initialize preview window
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Initialize UI
        self._init_ui()
        
        # Create decoder
        self.decoder = DecodeH26x()
        
        # Connect decoder signal to display slot
        self.decoder.frame_decoded.connect(self._on_frame_decoded)
        
        # Display thread and queue
        self.display_running = False
        self.display_thread = None
        self.display_queue = queue.Queue(maxsize=3)  # Limit to 3 frames
        
        # Current image for display
        self._current_image = None
        
        # Thread synchronization for overlay access
        self._overlay_lock = threading.RLock()
        
        # Connect display update signal to slot
        self.display_update_signal.connect(self._update_display)
        
        # Connect stop signal to slot
        self.stop_preview_signal.connect(self._handle_stop)
        
        # Display timer for UI updates
        # self.display_timer = QTimer()
        # self.display_timer.timeout.connect(self._update_display)
        # self.display_timer.start(16)  # ~60 FPS
        
    def _init_ui(self):
        """Initialize user interface"""
        # Set widget properties
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create video display label
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(320, 240)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet("QLabel { background-color: black; color: white; }")
        self.video_label.setText("Waiting for connect to camera and start stream...")
        layout.addWidget(self.video_label)
        
        # Create overlay
        self.overlay = OverlayLabel(self.video_label)
        self.overlay.setGeometry(0, 0, self.video_label.width(), self.video_label.height())
        self.overlay.raise_()  # Ensure overlay is on top
        self.overlay.clear()  # Ensure initial state is empty
        self.overlay.hide()
        
    def start(self, encoder_type='h264'):
        """Start preview (starts decoder and display thread)"""
        if self.display_running:
            print("Preview is already running")
            return
            
        # Start decoder
        self.decoder.start(encoder_type)
        
        # Start display thread
        self.display_running = True
        self.display_thread = threading.Thread(target=self._display_worker, daemon=True)
        self.display_thread.start()
        
        print("Preview started")
        
    def stop(self):
        """Stop preview (stops decoder and display thread)"""
        if not self.display_running:
            print("Preview is not running")
            return
            
        print("Stopping preview...")
        
        # Stop decoder
        self.decoder.stop()
        
        # Stop display thread
        self.display_running = False
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=5)
            
        # Clear current image first
        self._current_image = None
        
        # Emit signal to update UI in main thread
        self.stop_preview_signal.emit()
        
        print("Preview stopped")
        
    def push_frame(self, frame_type, frame_raw_data):
        """
        Push frame data to decoder
        
        Args:
            frame_type (str): Frame type ('I', 'P', etc.)
            frame_raw_data (bytes): Raw H.264/H.265 frame data
        """
        if self.decoder and self.display_running:
            self.decoder.push_frame(frame_type, frame_raw_data)
        
            # Update overlay with thread safety
            if self.overlay:
                with self._overlay_lock:
                    if self.overlay.isHidden:
                        self.overlay.show()
                    self.overlay.update_bitrate(len(frame_raw_data))
                    self.overlay.update_fps()
            
    def _on_frame_decoded(self, frame):
        """
        Handle decoded frame from decoder
        
        Args:
            frame: Decoded av.VideoFrame
        """
        if not self.display_running or frame is None:
            return
            
        try:
            # Add frame to display queue
            self.display_queue.put(frame, timeout=0.1)
        except queue.Full:
            # Queue full, drop frame
            print("Warning: Display queue full, dropping frame")
            
    def _display_worker(self):
        """Worker thread for converting frames to displayable format"""
        print("Display worker started")
        
        while self.display_running:
            try:
                # Get frame from queue, maybe get a none frame
                frame = self.display_queue.get(timeout=0.01)
                if frame is None:
                    print("Warning: display queue is empty, skipping once...")
                    continue
                
                # Convert frame to RGB24 format
                try:
                    rgb_frame = frame.to_ndarray(format='rgb24')
                    
                    if rgb_frame is not None:
                        # Create QImage
                        height, width, channel = rgb_frame.shape
                        bytes_per_line = 3 * width
                        q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
                        
                        # Check if QImage is valid
                        if not q_image.isNull():
                            # Emit signal to update display in main thread
                            # Let main thread handle scaling with current video_label size
                            self.display_update_signal.emit(q_image)
                        
                except Exception as e:
                    print(f"Frame conversion error: {e}")
                    
            except queue.Empty:
                # No frame in queue, continue
                continue
            except Exception as e:
                print(f"Display worker error: {e}")
                
        print("Display worker stopped")
        
    def _update_display(self, q_image):
        """Update display with current frame (called by signal in main thread)"""
        try:
            # Don't update if preview is not running or if image is None
            if not self.display_running or q_image is None:
                return
                
            # Store current image
            self._current_image = q_image
            
            # Create scaled pixmap using current video_label size
            if self.video_label and not q_image.isNull():
                scaled_pixmap = QPixmap.fromImage(q_image).scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                
                # Update video label
                if not scaled_pixmap.isNull():
                    self.video_label.setPixmap(scaled_pixmap)
                    
                    # Update overlay if it exists
                    if self.overlay:
                        # Calculate video frame position in window
                        x_offset = (self.video_label.width() - scaled_pixmap.width()) // 2
                        y_offset = (self.video_label.height() - scaled_pixmap.height()) // 2
                        
                        # Update overlay size and position
                        with self._overlay_lock:
                            self.overlay.setGeometry(x_offset, y_offset, scaled_pixmap.width(), scaled_pixmap.height())
                        
        except Exception as e:
            print(f"Display update error: {e}")
            
    def resizeEvent(self, event):
        """Handle widget resize"""
        super().resizeEvent(event)
        # Trigger display update on resize
        if self._current_image is not None:
            self._update_display(self._current_image)

    def _handle_stop(self):
        """Handle stop signal in main thread"""
        # Clear display and restore to initial state
        self.video_label.clear()  # Clear both pixmap and text
        
        # Force immediate update of video_label
        self.video_label.repaint()
        self.video_label.update()
        
        # Force processing of all pending events
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # Now set the text after clearing
        self.video_label.setText("Waiting for connect to camera and start stream...")
        
        # Force another update to ensure text is displayed
        self.video_label.repaint()
        self.video_label.update()
        
        # Force processing of all pending events again
        QApplication.processEvents()
        
        # Clear overlay content
        if self.overlay:
            with self._overlay_lock:
                self.overlay.clear()
                # Hide overlay so it doesn't block video_label text
                self.overlay.hide()
        
        # Force layout update
        self.update()
        self.repaint()
        
        # Final event processing
        QApplication.processEvents()

# Example usage
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create main window
    main_window = QMainWindow()
    main_window.setWindowTitle("H.26x Preview Test")
    main_window.resize(640, 480)
    
    # Create central widget
    central_widget = QWidget()
    main_window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    
    # Create preview widget
    preview = PreviewH26xWnd()
    layout.addWidget(preview)
    
    # Show window
    main_window.show()
    
    # Start preview
    preview.start()
    
    # Run application
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("Stopping preview...")
        preview.stop() 