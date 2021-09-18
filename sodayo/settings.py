#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/16 


# 主节点的位置
# ('host':str, port:int), default: ('127.0.0.1', 2333)
MASTER_SOCKET = ('127.0.0.1', 2333)


# 静态注册的从节点们的位置
# [('host':str, port:int)], default: []
# NOTE: 可空，参考`DYNAMIC_REGISTER`
SLAVES_SOCKET = [ ]


# 主节点是否接受除了`SLAVES_SOCKET`以外从节点的动态注册
# bool, default: True
DYNAMIC_REGISTER = True


# 主节点将在这个时间之后自动忘记已失效的、动态注册的从节点
# int (in minutes), default: 240
DYNAMIC_UNREGISTER_WAIT = 60 * 4


# 从节点发送 心跳heartbeat 的时间间隔
# int (in seconds), default: 15
# NOTE: -1表示禁用心跳
HERATBEAT_INTERVAL = -1


# 从节点采样 统计数据runtime_info 的时间间隔
# int (in seconds), default: 10
# NOTE: 该值应该比COMMIT_INTERVAL小，主要是为了更频繁地发现哪些任务结束了
UPDATE_INTERVAL = 10


# 从节点提交最近一次 统计数据runtime_info 的时间间隔
# int (in seconds), default: 60
COMMIT_INTERVAL = 60 * 1


# 主从节点宕机自动重启的检查间隔 (通过run.py脚本运行时)
# int (in minutes), default: 60
DEAD_REVIVE_INTERVAL = 60


# 主/从节点dump一次 运行时数据rtdata 的时间间隔，也是查找清理失效动态注册的节点的间隔
# int (in minutes), default: 10
COREDUMP_INTERVAL = 10


# 主节点强制flush一次 任务记录Task 的时间间隔
# int (in minutes), default: 10
# NOTE: 这是下限，数据量多时实际flush可能比这个值频繁
FLUSH_INTERVAL = 10


# 主节点备份一次 任务记录Task 的时间间隔
# int (in days), default: 5
BACKUP_INTERVAL = 5


# 主节点只滚动记录最近多少天的 持久存档数据stdata
# int (in days), default: 360
STDATA_TRUNCATE_EXPIRE = 30 * 12


# 主节点只滚动记录最近多少天的 运行时数据rtdata
# int (in days), default: 21
RTDATA_TRUNCATE_EXPIRE = 21


# 配额规则quota_rule 所在文件路径
# str (relpath or abspath), default: 'quota_rule.txt'
QUOTA_RULE_FILE = 'quota_rule.txt'


# 任务记录Task 与 运行时数据rtdata 文件存放的目录
# str (relpath or abspath), default: 'data'
DATA_PATH = 'data'


# 日志log 文件存放的目录
# str (relpath or abspath), default: 'log'
LOG_PATH = 'log'


# 启用 access log 和 控制台回显
# bool, default: False
DEBUG_MODE = True
