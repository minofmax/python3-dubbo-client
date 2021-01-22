import re
import sys
import telnetlib
import time
import traceback
from typing import Union, List

from kazoo.client import KazooClient


class TelnetClient(object):
    """
    通过telnet连接和dubbo provider建立TCP链接
    """

    def __init__(self, server_host, server_port):
        self.tn = telnetlib.Telnet()
        self.server_host = server_host
        self.server_port = server_port

    def connect_dubbo(self):
        """
        实现利用telnet lib连接dubbo服务端
        :return:
        """
        try:
            print("telent连接dubbo服务端: telnet {} {} ……".format(self.server_host, self.server_port))
            self.tn.open(self.server_host, port=self.server_port)
            return True
        except Exception as e:
            print('连接失败, 原因是: {}'.format(str(e)))
            return False

    def execute_some_command(self, command):
        """
        此函数实现执行传过来的命令，并输出其执行结果
        :param command:
        :return:
        """
        cmd = (command + '\n').encode("gbk")
        self.tn.write(cmd)

        # 获取命令结果,字符串类型
        retry_count = 0
        result = self.tn.read_very_eager().decode(encoding='gbk')
        # 如果响应未及时返回,则等待后重新读取，并记录重试次数，重试不超过3次
        while result == '' and retry_count <= 3:
            time.sleep(1)
            result = self.tn.read_very_eager().decode(encoding='gbk')
            retry_count += 1
        return result

    def logout_host(self):
        self.tn.write(b"exit\n")
        print("登出成功")


class InvokeDubboApi(object):
    """
    调用dubbo provider提供的服务接口
    """

    def __init__(self, server_host, server_port):
        try:
            self.telnet_client = TelnetClient(server_host, server_port)
            self.login_flag = self.telnet_client.connect_dubbo()
        except Exception as e:
            print("invoke dubbo api init error" + str(e))

    def invoke_dubbo_api(self, dubbo_service, dubbo_method, *args):
        """
        调用dubbo接口
        :param dubbo_service: dubbo provider的服务接口, 如HelloService, 是interface
        :param dubbo_method: 接口中的具体的额方法
        :param args: 传入的参数
        :return:
        """
        api_name = dubbo_service + "." + dubbo_method + "{}"
        # api_name = dubbo_service + "." + dubbo_method + "(" + "{\"class\": \"com.test.dubbotest.TestEntity\",\"name\": \"test\",\"age\": \"25\"}" + ")"
        cmd = "invoke " + api_name.format(args)
        cmd = cmd.replace(",)", ")").replace("'", '"')
        print("调用命令是：{}".format(cmd))
        resp0 = None
        try:
            if self.login_flag:
                resp0 = self.telnet_client.execute_some_command(cmd)
                print("接口响应是,resp={}".format(resp0))
                # dubbo接口返回的数据中有 elapsed: 4 ms. 耗时，需要使用elapsed 进行切割
                return str(re.compile(".+").findall(resp0).pop(0)).split("elapsed").pop(0).strip()
            else:
                print("登陆失败！")
        except Exception as e:
            raise Exception("调用接口异常, 接口响应是resp={}, 异常信息为：{}".format(resp0, str(e)))
        self.logout()

    def logout(self):
        self.telnet_client.logout_host()


class Dubbo(object):
    """
    dubbo调用入口
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def _init_dubbo_client(self):
        """
        实例化一个dubbo client
        :return:
        """
        dubbo = InvokeDubboApi(self.host, self.port)
        return dubbo

    def invoke_api(self, service: str, method: str, type: str, params: Union[dict, list, None]) -> str:
        """
        调用provider的api
        :param service: provider对外暴露的接口
        :param method: provider方法
        :param type: 参数类型，pojo类和其他参数调用的传参不一样
        :param params: 请求参数：常规参数用list[]接收,如["test",25], pojo类需要用下面这个格式：
        {
        "class": "com.test.dubbotest.TestEntity",
        "name": "test",
        "age": "25"
        }
        需要注意的是，java里不接受"'",同时需要注意序列化和反序列化的问题
        :return:
        """
        if not (isinstance(params, dict) or isinstance(params, list)):
            raise Exception('调用dubbo的方法类型非法')
        dubbo = self._init_dubbo_client()
        if type == 'class':
            return_result = dubbo.invoke_dubbo_api(service, method, params)
        else:
            return_result = dubbo.invoke_dubbo_api(service, method, *params)
        return return_result


class GetDubboService(object):
    """
    利用zookeeper来获取dubbo provider的注册地址
    """

    def __init__(self, hosts):
        """
        传入zk地址：'domain:2183'
        如果是ip,则输入ip:port,ip1:port用逗号隔开
        :param hosts: 'domain:2183'或者'ip:port,ip1:port,ip2:port'
        """
        self.hosts = hosts
        if self.hosts:
            self.zk = KazooClient(hosts=self.hosts, timeout=15)
            self.zk.start()  # 与zookeeper连接
        else:
            print("请配置zk地址信息zookeeper.address字段")
            sys.exit(0)

    def get_dubbo_info(self, dubbo_service):
        """
        根据service接口来查询当前zk中是否有提供该dubbo_service的dubbo服务注册
        :param dubbo_service: 需要将service接口的包路径全量传入，如：'com.test.dubbotest.HelloService'
        :return: 
        if exist:
        return {'server_host': '172.25.213.146', 'server_port': '18080'}
        else:
        return None
        """
        try:
            nodes = self.zk.get_children('/dubbo/')
            if dubbo_service not in nodes:
                return None
            node = self.zk.get_children('/dubbo/' + dubbo_service + '/providers')
            from urllib import parse
            if node:
                server = parse.unquote(node[0])
                dubbore = re.compile(r"^dubbo://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+)", re.I)
                result = dubbore.match(server)
                if result:
                    result = result.group(1)
                    print("获取到dubbo部署信息" + result)
                    ip, port = result.split(":")
                    return {"server_host": ip, "server_port": port}
        except Exception as e:
            msg = traceback.format_exc()
            print('获取dubbo provider信息异常：{}'.format(msg))

    def stop_zk_connection(self) -> None:
        """
        断开zk连接, 在调用完api后, 请关闭和zk服务端的tcp连接
        :return:
        """
        self.zk.stop()

    def get_all_register_services(self) -> List[str]:
        """
        获取zk注册中心中所有注册的dubbo providers
        :return: 返回注册的服务
        """
        nodes = self.zk.get_children('/dubbo/')
        return nodes


if __name__ == '__main__':
    dubbo = Dubbo('localhost', 18080)
    param = {
        "class": "com.test.dubbotest.TestEntity",
        "name": "test",
        "age": "25"
    }
    # param = ['12345']
    # print(param.values())
    result = dubbo.invoke_api('HelloService', 'testDto', 'class', param)
    # print(json.loads(result))
    service = GetDubboService(hosts="zk地址")
    print(service.get_all_register_services())
    print(service.get_dubbo_info("com.test.dubbotest.HelloService"))
