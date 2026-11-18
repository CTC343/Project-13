# client/client.c

控制台启动入口，读取命令行并执行公共客户端流程。

## main

```c
int main(int argc, char *argv[]);
```

**用途：** 控制台客户端入口：读取节点 ID、测试模式及是否持续在线的命令行选项，调用 run_client，打印收集到的日志，并把其退出码返回给操作系统。

| 参数 | 含义 |
| --- | --- |
| `argc` | [输入] 命令行参数总数，包含程序名本身；用于判断后续选项是否存在。 |
| `argv` | [输入] 命令行字符串数组；argv[0] 为程序名，argv[1] 为节点 ID，argv[2] 为 normal／wrong／tamper 模式，argv[3] 为 stay 时保持在线。缺省节点为 node-1，模式为 normal。 |
