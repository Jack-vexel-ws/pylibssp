import threading
import time
from . import _libssp

# define SspClient class for _libssp.SspClient class，provide Pythonic interfaces
class SspClient:
    """
    Python wrapper for the libssp SspClient.
    This class provides a more Pythonic interface to the libssp library.
    """
    def __init__(self, ip, buf_size, port=9999, stream_style=_libssp.STREAM_DEFAULT):
        """
        Initialize a new SspClient.
        
        Args:
            ip (str): The IP address of the SSP server.
            buf_size (int): The size of the receive buffer.
            port (int, optional): The port of the SSP server. Defaults to 9999.
            stream_style (int, optional): The stream style. Defaults to STREAM_DEFAULT.
        """
        if stream_style is None:
            stream_style = _libssp.STREAM_DEFAULT

        self._client = _libssp.SspClient(ip, buf_size, port, stream_style)
        self._running = False
        
        # Initialize callback handlers
        self._on_h264_data = None
        self._on_audio_data = None
        self._on_meta = None
        self._on_disconnected = None
        self._on_connected = None
        self._on_exception = None
        self._on_recv_buffer_full = None
    
    def start(self):
        """
        Start the SSP client.
        """
        self._running = True
        self._client.start()
        return self
    
    def stop(self):
        """
        Stop the SSP client.
        """
        if self._running:
            self._running = False
            self._client.stop()
    
    def __enter__(self):
        """
        Context manager entry point.
        """
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.
        """
        self.stop()
    
    @property
    def on_h264_data(self):
        """
        Get the H264 data callback.
        """
        return self._on_h264_data
    
    @on_h264_data.setter
    def on_h264_data(self, callback):
        """
        Set the H264 data callback.
        
        Args:
            callback (callable): A function that takes a dictionary with the following keys:
                - data (bytes): The H264 data.
                - len (int): The length of the data.
                - pts (int): The presentation timestamp.
                - ntp_timestamp (int): The NTP timestamp.
                - frm_no (int): The frame number.
                - type (int): The frame type (I or P).
        """
        self._on_h264_data = callback
        self._client.set_on_h264_data_callback(callback)
    
    @property
    def on_audio_data(self):
        """
        Get the audio data callback.
        """
        return self._on_audio_data
    
    @on_audio_data.setter
    def on_audio_data(self, callback):
        """
        Set the audio data callback.
        
        Args:
            callback (callable): A function that takes a dictionary with the following keys:
                - data (bytes): The audio data.
                - len (int): The length of the data.
                - pts (int): The presentation timestamp.
                - ntp_timestamp (int): The NTP timestamp.
        """
        self._on_audio_data = callback
        self._client.set_on_audio_data_callback(callback)
    
    @property
    def on_meta(self):
        """
        Get the metadata callback.
        """
        return self._on_meta
    
    @on_meta.setter
    def on_meta(self, callback):
        """
        Set the metadata callback.
        
        Args:
            callback (callable): A function that takes three dictionaries:
                - video_meta: A dictionary with video metadata.
                - audio_meta: A dictionary with audio metadata.
                - meta: A dictionary with general metadata.
        """
        self._on_meta = callback
        self._client.set_on_meta_callback(callback)
    
    @property
    def on_disconnected(self):
        """
        Get the disconnected callback.
        """
        return self._on_disconnected
    
    @on_disconnected.setter
    def on_disconnected(self, callback):
        """
        Set the disconnected callback.
        
        Args:
            callback (callable): A function that takes no arguments.
        """
        self._on_disconnected = callback
        self._client.set_on_disconnected_callback(callback)
    
    @property
    def on_connected(self):
        """
        Get the connected callback.
        """
        return self._on_connected
    
    @on_connected.setter
    def on_connected(self, callback):
        """
        Set the connected callback.
        
        Args:
            callback (callable): A function that takes no arguments.
        """
        self._on_connected = callback
        self._client.set_on_connected_callback(callback)
    
    @property
    def on_exception(self):
        """
        Get the exception callback.
        """
        return self._on_exception
    
    @on_exception.setter
    def on_exception(self, callback):
        """
        Set the exception callback.
        
        Args:
            callback (callable): A function that takes two arguments:
                - code (int): The error code.
                - description (str): The error description.
        """
        self._on_exception = callback
        self._client.set_on_exception_callback(callback)
    
    @property
    def on_recv_buffer_full(self):
        """
        Get the receive buffer full callback.
        """
        return self._on_recv_buffer_full
    
    @on_recv_buffer_full.setter
    def on_recv_buffer_full(self, callback):
        """
        Set the receive buffer full callback.
        
        Args:
            callback (callable): A function that takes no arguments.
        """
        self._on_recv_buffer_full = callback
        self._client.set_on_recv_buffer_full_callback(callback)

# Export constants
STREAM_DEFAULT = _libssp.STREAM_DEFAULT
STREAM_MAIN = _libssp.STREAM_MAIN
STREAM_SEC = _libssp.STREAM_SEC

VIDEO_ENCODER_UNKNOWN = _libssp.VIDEO_ENCODER_UNKNOWN
VIDEO_ENCODER_H264 = _libssp.VIDEO_ENCODER_H264
VIDEO_ENCODER_H265 = _libssp.VIDEO_ENCODER_H265

AUDIO_ENCODER_UNKNOWN = _libssp.AUDIO_ENCODER_UNKNOWN
AUDIO_ENCODER_AAC = _libssp.AUDIO_ENCODER_AAC
AUDIO_ENCODER_PCM = _libssp.AUDIO_ENCODER_PCM

ERROR_SSP_PROTOCOL_VERSION_GT_SERVER = _libssp.ERROR_SSP_PROTOCOL_VERSION_GT_SERVER
ERROR_SSP_PROTOCOL_VERSION_LT_SERVER = _libssp.ERROR_SSP_PROTOCOL_VERSION_LT_SERVER
ERROR_SSP_CONNECTION_FAILED = _libssp.ERROR_SSP_CONNECTION_FAILED
ERROR_SSP_CONNECTION_EXIST = _libssp.ERROR_SSP_CONNECTION_EXIST