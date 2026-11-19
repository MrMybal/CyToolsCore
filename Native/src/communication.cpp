#include <cytools/communication.hpp>
#include <cymcp/http.hpp>
#include <csignal>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>

namespace cytools {
namespace {
using namespace cymcp;
Json object() { return Json::object(); }
Json error_value(const std::string& code, const std::string& message) {
    return {{"code",code},{"message",message},{"technicalDetails",nullptr},
            {"recoverable",false},{"suggestedAction",nullptr}};
}
Json read_json_file(const std::string& path) {
    std::ifstream in(std::filesystem::u8path(path), std::ios::binary);
    if (!in) throw Error("ConfigurationError", "Cannot open JSON parameters file");
    std::string text((std::istreambuf_iterator<char>(in)), {});
    if (text.starts_with("\xef\xbb\xbf")) text.erase(0,3);
    return parse_json(text, provider_message_limit);
}
Json envelope(Json spec, const std::string& field) {
    std::function<void(Json&)> visit = [&](Json& node) {
        if (node.is_object()) {
            node.erase("$id");
            for (auto& [key,value] : node.items()) {
                if ((key=="$ref" || key=="$dynamicRef") && value.is_string()) {
                    auto ref=value.get<std::string>();
                    if (ref=="#") value="#/properties/"+field;
                    else if (ref.starts_with("#/")) value="#/properties/"+field+"/"+ref.substr(2);
                } else visit(value);
            }
        } else if (node.is_array()) for (auto& child : node) visit(child);
    };
    visit(spec); return spec;
}
std::atomic_bool interrupted{false};
void on_interrupt(int) { interrupted.store(true); }
}
struct Communication::Impl {
    HostCallback callback;
    std::string principal, remote_url, remote_token;
    std::unique_ptr<LocalHttpServer> http;
    std::unique_ptr<Registry> registry;
    std::unique_ptr<McpServer> mcp;
    std::mutex registry_mutex;
    std::mutex tasks_mutex;
    struct Tasks { std::string current; std::set<std::string> owned; };
    using Scope = std::pair<std::string, std::string>;
    std::map<Scope,Tasks> tasks;
    explicit Impl(HostCallback cb) : callback(std::move(cb)) {
        if (!callback) throw Error("InvalidOptions","Tool host callback required");
    }
    Json host(Json request) {
        auto reply=remote_url.empty()?callback(request):Communication::http_call(
            remote_url,remote_token,{{"method","cytools.host"},{"request",request}});
        if (reply.contains("error")) {
            const auto& e=reply.at("error");
            throw Error(e.value("code","InternalError"), e.value("message","Host request failed"));
        }
        return reply.at("result");
    }
    void bootstrap(const std::string& data_dir=".cytools") {
        if (remote_url.empty() && principal.empty())
            principal=host({{"method","$bootstrap"},{"params",{{"dataDir",data_dir}}}}).at("principal").get<std::string>();
    }
    Json wire(const Json& request, const std::string& actor) {
        if (!remote_url.empty()) return Communication::http_call(remote_url,remote_token,request);
        return host({{"method","$request"},{"principal",actor.empty()?principal:actor},{"request",request}});
    }
    Json call(const std::string& method, Json params=object(), const std::string& actor="") {
        auto result=wire({{"protocolVersion","1.0"},{"id",0},{"method",method},{"params",params}},actor);
        if (result.contains("error")) {
            auto e=result.at("error");
            throw Error(e.value("code","InternalError"),e.value("message","Tool request failed"));
        }
        return result.at("result");
    }
    std::string actor(const CallContext& c) const {
        return c.principal=="local" ? principal : c.principal;
    }
    Scope scope(const CallContext& c) const {
        return {actor(c),c.transport_scope};
    }
    Json task_call(const std::string& method, Json args, const CallContext& c,
                   const std::string& operation="") {
        const auto identity=actor(c);
        const auto key=scope(c);
        // Task bookkeeping only. No handler or generation runs synchronously here.
        std::lock_guard lock(tasks_mutex);
        auto& task=tasks[key];
        auto new_task=[&] {
            auto result=call("CreateSession",{{"temporary",true}},identity);
            task.current=result.at("sessionId"); task.owned.insert(task.current);
        };
        if (method=="CreateSession") {
            args["temporary"]=true;
            auto result=call(method,args,identity); task.owned.insert(result.at("sessionId")); return result;
        }
        if (method=="SubmitJob" || method=="FinishTask" || method=="KeepTaskAlive" || method=="ImportFile") {
            if (!args.contains("sessionId")) {
                if (task.current.empty()) new_task();
                if (method=="SubmitJob") {
                    try { call("KeepTaskAlive",{{"sessionId",task.current}},identity); }
                    catch (const Error& e) { if(e.code!="AccessDenied") throw; new_task(); }
                }
                args["sessionId"]=task.current;
            }
            if (!task.owned.contains(args.at("sessionId").get<std::string>()))
                throw Error("AccessDenied","Task belongs to another connection");
        }
        if (!operation.empty()) args["operationId"]=operation;
        auto result=call(method,args,identity);
        if (method=="FinishTask" && args.at("sessionId")==task.current) task.current.clear();
        return result;
    }
    void clean_tasks() noexcept {
        for (auto& [key,task] : tasks) {
            const auto& identity=key.first;
            for (const auto& session : task.owned) try {
                call("FinishTask",{{"sessionId",session},{"cancelRunning",true}},identity);
            } catch (...) { /* Runtime retains pending cleanup until its worker actually stops. */ }
        }
        tasks.clear();
    }
    void create_registry() {
        std::lock_guard initialize(registry_mutex);
        if (registry) return;
        bootstrap();
        const auto descriptor=call("DescribeTool");
        auto schemas=host({{"method","$schemas"}});
        const auto controls=schemas.at("requests");
        auto validation=std::make_shared<SchemaValidation>();
        validation->check=[this](const Json& schema) { host({{"method","$check_schema"},{"schema",schema}}); };
        validation->validate=[this](const Json& value,const Json& schema) {
            host({{"method","$validate"},{"value",value},{"schema",schema}});
        };
        registry=std::make_unique<Registry>(Policy::allow_all());
        auto add=[&](std::string name,std::string description,Json schema,bool readonly,
                     std::function<Json(const Json&,const CallContext&)> handler,Json output=object()) {
            Operation op;op.name=std::move(name);op.description=std::move(description);
            op.input_schema=std::move(schema);op.output_schema=std::move(output);
            op.read_only=readonly;op.schema_validation=validation;
            op.handler=[handler=std::move(handler)](const Json& p,const CallContext& c) {
                return Json{{"result",handler(p,c)}};
            };
            registry->add(std::move(op));
        };
        const Json job_output={{"type","object"},{"properties",{{"result",envelope(schemas.at("job"),"result")}}},
                               {"required",Json::array({"result"})},{"additionalProperties",false}};
        std::set<std::string> reserved_names;
        for(const auto& op : descriptor.at("operations"))
            reserved_names.insert("op_"+op.at("id").get<std::string>());
        for (const auto& op : descriptor.at("operations")) {
            auto id=op.at("id").get<std::string>();
            Json props={{"parameters",envelope(op.at("inputSchema"),"parameters")},
                {"sessionId",{{"type","string"}}},{"backendId",{{"type","string"}}},{"modelId",{{"type","string"}}},
                {"priority",controls.at("SubmitJob").at("properties").at("priority")}};
            for (auto name : {"queueTimeout","executionTimeout"})
                props[name]=controls.at("SubmitJob").at("properties").at(name);
            Json spec={{"type","object"},{"properties",props},{"required",Json::array({"parameters"})},{"additionalProperties",false}};
            auto tool_name="op_"+id;
            if(tool_name.size()>128){
                for(unsigned salt=0;;++salt){
                    auto alias="op_"+id.substr(0,100)+"_"+sha256(id+":"+std::to_string(salt)).substr(0,24);
                    if(reserved_names.insert(alias).second){tool_name=std::move(alias);break;}
                }
            }
            add(tool_name,op.value("description",id)+" [operationId: "+id+"] Starts an asynchronous job. Poll cy_get_job; export wanted results, then cy_finish_task. Absolute local inputs are imported automatically. Task files are temporary.",spec,false,
                [this,id](const Json& p,const CallContext& c){return task_call("SubmitJob",p,c,id);},job_output);
        }
        const std::map<std::string,std::string> names={
            {"cy_describe","DescribeTool"},{"cy_status","GetRuntimeStatus"},{"cy_list_jobs","ListJobs"},
            {"cy_get_job","GetJob"},{"cy_cancel_job","CancelJob"},{"cy_events","GetEvents"},
            {"cy_can_run","CanRun"},{"cy_capabilities","GetCapabilities"},{"cy_list_operations","ListOperations"},
            {"cy_describe_operation","DescribeOperation"},{"cy_list_backends","ListBackends"},{"cy_list_models","ListModels"},
            {"cy_system_resources","GetSystemResources"},{"cy_estimate","EstimateResources"},{"cy_diagnose","Diagnose"},
            {"cy_release_resources","ReleaseResources"},{"cy_begin_task","CreateSession"},{"cy_finish_task","FinishTask"},
            {"cy_keep_task_alive","KeepTaskAlive"},{"cy_export_job","ExportJob"},{"cy_import_file","ImportFile"},
            {"cy_share_job","ShareJob"},{"cy_submit_job","SubmitJob"}};
        for (const auto& [name,method] : names) {
            Json spec=controls.at(method);
            if (method=="CreateSession") spec["properties"]["temporary"]={{"const",true},{"default",true}};
            if (method=="SubmitJob" || method=="FinishTask" || method=="KeepTaskAlive" || method=="ImportFile") {
                Json required=Json::array();
                for (auto& item : spec.value("required",Json::array())) if(item!="sessionId") required.push_back(item);
                spec["required"]=required;
            }
            const bool mutating=method=="SubmitJob" || method=="CancelJob" || method=="ReleaseResources" || method=="CreateSession" ||
                method=="FinishTask" || method=="KeepTaskAlive" || method=="ExportJob" || method=="ImportFile" || method=="ShareJob";
            add(name,method+" (CyTools v1). Task files are temporary; export results before finishing a task.",spec,!mutating,
                [this,method](const Json& p,const CallContext& c){return task_call(method,p,c);},
                (method=="GetJob" || method=="SubmitJob")?job_output:object());
        }
        McpServerOptions options;
        options.result_text=[](const Json& value){return value.at("result").dump();};
        mcp=std::make_unique<McpServer>(*registry,descriptor.at("name").get<std::string>(),options);
    }
};
Communication::Communication(HostCallback cb):impl_(std::make_unique<Impl>(std::move(cb))){}
Communication::~Communication(){stop_http();impl_->clean_tasks();}
Json Communication::dispatch(const Json& request,const std::string& principal) {
    impl_->bootstrap(); return impl_->wire(request,principal);
}
Json Communication::sdk(const Json& request,const std::string& principal) {
    impl_->create_registry(); CallContext context;
    if(!principal.empty()) context.principal=principal;
    return dispatch_app(*impl_->registry,request,context);
}
int Communication::start_http(int port) {
    if(impl_->http) throw Error("InvalidState","Server already running");
    auto auth=[this](std::string_view token){
        return impl_->host({{"method","$authenticate"},{"token",std::string(token)}}).at("principal").get<std::string>();
    };
    auto endpoint=[this](const Json& request,const CallContext& context){
        // HTTP v1 retains the portable CyTools request envelope and host identity.
        if(request.contains("protocolVersion")) return impl_->wire(request,context.principal);
        if(request.value("method",std::string())=="cytools.host"){
            const auto& internal=request.at("request");
            const auto method=internal.value("method",std::string());
            if(method=="$schemas")return impl_->callback(internal);
            if(method=="$check_schema" || method=="$validate"){
                impl_->create_registry();
                const auto& spec=internal.at("schema");
                bool known=spec==Json::object();
                for(const auto& op : impl_->registry->describe())
                    known=known || spec==op.at("inputSchema") ||
                        (op.contains("outputSchema") && spec==op.at("outputSchema"));
                if(known)return impl_->callback(internal);
            }
            // No arbitrary schema evaluation, identity selection or host methods over HTTP.
            return Json{{"error",error_value("AccessDenied","Unknown host schema or binding method")}};
        }
        return sdk(request,context.principal);
    };
    impl_->http=std::make_unique<LocalHttpServer>(auth,endpoint,8,1024*1024);
    return impl_->http->start(port);
}
void Communication::stop_http(){if(impl_ && impl_->http){impl_->http->stop();impl_->http.reset();}}
void Communication::serve_mcp(){impl_->create_registry();impl_->mcp->serve_stdio(std::cin,std::cout);impl_->clean_tasks();}
Json Communication::http_call(const std::string& url,const std::string& token,const Json& request,int timeout_ms){
    auto parsed=parse_url(url);
    if(parsed.scheme!="https" && !(parsed.scheme=="http" && parsed.loopback))
        throw Error("ConfigurationError","Remote API connections require HTTPS");
    HttpRequest http;http.method="POST";http.url=url;http.body=request.dump();
    http.headers={{"Authorization","Bearer "+token},{"Content-Type","application/json"}};
    http.timeout=std::chrono::milliseconds(timeout_ms);
    auto reply=HttpClient().perform(http);
    if(reply.status!=200) throw Error(reply.status==401?"AuthenticationRequired":"TransportError","HTTP "+std::to_string(reply.status));
    return parse_json(reply.body,provider_message_limit);
}
int Communication::run_cli(const std::vector<std::string>& argv){
    std::string command, data_dir=".cytools", operation, text="{}", params_file, backend, model, name, export_dir;
    std::vector<std::string> permissions;double timeout=300;int port=8766;
    std::set<std::string> supplied;
    auto value=[&](std::size_t& i){if(++i>=argv.size())throw Error("InvalidParameters","Missing argument value");return argv[i];};
    for(std::size_t i=0;i<argv.size();++i){const auto& a=argv[i];
        if(a.starts_with("--"))supplied.insert(a);
        if(a=="--data-dir")data_dir=value(i);
        else if(a=="--connect")impl_->remote_url=value(i);
        else if(a=="--params")text=value(i);
        else if(a=="--params-file")params_file=value(i);
        else if(a=="--export-dir")export_dir=value(i);
        else if(a=="--backend")backend=value(i);
        else if(a=="--model")model=value(i);
        else if(a=="--timeout")timeout=std::stod(value(i));
        else if(a=="--port")port=std::stoi(value(i));
        else if(a=="--name")name=value(i);
        else if(a=="--permission")permissions.push_back(value(i));
        else if(a=="--help" || a=="-h"){
            std::cout<<"CyTools native communication 0.11.0 / CyMCPSDK "<<cymcp::version<<"\n"
                <<"Commands: describe, list-operations, describe-operation ID, list-backends, list-models, diagnose, estimate ID, can-run ID, invoke ID, stdio, mcp, serve, create-client\n"
                <<"Options: --data-dir PATH, --connect URL, --params JSON, --params-file FILE, --export-dir ABSOLUTE_PATH, --backend ID, --model ID, --timeout SECONDS, --port PORT\n";return 0;
        } else if(a.starts_with('-'))throw Error("InvalidParameters","Unknown option: "+a);
        else if(command.empty())command=a;
        else if(operation.empty())operation=a;
        else throw Error("InvalidParameters","Unexpected positional argument");
    }
    const std::set<std::string> commands={"describe","list-operations","describe-operation","list-backends","list-models","diagnose","estimate","can-run","invoke","stdio","mcp","serve","create-client"};
    if(!commands.contains(command))throw Error("InvalidParameters","A supported command is required; use --help");
    std::set<std::string> accepted={"--data-dir","--connect"};
    if(command=="invoke" || command=="estimate" || command=="can-run")
        accepted.insert({"--params","--params-file","--backend","--model"});
    if(command=="invoke")accepted.insert({"--timeout","--export-dir"});
    if(command=="serve")accepted.insert("--port");
    if(command=="create-client")accepted.insert({"--name","--permission"});
    for(const auto& option : supplied)
        if(!accepted.contains(option))throw Error("InvalidParameters","Option does not apply to this command: "+option);
    if(!operation.empty() && command!="invoke" && command!="estimate" && command!="can-run" && command!="describe-operation")
        throw Error("InvalidParameters","Unexpected operation argument");
    if(supplied.contains("--params") && supplied.contains("--params-file"))
        throw Error("InvalidParameters","Use either --params or --params-file");
    if(!impl_->remote_url.empty()){
        if(command=="serve" || command=="create-client")throw Error("InvalidParameters","Command requires a local Tool host");
        const auto token=std::getenv("CYTOOLS_TOKEN");if(!token || !*token)throw Error("AuthenticationRequired","Set CYTOOLS_TOKEN for the selected client");
        impl_->remote_token=token;
    }else if(command=="create-client"){
        if(name.empty())throw Error("InvalidParameters","--name is required");
        std::cout<<impl_->host({{"method","$create_client"},{"params",{{"dataDir",data_dir},{"name",name},{"permissions",permissions}}}}).dump()<<std::endl;return 0;
    }else impl_->bootstrap(data_dir);
    if(command=="mcp"){serve_mcp();return 0;}
    if(command=="stdio"){
        std::string line;while(std::getline(std::cin,line)){
            Json response;try{response=impl_->wire(parse_json(line),"");}
            catch(const Error& e){response={{"protocolVersion","1.0"},{"id",nullptr},{"error",error_value(e.code,e.what())}};}
            std::cout<<response.dump()<<std::endl;
        }return 0;
    }
    if(command=="serve"){
        const auto actual=start_http(port);
        std::cerr<<"CyTools native API listening on http://127.0.0.1:"<<actual<<"/v1\n"<<std::flush;
        interrupted=false;auto previous=std::signal(SIGINT,on_interrupt);
        while(!interrupted.load())std::this_thread::sleep_for(std::chrono::milliseconds(50));
        std::signal(SIGINT,previous);stop_http();return 0;
    }
    if(command=="invoke" || command=="estimate" || command=="can-run" || command=="describe-operation"){
        if(operation.empty())throw Error("InvalidParameters","Operation ID is required");
        Json args={{"operationId",operation}};
        if(command!="describe-operation"){
            args["parameters"]=params_file.empty()?parse_json(text):read_json_file(params_file);
            args["backendId"]=backend;args["modelId"]=model;
        }
        if(command!="invoke"){
            auto method=command=="estimate"?"EstimateResources":command=="can-run"?"CanRun":"DescribeOperation";
            std::cout<<impl_->call(method,args).dump(2)<<std::endl;return 0;
        }
        if(!std::isfinite(timeout) || timeout<=0)throw Error("InvalidParameters","Timeout must be positive and finite");
        // AI/CLI work is a temporary task. Export explicitly through SDK/MCP to retain files.
        auto session=impl_->call("CreateSession",{{"temporary",true}}).at("sessionId");
        try{
            args["sessionId"]=session;args["queueTimeout"]=timeout;args["executionTimeout"]=timeout;
            auto job=impl_->call("SubmitJob",args);auto deadline=Clock::now()+std::chrono::duration<double>(timeout+5);
            while(job["state"]!="Completed" && job["state"]!="Failed" && job["state"]!="Cancelled"){
                if(Clock::now()>deadline)throw Error("Timeout","Job has not stopped; query its ID before retrying");
                std::this_thread::sleep_for(std::chrono::milliseconds(30));job=impl_->call("GetJob",{{"jobId",job["jobId"]}});
            }
            const bool completed=job["state"]=="Completed";
            Json exported;
            if(!export_dir.empty())exported=impl_->call("ExportJob",{{"jobId",job["jobId"]},{"destination",export_dir}});
            impl_->call("FinishTask",{{"sessionId",session},{"cancelRunning",true}});
            if(export_dir.empty()){
                auto snapshot=job.at("outputs");
                job=impl_->call("GetJob",{{"jobId",job["jobId"]}});
                // Keep the returned value snapshot; artifactsDeleted describes file lifetime.
                job["outputs"]=std::move(snapshot);
            }
            std::cout<<(export_dir.empty()?job:exported).dump()<<std::endl;
            return completed?0:1;
        }catch(...){try{impl_->call("FinishTask",{{"sessionId",session},{"cancelRunning",true}});}catch(...){}throw;}
    }
    const std::map<std::string,std::string> mapping={{"describe","DescribeTool"},{"list-operations","ListOperations"},
        {"list-backends","ListBackends"},{"list-models","ListModels"},{"diagnose","Diagnose"}};
    std::cout<<impl_->call(mapping.at(command)).dump(2)<<std::endl;return 0;
}
}
