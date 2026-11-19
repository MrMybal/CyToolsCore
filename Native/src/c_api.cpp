#include <cytools/communication.hpp>
using namespace cytools;
namespace {
thread_local std::string returned;
template<class F> const char* protect(F fn) noexcept {
    try{returned=Json{{"result",fn()}}.dump();}
    catch(const cymcp::Error& e){returned=Json{{"error",{{"code",e.code},{"message",e.what()}}}}.dump();}
    catch(const Json::exception&){returned=R"({"error":{"code":"InvalidParameters","message":"Invalid native binding request"}})";}
    catch(const std::invalid_argument&){returned=R"({"error":{"code":"InvalidParameters","message":"Invalid command argument value"}})";}
    catch(const std::exception&){returned=R"({"error":{"code":"InternalError","message":"Native communication request failed"}})";}
    return returned.c_str();
}
}
extern "C" {
const char* cytools_native_info(){static const auto info=Json{{"abi",1},{"version","0.11.0"},{"cymcp",cymcp::version}}.dump();return info.c_str();}
void* cytools_communication_create(cytools_callback callback,void* user){
    if(!callback)return nullptr;
    try{return new Communication([callback,user](const Json& request){
        const auto text=request.dump();const char* reply=callback(text.c_str(),user);
        if(!reply)throw cymcp::Error("HostError","Host callback did not return JSON");
        return cymcp::parse_json(reply,cymcp::provider_message_limit);
    });}catch(...){return nullptr;}
}
const char* cytools_communication_call(void* handle,const char* text){return protect([&]()->Json{
    if(!handle || !text)throw cymcp::Error("InvalidParameters","Native host and JSON request required");
    auto& host=*static_cast<Communication*>(handle);auto request=cymcp::parse_json(text,cymcp::provider_message_limit);
    const auto command=request.at("command").get<std::string>();
    if(command=="run_cli")return host.run_cli(request.at("argv").get<std::vector<std::string>>());
    if(command=="start_http")return host.start_http(request.value("port",0));
    if(command=="stop_http"){host.stop_http();return nullptr;}
    if(command=="serve_mcp"){host.serve_mcp();return nullptr;}
    if(command=="dispatch")return host.dispatch(request.at("request"));
    if(command=="sdk")return host.sdk(request.at("request"));
    throw cymcp::Error("UnknownMethod","Unknown native binding command");
});}
void cytools_communication_destroy(void* handle){delete static_cast<Communication*>(handle);}
const char* cytools_http_call(const char* text){return protect([&]{
    auto request=cymcp::parse_json(text,cymcp::provider_message_limit);
    return Communication::http_call(request.at("url"),request.at("token"),request.at("request"),request.value("timeoutMs",30000));
});}
}
