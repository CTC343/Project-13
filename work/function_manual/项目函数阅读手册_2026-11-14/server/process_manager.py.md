# server/process_manager.py

通过独立进程启动、停止或重启服务端，并将状态和输出送入事件队列；另提供打开已有客户端窗口的入口，不包含 GUI 控件实现。

## ProcessManager.__init__

```python
def __init__(self, event_queue):
```

**用途：** 初始化进程管理器，记住事件队列和项目目录，并创建服务端进程句柄及就绪事件的初始状态。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入/输出] 正在初始化的 ProcessManager 实例；为它设置 event_queue、project_root、server_process 和 server_ready。 |
| `event_queue` | [输入/输出] 接收状态事件的队列对象；后续方法通过 put() 写入 (事件类型, 内容) 二元组，例如 status、server_line、server_stopped。 |

## ProcessManager.default_task_settings

```python
def default_task_settings(self):
```

**用途：** 把配置中的运算、起止值、子任务数量和每个子任务节点数量组织为一个新的任务设置字典并返回。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入] 当前 ProcessManager 实例，用于调用该实例方法；这个方法的具体默认值来自导入的配置常量。 |

## ProcessManager.start_server

```python
def start_server(self, task_settings=None):
```

**用途：** 若服务端尚未运行，将任务设置转换为 PROJECT13_* 环境变量，使用当前 Python 解释器隐藏启动 server/server.py，并开后台线程转发输出。返回是否发起启动；传入 None 时使用默认参数但将任务模式设为等待客户端，显式传设置时启用任务。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入/输出] 当前 ProcessManager 实例；保存新进程句柄、清除就绪事件，并向事件队列写入启动状态。 |
| `task_settings` | [输入，可选，默认 None] 任务设置字典，需含 operation、start、end、subtask_count、nodes_per_subtask；为 None 时服务端只等待客户端。当前代码以“是否为 None”决定任务是否启用，以字典真假值决定是否取默认参数。 |

## ProcessManager.stop_server

```python
def stop_server(self):
```

**用途：** 停止已运行的服务端进程：先 terminate，等待 2 秒仍未结束则 kill；随后清空进程句柄和就绪事件，并写入停止状态。未运行时仅清空句柄并提示。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入/输出] 当前 ProcessManager 实例；读取并结束 server_process，更新 server_ready，并把状态写入 event_queue。 |

## ProcessManager.restart_server

```python
def restart_server(self, task_settings):
```

**用途：** 先停止当前服务端，再用给定任务设置启动新服务端；参数为 None 或空字典时改用默认任务设置，因此重启时会传入非 None 设置并开启任务。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入/输出] 当前 ProcessManager 实例；其进程句柄、就绪事件和事件队列由停止、启动流程更新。 |
| `task_settings` | [输入] 重启后使用的任务设置字典，字段与 start_server() 相同；None 或空字典会替换为 default_task_settings() 返回的默认设置。 |

## ProcessManager.open_client_window

```python
def open_client_window(self):
```

**用途：** 检查 client/client_gui.exe 是否存在；存在时启动一个客户端窗口，不存在时向事件队列提示先编译。本方法只负责启动程序，不实现窗口逻辑。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入/输出] 当前 ProcessManager 实例；读取 project_root 定位客户端程序，并通过 event_queue 发出提示。 |

## ProcessManager.is_server_running

```python
def is_server_running(self):
```

**用途：** 检查服务端进程句柄是否存在且 poll() 尚未得到退出码，返回布尔值；只表示进程存活，不证明监听端口已就绪。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入] 当前 ProcessManager 实例；读取它保存的 server_process。 |

## ProcessManager._read_server_output

```python
def _read_server_output(self):
```

**用途：** 作为后台线程逐行读取服务端标准输出；遇到 READY: 前缀时设置就绪事件，所有输出转成 server_line 事件，输出流结束后发送 server_stopped 事件。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入/输出] 当前 ProcessManager 实例；读取 server_process.stdout，必要时设置 server_ready，并持续向 event_queue 写入事件。 |
