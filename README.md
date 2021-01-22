# python3-dubbo-client
## 一、简介

基于telnetlib实现直接调用dubbo provider暴露出来的服务。同时，也基于kazoo提供了从zk注册中心获取当前zk中注册所有服务的功能。
## 二、使用示例
直接调用dubbo provider地址
```python
dubbo = Dubbo('localhost', 18080)
param = {
    "class": "com.test.dubbotest.TestEntity", # 如果传入参数是pojo类接收,那么就需要指明package name + pojo name。其他使用可以参考方法注释。
    "name": "test",
    "age": "25"
} 
result = dubbo.invoke_api('HelloService', 'testDto', 'class', param)
```
根据zk地址获取当前注册中心中注册的所有服务提供方
```python
service = GetDubboService(hosts="zk地址")
print(service.get_all_register_services()) # 获取所有服务注册列表
print(service.get_dubbo_info("com.test.dubbotest.HelloService")) # 根据服务接口名查询,需要注意的是, 需要绝对路径, 且不支持模糊查询
```

