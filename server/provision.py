"""编译完成后生成节点凭据，并把当前客户端哈希写入白名单。"""

from credential_store import provision_demo_credentials


if __name__ == "__main__":
    count = provision_demo_credentials(refresh_hashes=True)
    print(f"Provisioned credentials: {count} nodes")
