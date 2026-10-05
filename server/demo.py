"""兼容原演示入口：打开控制中心，不再自动创建客户端节点。"""

from gui import ControlCenter


if __name__ == "__main__":
    ControlCenter().run()
