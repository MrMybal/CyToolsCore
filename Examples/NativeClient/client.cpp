#include <cytools/communication.hpp>
#include <cstdlib>
#include <iostream>
int main(int argc,char** argv){
    if(argc==1){std::cout<<cytools_native_info()<<std::endl;return 0;}
    const auto token=std::getenv("CYTOOLS_TOKEN");
    if(!token){std::cerr<<"Set CYTOOLS_TOKEN for your service identity\n";return 1;}
    try{
        auto result=cytools::Communication::http_call(argv[1],token,
            {{"protocolVersion","1.0"},{"id",1},{"method","DescribeTool"},{"params",cytools::Json::object()}});
        std::cout<<result.dump()<<std::endl;return result.contains("error")?1:0;
    }catch(const cymcp::Error& e){
        std::cerr<<cytools::Json{{"error",{{"code",e.code},{"message",e.what()}}}}.dump()<<std::endl;return 1;
    }
}
