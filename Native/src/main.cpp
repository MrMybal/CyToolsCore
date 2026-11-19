#include <cytools/communication.hpp>
#include <iostream>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif
int run(const std::vector<std::string>& arguments){
    try{
        cytools::Communication host([](const auto&)->cytools::Json{
            throw cymcp::Error("ConfigurationError","Select --connect URL, or embed CyTools::Communication in a Tool host");
        });
        return host.run_cli(arguments);
    }catch(const cymcp::Error& e){
        std::cerr<<cytools::Json{{"error",{{"code",e.code},{"message",e.what()}}}}.dump()<<std::endl;return 1;
    }catch(const std::exception&){std::cerr<<"{\"error\":{\"code\":\"ConfigurationError\",\"message\":\"Invalid command arguments\"}}\n";return 1;}
}
#ifdef _WIN32
int wmain(int argc,wchar_t** argv){
    std::vector<std::string> arguments;
    for(int i=1;i<argc;++i){
        const int bytes=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,nullptr,0,nullptr,nullptr);
        if(!bytes){std::cerr<<"{\"error\":{\"code\":\"InvalidParameters\",\"message\":\"Invalid Unicode argument\"}}\n";return 1;}
        std::string value(static_cast<std::size_t>(bytes),'\0');
        WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,value.data(),bytes,nullptr,nullptr);
        value.pop_back();arguments.push_back(std::move(value));
    }
    return run(arguments);
}
#else
int main(int argc,char** argv){return run(std::vector<std::string>(argv+1,argv+argc));}
#endif
