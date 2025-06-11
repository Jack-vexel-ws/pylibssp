#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>
#include <memory>
#include <string>
#include <functional>

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

// Wrapper for SspClient class
class PySspClient {
public:
    PySspClient(const std::string& ip, size_t bufSize, unsigned short port = 9999, uint32_t streamStyle = imf::STREAM_DEFAULT)
        : thread_loop_(nullptr), client_(nullptr), ip_(ip), bufSize_(bufSize), port_(port), streamStyle_(streamStyle) {
        // Create thread loop
        thread_loop_ = std::make_unique<imf::ThreadLoop>([this](imf::Loop* loop) {
            // Create SspClient in thread loop
            client_ = std::make_unique<imf::SspClient>(ip_, loop, bufSize_, port_, streamStyle_);
            // Initialize client
            client_->init();
            // Set all callbacks
            updateCallbacks();
            // client start
            client_->start();
        });
    }

    void updateCallbacks() {
        if (!client_) return;

        // Set callback functions
        if (callbacks_.on_h264_data) {
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
            client_->setOnDisconnectedCallback([this]() {
                py::gil_scoped_acquire acquire;
                callbacks_.on_disconnected();
            });
        }
            
        if (callbacks_.on_connected) {
            client_->setOnConnectionConnectedCallback([this]() {
                py::gil_scoped_acquire acquire;
                callbacks_.on_connected();
            });
        }
        
        if (callbacks_.on_exception) {
            client_->setOnExceptionCallback([this](int code, const char* description) {
                py::gil_scoped_acquire acquire;
                callbacks_.on_exception(code, description);
            });
        }
        
        if (callbacks_.on_recv_buffer_full) {
            client_->setOnRecvBufferFullCallback([this]() {
                py::gil_scoped_acquire acquire;
                callbacks_.on_recv_buffer_full();
            });
        }
    };
    
    ~PySspClient() {
        stop();
    }
    
    void start() {
        if (thread_loop_) {
            thread_loop_->start();
            }
    }
    
    void stop() {
        if (client_) {
            client_->stop();
        }
        if (thread_loop_) {
            thread_loop_->stop();
        }
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

private:
    std::unique_ptr<imf::ThreadLoop> thread_loop_;
    std::unique_ptr<imf::SspClient> client_;
    PythonCallbacks callbacks_;
    std::string ip_;
    size_t bufSize_;
    unsigned short port_;
    uint32_t streamStyle_;
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
    
    // Define SspClient class
    py::class_<PySspClient>(m, "SspClient")
        .def(py::init<const std::string&, size_t, unsigned short, uint32_t>(),
             py::arg("ip"), py::arg("bufSize"), py::arg("port") = 9999, py::arg("streamStyle") = static_cast<uint32_t>(imf::STREAM_DEFAULT))
        .def("start", &PySspClient::start)
        .def("stop", &PySspClient::stop)
        .def("set_on_h264_data_callback", &PySspClient::set_on_h264_data_callback)
        .def("set_on_audio_data_callback", &PySspClient::set_on_audio_data_callback)
        .def("set_on_meta_callback", &PySspClient::set_on_meta_callback)
        .def("set_on_disconnected_callback", &PySspClient::set_on_disconnected_callback)
        .def("set_on_connected_callback", &PySspClient::set_on_connected_callback)
        .def("set_on_exception_callback", &PySspClient::set_on_exception_callback)
        .def("set_on_recv_buffer_full_callback", &PySspClient::set_on_recv_buffer_full_callback);
}