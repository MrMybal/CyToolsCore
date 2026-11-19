#pragma once
#include <cymcp/mcp.hpp>
#include <functional>
#include <memory>
#include <string>
#include <vector>
#include "c_api.h"
namespace cytools {
using Json = cymcp::Json;
// A host implements its Tool runtime; all public communication belongs to CyMCPSDK.
// The trusted callback envelope carries identity separately from business parameters.
using HostCallback = std::function<Json(const Json&)>;
class CYTOOLS_API Communication {
    struct Impl;
    std::unique_ptr<Impl> impl_;
public:
    explicit Communication(HostCallback);
    ~Communication();
    Communication(const Communication&) = delete;
    Communication& operator=(const Communication&) = delete;
    Json dispatch(const Json&, const std::string& principal = "");
    int start_http(int port = 0);
    void stop_http();
    void serve_mcp();
    int run_cli(const std::vector<std::string>&);
    Json sdk(const Json&, const std::string& principal = "");
    static Json http_call(const std::string& url, const std::string& token,
                          const Json&, int timeout_ms = 30000);
};
}
