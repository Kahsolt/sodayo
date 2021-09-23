# sodayo (便乗)

    A simple-stupid (i.e. unsecure) dashboard monitoring your measly laboratory GPUs, for managing usage quota :(

----

## Quickstart

  - 平台 & 权限
    - Linux类系统
    - 访问权限: 最好能 读写 `/run`, 读 `/proc`
  - 配置
    - 配额规则: `quota_rule.txt`
    - 节点配置: `sodayo/settings.py`，建议在项目根目录放一个软链接 `ln -s sodayo/settings.py settings.py`
    - 动态更新配置: 给server进程发送 `SIGUSR1` 信号
  - 运行
    - 手动部署: 使用 `run.py` 脚本
      - 主节点运行 `python3 run.py --server`
      - 从节点运行 `python3 run.py --client`
      - 浏览器访问 `MASTER_SOCKET` 所设置的地址
    - [没实现] 自动部署: 使用 `deploy.py` 脚本
      - 所有节点: `python3 deploy.py --all`; 需要先配置 `MASTER_SOCKET` 和 `SLAVES_SOCKET`
      - 指定节点: `python3 deploy.py --host <ip> --port <port> --role [server|client]`
  - 停止
    - 给client/server进程发送 `SIGINT` 信号

#### requirements

  - Flask
  - Flask-SocketIO
  - gpustat

----
Armit, 2021/9/16
