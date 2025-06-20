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
from PySide6.QtGui import QImage, QPixmap


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
        
        # Frame queue for incoming raw data
        self.frame_queue = queue.Queue(maxsize=queue_size)
        
        # Initialize codec
        self._init_codec()
        
    def _init_codec(self):
        """Initialize H.264/H.265 decoder"""
        try:
            # Try to create H.264 decoder first
            self.codec = av.CodecContext.create('h264', 'r')
            print("Initialized H.264 decoder")
        except Exception as e:
            try:
                # Try H.265 decoder
                self.codec = av.CodecContext.create('hevc', 'r')
                print("Initialized H.265 decoder")
            except Exception as e2:
                print(f"Failed to initialize codec: {e2}")
                raise
        
        # Configure codec options
        self.codec.options.update({
            'threads': '1',
            'thread_type': 'slice'
        })
        
        # Open codec
        self.codec.open()
        
    def start(self):
        """Start the decode thread"""
        if self.running:
            print("Decoder is already running")
            return
            
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
                    packets = self.codec.parse(frame_raw_data)
                    for packet in packets:
                        frames = self.codec.decode(packet)
                        for frame in frames:
                            # Emit decoded frame
                            self.frame_decoded.emit(frame)
                            
                except Exception as e:
                    print(f"Decode error: {e}")
                    
            except queue.Empty:
                # No data in queue, continue
                continue
            except Exception as e:
                print(f"Decode worker error: {e}")
                
        print("Decode worker stopped")


class PreviewH26xWnd(QWidget):
    """
    Qt widget for displaying H.264/H.265 video streams
    Contains DecodeH26x object and display thread
    """
    
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
        self.video_label.setStyleSheet("QLabel { background-color: black; }")
        self.video_label.setText("Waiting for connect to camera and start stream...")
        layout.addWidget(self.video_label)
        
    def start(self):
        """Start preview (starts decoder and display thread)"""
        if self.display_running:
            print("Preview is already running")
            return
            
        # Start decoder
        self.decoder.start()
        
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
            
        # Clear display
        self.video_label.setText("Waiting for connect to camera and start stream...")
        
        self._current_image = None
        
        print("Preview stopped")
        
    def push_frame(self, frame_type, frame_raw_data):
        """
        Push frame data to decoder
        
        Args:
            frame_type (str): Frame type ('I', 'P', etc.)
            frame_raw_data (bytes): Raw H.264/H.265 frame data
        """
        self.decoder.push_frame(frame_type, frame_raw_data)
        
    def _on_frame_decoded(self, frame):
        """
        Handle decoded frame from decoder
        
        Args:
            frame: Decoded av.VideoFrame
        """
        if not self.display_running:
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
                # Get frame from queue
                frame = self.display_queue.get(timeout=0.01)
                
                # Convert frame to RGB24 format
                try:
                    rgb_frame = frame.to_ndarray(format='rgb24')
                    
                    # Create QImage
                    height, width, channel = rgb_frame.shape
                    bytes_per_line = 3 * width
                    q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
                    
                    # Store for display update
                    self._current_image = q_image
                    
                    # Update display
                    self._update_display()
                    
                except Exception as e:
                    print(f"Frame conversion error: {e}")
                    
            except queue.Empty:
                # No frame in queue, continue
                continue
            except Exception as e:
                print(f"Display worker error: {e}")
                
        print("Display worker stopped")
        
    def _update_display(self):
        """Update display with current frame (called by timer)"""
        if hasattr(self, '_current_image') and self._current_image is not None:
            # Scale image to fit label while maintaining aspect ratio
            scaled_pixmap = QPixmap.fromImage(self._current_image).scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)
            
    def resizeEvent(self, event):
        """Handle widget resize"""
        super().resizeEvent(event)
        # Trigger display update on resize
        if hasattr(self, '_current_image') and self._current_image is not None:
            self._update_display()


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