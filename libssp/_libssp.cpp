#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>
#include <memory>
#include <string>
#include <functional>
#include <mutex>
#include <condition_variable>
#include <iostream>
#include <atomic>

// Include libssp header files
#include "imf/net/loop.h"
#include "imf/net/threadloop.h"
#include "imf/ssp/sspclient.h"

namespace py = pybind11;


// Global variables for storing Python callback functions
struct PythonCallbacks {
    py::function on_h264_data;
    py::function on_audio_data;
    py::function on_meta;
    py::function on_disconnected;
    py::function on_connected;
    py::function on_exception;
    py::function on_recv_buffer_full;
};

// Python c++ extension wrapper for imf::SspClient class from zcam c++ libssp library
class PySspClient {
public:
    PySspClient(const std::string& ip, size_t bufSize, unsigned short port = 9999, uint32_t streamStyle = imf::STREAM_DEFAULT)
        : thread_loop_(nullptr), client_(nullptr), client_running_(false), thread_running_(false), 
          ip_(ip), bufSize_(bufSize), port_(port), streamStyle_(streamStyle), isHlg_(false), capability_(0),
          threadLoop_executed_(false), debug_print_(true)
    {
        // check stream style, if invalid, use STREAM_DEFAULT instead
        if (streamStyle_ != imf::STREAM_DEFAULT && streamStyle_ != imf::STREAM_MAIN && streamStyle_ != imf::STREAM_SEC) {
            _debug_print("Invalid stream style: " + std::to_string(streamStyle) + ", use STREAM_DEFAULT instead");
            streamStyle_ = imf::STREAM_DEFAULT;
        }

        // get stream style string
        auto _getStreamStyleString = [](uint32_t style) -> std::string 
        {
            switch (style) 
            {
                case imf::STREAM_DEFAULT:
                    return "STREAM_DEFAULT";
                case imf::STREAM_MAIN:
                    return "STREAM_MAIN";
                case imf::STREAM_SEC:
                    return "STREAM_SEC";
                default:
                    return "STREAM_UNKNOWN";
            }
        };

        // print input parametersdebug message
        _debug_print("Initializing PySspClient with IP: " + ip_ + ", port: " + std::to_string(port_));
        _debug_print("bufSize: " + std::to_string(bufSize_) + ", streamStyle: " + _getStreamStyleString(streamStyle_));

        // Create thread loop and set callback functions
        _debug_print("Creating thread loop...");
        thread_loop_ = std::make_unique<imf::ThreadLoop>([this](imf::Loop* loop) {
            _debug_print("Thread loop started");

            _debug_print("  Creating imf::SspClient in thread loop thread");
            
            // Create SspClient in thread loop
            client_ = std::make_unique<imf::SspClient>(ip_, loop, bufSize_, port_, streamStyle_);

            // Initialize client
            _debug_print("  Initializing imf::SspClient");
            client_->init();
            
            // Set a flag to indicate thread_loop PreLoopCallback execution is completed
            {
                std::lock_guard<std::mutex> lock(threadLoop_mutex_);
                threadLoop_executed_ = true;
            }

            threadLoop_cv_.notify_one();
        });

        _debug_print("Thread loop created");
    }

    void _setCallbacks() {
        if (!client_) {
            _debug_print("Warning: _setCallbacks called but imf::SspClient is null");
            return;
        }

        _debug_print("imf::SspClient set callbacks...");

        // Set callback functions
        if (callbacks_.on_h264_data) {
            _debug_print("  imf::SspClient set on_h264_data callback");
            client_->setOnH264DataCallback([this](imf::SspH264Data* h264) {
                // Create Python dictionary to store H264 data
                py::gil_scoped_acquire acquire;
                py::dict data;
                data["data"] = py::bytes(reinterpret_cast<char*>(h264->data), h264->len);
                data["len"] = h264->len;
                data["pts"] = h264->pts;
                data["ntp_timestamp"] = h264->ntp_timestamp;
                data["frm_no"] = h264->frm_no;
                data["type"] = h264->type;
                
                // Call Python callback function
                callbacks_.on_h264_data(data);
            });
        }
        
        if (callbacks_.on_audio_data) {
            _debug_print("  imf::SspClient set on_audio_data callback");
            client_->setOnAudioDataCallback([this](imf::SspAudioData* audio) {
                py::gil_scoped_acquire acquire;
                py::dict data;
                data["data"] = py::bytes(reinterpret_cast<char*>(audio->data), audio->len);
                data["len"] = audio->len;
                data["pts"] = audio->pts;
                data["ntp_timestamp"] = audio->ntp_timestamp;
                
                callbacks_.on_audio_data(data);
            });
        }
        
        if (callbacks_.on_meta) {
            _debug_print("  imf::SspClient set on_meta callback");
            client_->setOnMetaCallback([this](imf::SspVideoMeta* v, imf::SspAudioMeta* a, imf::SspMeta* m) {
                py::gil_scoped_acquire acquire;
                
                py::dict video_meta;
                video_meta["width"] = v->width;
                video_meta["height"] = v->height;
                video_meta["timescale"] = v->timescale;
                video_meta["unit"] = v->unit;
                video_meta["gop"] = v->gop;
                video_meta["encoder"] = v->encoder;
                
                py::dict audio_meta;
                audio_meta["timescale"] = a->timescale;
                audio_meta["unit"] = a->unit;
                audio_meta["sample_rate"] = a->sample_rate;
                audio_meta["sample_size"] = a->sample_size;
                audio_meta["channel"] = a->channel;
                audio_meta["bitrate"] = a->bitrate;
                audio_meta["encoder"] = a->encoder;
                
                py::dict meta;
                meta["pts_is_wall_clock"] = m->pts_is_wall_clock;
                
                callbacks_.on_meta(video_meta, audio_meta, meta);
            });
        }
        
        if (callbacks_.on_disconnected) {
            _debug_print("  imf::SspClient set on_disconnected callback");
            client_->setOnDisconnectedCallback([this]() {
                py::gil_scoped_acquire acquire;
                callbacks_.on_disconnected();
            });
        }
            
        if (callbacks_.on_connected) {
            _debug_print("  imf::SspClient set on_connected callback");
            client_->setOnConnectionConnectedCallback([this]() {
                py::gil_scoped_acquire acquire;
                callbacks_.on_connected();
            });
        }
        
        if (callbacks_.on_exception) {
            _debug_print("  imf::SspClient set on_exception callback");
            client_->setOnExceptionCallback([this](int code, const char* description) {
                py::gil_scoped_acquire acquire;
                callbacks_.on_exception(code, description);
            });
        }
        
        if (callbacks_.on_recv_buffer_full) {
            _debug_print("  imf::SspClient set on_recv_buffer_full callback");
            client_->setOnRecvBufferFullCallback([this]() {
                py::gil_scoped_acquire acquire;
                callbacks_.on_recv_buffer_full();
            });
        }
    };
    
    void _waitClientInited() {
        _debug_print("  Waiting for imf::SspClient has been created and initialized...");
        std::unique_lock<std::mutex> lock(threadLoop_mutex_);
        if (threadLoop_cv_.wait_for(lock, std::chrono::seconds(30), [this] { return threadLoop_executed_; })) {
            _debug_print("  imf::SspClient has been created and initialized");
        } else {
            _debug_print("  Timeout (30 sec) waiting for imf::SspClient to be created and initialized...");
        }
    }

    // add debug print function for trace debug message
    void _debug_print(const std::string& message) {
        //use stderr to avoid blocking Python main thread
        //py::gil_scoped_acquire acquire;
        //py::print("[DEBUG]", message);
        if (debug_print_) {
            std::cerr << "[PySspClient DEBUG] " << message << std::endl;
        }
    }

    ~PySspClient() {
        _debug_print("~PySspClient enter");

        // stop imf::SspClient it is running
        stop();

        // stop thread loop if it is running
        if (thread_loop_ && thread_running_.load()) {
            _debug_print("  ~PySspClient stopping thread loop...");
            thread_loop_->stop();
            thread_running_.store(false);
        }

        // release imf::SspClient if it is not null
        if (client_) {
            _debug_print("  ~PySspClient release imf::SspClient");
            client_.reset();
        }

        // release thread loop if it is not null
        if (thread_loop_) {
            _debug_print("  ~PySspClient release thread loop");
            thread_loop_.reset();
        }

        _debug_print("~PySspClient leave");
    }
    
    void start() {
        if (!thread_loop_) {
            _debug_print("Warning: Cannot start, thread_loop is null");
            return;
        }

        _debug_print("PySspClient::start() enter");

        if (thread_loop_ && !thread_running_.load()) {
            _debug_print("  Detect thread_loop is not running, starting it...");
            thread_loop_->start();
            thread_running_.store(true);
        }

        // wait for thread_loop has completed loop callback execution
        _waitClientInited();

        // client start
        if (client_ && !client_running_.load()) {
            _debug_print("  imf::SspClient not started, prepare to start...");
            
            // Set HLG mode
            _debug_print("  imf::SspClient set HLG mode = " + std::to_string(isHlg_));
            client_->setIsHlg(isHlg_);
            
            // Set capability
            _debug_print("  imf::SspClient set capability = " + std::to_string(capability_));
            if (capability_ != 0) {
                client_->setCapability(capability_);
            }

            // Set all callbacks
            _debug_print("  imf::SspClient set callbacks");
            _setCallbacks();

            // start imf::SspClient
            _debug_print("  imf::SspClient to start...");
            {
                py::gil_scoped_release release;
                client_->start();
                client_running_.store(true);
            }

            _debug_print("  imf::SspClient started successfully");
        }
        else {
            if (!client_) {
                _debug_print("  imf::SspClient client is null, failed to start");
            }
            else {
                _debug_print("  imf::SspClient is already running");
            }
        }

        _debug_print("PySspClient::start() leave");
    }
    
    void stop() {
        _debug_print("PySspClient::stop() enter");

        if (client_ && client_running_.load()) {
            _debug_print("  Stopping imf::SspClient if it is running...");
            
            // release GIL before calling client_->stop(), this is very important, 
            // otherwise the Python main thread will be blocked and the program will hang
            // because the client_->stop() will call a python callback - on_disconnected()
            // which will aquire the GIL
            {
                py::gil_scoped_release release;
                client_->stop();
                client_running_.store(false);
            }
            
            _debug_print("  imf::SspClient stopped");
        }

        _debug_print("PySspClient::stop() leave");
    }
    
    void set_on_h264_data_callback(py::function callback) {
        callbacks_.on_h264_data = callback;
    }
    
    void set_on_audio_data_callback(py::function callback) {
        callbacks_.on_audio_data = callback;
    }
    
    void set_on_meta_callback(py::function callback) {
        callbacks_.on_meta = callback;
    }
    
    void set_on_disconnected_callback(py::function callback) {
        callbacks_.on_disconnected = callback;
    }
    
    void set_on_connected_callback(py::function callback) {
        callbacks_.on_connected = callback;
    }
    
    void set_on_exception_callback(py::function callback) {
        callbacks_.on_exception = callback;
    }
    
    void set_on_recv_buffer_full_callback(py::function callback) {
        callbacks_.on_recv_buffer_full = callback;
    }

    void setIsHlg(bool isHlg) {
        isHlg_.store(isHlg);
    }

    void setCapability(uint32_t capability) {
        capability_.store(capability);
    }

    void setDebugPrint(bool debug_print) {
        debug_print_.store(debug_print);
    }

private:
    std::unique_ptr<imf::ThreadLoop> thread_loop_;
    std::unique_ptr<imf::SspClient> client_;
    PythonCallbacks callbacks_;
    std::string ip_;
    size_t bufSize_;
    unsigned short port_;
    uint32_t streamStyle_;
    std::atomic<bool> client_running_;
    std::atomic<bool> thread_running_;
    std::atomic<bool> isHlg_;
    std::atomic<uint32_t> capability_;

    // variables for waiting thread_loop callback function execution
    std::mutex threadLoop_mutex_;
    std::condition_variable threadLoop_cv_;
    bool threadLoop_executed_;

    // control debug print
    std::atomic<bool> debug_print_;
};

PYBIND11_MODULE(_libssp, m) {
    m.doc() = "Python bindings for libssp";
    
    // Define constants
    m.attr("STREAM_DEFAULT") = py::int_(static_cast<int>(imf::STREAM_DEFAULT));
    m.attr("STREAM_MAIN") = py::int_(static_cast<int>(imf::STREAM_MAIN));
    m.attr("STREAM_SEC") = py::int_(static_cast<int>(imf::STREAM_SEC));
    
    m.attr("VIDEO_ENCODER_UNKNOWN") = py::int_(VIDEO_ENCODER_UNKNOWN);
    m.attr("VIDEO_ENCODER_H264") = py::int_(VIDEO_ENCODER_H264);
    m.attr("VIDEO_ENCODER_H265") = py::int_(VIDEO_ENCODER_H265);
    
    m.attr("AUDIO_ENCODER_UNKNOWN") = py::int_(AUDIO_ENCODER_UNKNOWN);
    m.attr("AUDIO_ENCODER_AAC") = py::int_(AUDIO_ENCODER_AAC);
    m.attr("AUDIO_ENCODER_PCM") = py::int_(AUDIO_ENCODER_PCM);
    
    // Define error codes
    m.attr("ERROR_SSP_PROTOCOL_VERSION_GT_SERVER") = py::int_(ERROR_SSP_PROTOCOL_VERSION_GT_SERVER);
    m.attr("ERROR_SSP_PROTOCOL_VERSION_LT_SERVER") = py::int_(ERROR_SSP_PROTOCOL_VERSION_LT_SERVER);
    m.attr("ERROR_SSP_CONNECTION_FAILED") = py::int_(ERROR_SSP_CONNECTION_FAILED);
    m.attr("ERROR_SSP_CONNECTION_EXIST") = py::int_(ERROR_SSP_CONNECTION_EXIST);

    // Define capability flags
    m.attr("SSP_CAPABILITY_IGNORE_HEARTBEAT_DISABLE_ENC") = py::int_(SSP_CAPABILITY_IGNORE_HEARTBEAT_DISABLE_ENC);
    
    // Define SspClient class
    py::class_<PySspClient>(m, "SspClient")
        .def(py::init<const std::string&, size_t, unsigned short, uint32_t>(),
             py::arg("ip"), py::arg("bufSize"), py::arg("port") = 9999, py::arg("streamStyle") = static_cast<uint32_t>(imf::STREAM_DEFAULT))
        .def("start", &PySspClient::start)
        .def("stop", &PySspClient::stop)
        .def("setIsHlg", &PySspClient::setIsHlg)
        .def("setCapability", &PySspClient::setCapability)
        .def("setDebugPrint", &PySspClient::setDebugPrint)
        .def("set_on_h264_data_callback", &PySspClient::set_on_h264_data_callback)
        .def("set_on_audio_data_callback", &PySspClient::set_on_audio_data_callback)
        .def("set_on_meta_callback", &PySspClient::set_on_meta_callback)
        .def("set_on_disconnected_callback", &PySspClient::set_on_disconnected_callback)
        .def("set_on_connected_callback", &PySspClient::set_on_connected_callback)
        .def("set_on_exception_callback", &PySspClient::set_on_exception_callback)
        .def("set_on_recv_buffer_full_callback", &PySspClient::set_on_recv_buffer_full_callback);
}