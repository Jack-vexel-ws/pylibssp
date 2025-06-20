#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dumph26x class for saving H.264 video stream data to file
Created by Cursor AI, modified by Jack-vexel.
"""

import time
import threading
import queue
import os


class Dumph26x:
    """
    A class for dumping H.264 video stream data to file using a separate thread
    """
    
    def __init__(self, file_path):
        """
        Initialize Dumph26x with file path
        
        Args:
            file_path (str): Path to the output .h264 file
        """
        self.file_path = file_path
        self.frame_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.dump_thread = None
        self.file_handle = None
        self.is_running = False
        
    def start(self):
        """
        Start the dump thread and begin writing to file
        """
        if self.is_running:
            print(f"Dumph26x is already running")
            return
            
        # Create and start the dump thread
        self.dump_thread = threading.Thread(target=self._dump_worker, daemon=True)
        self.dump_thread.start()
        self.is_running = True
        print(f"Dumph26x started, saving to: {self.file_path}")
        
    def stop(self):
        """
        Stop the dump thread and close the file
        """
        if not self.is_running:
            print(f"Dumph26x is not running")
            return
            
        print(f"Stopping Dumph26x...")
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.dump_thread and self.dump_thread.is_alive():
            self.dump_thread.join(timeout=10)
            
        self.is_running = False
        print(f"Dumph26x stopped")
        
    def write_frame(self, frame_data):
        """
        Add frame data to the queue for writing
        
        Args:
            frame_data (bytes): H.264 frame data to write
        """
        if self.is_running:
            try:
                self.frame_queue.put(frame_data, timeout=10.0)
            except queue.Full:
                print(f"Warning: Frame queue is full, dropping frame")
        else:
            print(f"Warning: Dumph26x is not running, frame dropped")
            
    def _dump_worker(self):
        """
        Worker thread function that writes frames to file
        """
        try:
            # Open the file for writing
            self.file_handle = open(self.file_path, 'wb')
            print(f"Opened H.264/H.265 file for writing: {self.file_path}")
            print("\n")
            
            frames_written = 0
            
            while not self.stop_event.is_set():
                try:
                    # Try to get frame data from queue with timeout
                    frame_data = self.frame_queue.get(timeout=0.1)
                    frames_written += 1
                    
                    # Write frame data to file
                    self.file_handle.write(frame_data)
                    self.file_handle.flush()
                    
                    # Print progress every 100 frames
                    if frames_written % 100 == 0:
                        print(f"\nDumph26x: Written {frames_written} frames")
                        
                except queue.Empty:
                    # No data in queue, continue waiting
                    continue
                    
            # Write remaining frames in queue
            remaining_frames = 0
            while not self.frame_queue.empty():
                try:
                    frame_data = self.frame_queue.get_nowait()
                    self.file_handle.write(frame_data)
                    remaining_frames += 1
                except queue.Empty:
                    break
                    
            if remaining_frames > 0:
                print(f"Dumph26x: Written {remaining_frames} remaining frames")
                
            print(f"Dumph26x: Total frames written: {frames_written + remaining_frames}")
            
        except Exception as e:
            print(f"Dumph26x error: {e}")
        finally:
            # Close the file
            if self.file_handle:
                self.file_handle.close()
                self.file_handle = None
                print(f"Closed H.264/H.265 file: {self.file_path}")


# Example usage and test code
if __name__ == "__main__":
    import time
    
    # Test the Dumph26x class
    dump_file_name = os.path.join(os.path.dirname(__file__), "dump", "test_output.h264")
    if not os.path.exists(os.path.dirname(dump_file_name)):
        os.makedirs(os.path.dirname(dump_file_name))   
    if os.path.exists(dump_file_name):
        os.remove(dump_file_name)
    
    dump = Dumph26x(dump_file_name)
    
    # Start dumping
    dump.start()
    
    # Simulate some frame data
    test_frames = [
        b'\x00\x00\x00\x01\x67\x42\x00\x1E\x9A\x74\x02\x80\x2D\xC8\x00\x00\x03\x00\x02\x00\x00\x03\x00\x65\x08',
        b'\x00\x00\x00\x01\x68\xCE\x3C\x80',
        b'\x00\x00\x00\x01\x65\x88\x80\x14\x00\x00\x03\x00\x02\x00\x00\x03\x00\x65\x08'
    ]
    
    # Write some test frames
    for i, frame in enumerate(test_frames):
        dump.write_frame(frame)
        time.sleep(0.1)
        print(f"Wrote test frame {i+1}")
    
    # Stop dumping
    time.sleep(1)
    dump.stop()
    
    print("Test completed")