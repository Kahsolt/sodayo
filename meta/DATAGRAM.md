# 数据报格式

    JSON string is your best friend :)
    yet, HTTP protocol is your mirror!

----

### 客户端请求

    客户端可以发起的请求类型: Heartbeat, Stats, Query, Realloc

#### 心跳包 Heartbeat packet

    客户端 启动时发送一次 **心跳包** 以告知服务端存在; 之后，周期性地发送以刷新注册状态
    服务端 监视所有静态/动态注册的客户端，并自动遗忘已长时间失效的、经由动态注册的客户端
    NOTE: 若禁用了心跳机制，则 **统计数据包** 将作为替代的心跳

```json
POST /heartbeat

// request
{
  "hostname": "server1",  // 第一次心跳必填，之后可选
  "ts": 1631766896        // 时间戳，可选
}

// response
{
  "status_code": 200,
  "reason": "OK",
}
```

#### 统计数据包 Stats packet

    客户端 注册后发送一次 **hardware包** 报告 **硬件配置** 信息
    客户端 周期性 地发送 **runtime包** 报告最近的 **运行时** 情况
    客户端 适时性 地发送 **tasks包** 报告最近完成的 **任务** 情况
    服务端 整理这些信息、存档备查

```json
POST /stats

// request
{
  "type": "hardware",
  "hardware": {
    "hostname": "server1",
    "gpu": [
      {"name": "GeForce RTX 2080 Ti", "mem": 11019},   // int in MB 
      {"name": "GeForce RTX 2080 Ti", "mem": 11019},   // int in MB 
    ],
    "cuda": "11.1",
    "os": "Ubuntu 18.04.5 LTS",
    "cpu": {
      "name": "Intel(R) Xeon(R) Gold 5122 CPU @ 3.60GHz",
      "proc_num": 16,
      "clock_speed": 3677          // int in MHz
    },
    "mem": 95161,                  // int in MB
  }
}

// request
{
  "type": "runtime",
  "runtime": {
    "gpu": [
      {
        "gpu_id": 0,
        "temp": 76,           // int in celsius
        "usage": 82,          // int in celsius
        "mem_usage": 7200,    // int in MB
        "procs": [            // this be a list, cos' someone loves high-high-stack
          {
            "username": "nobody",
            "command": "python nocode.py",
            "gpu_memory_usage": 1320,     // int in MB
            "start_ts": 1631766896,
          }
        ]
      },
      {"gpu_id": 1, "temp": 0, "usage": 0, "mem_usage": 0, "procs": []},    // gpu[1]: this card is free
    ],
    "loadavg": 0.25,          // float
    "cpu_usage": 75,          // int in percentage
    "mem_free": 12345,        // int in MB
  }
}

{
  "type": "tasks",
  "tasks": [
    {
      "gpu_id": 0,
      "username": "nobody",
      "command": "python nocode.py",
      "start_ts": 1631766896,
      "end_ts": 1631767896,
    }
  ]
}

// response
{
  "status_code": 200,
  "reason": "OK",
}
```

#### 查询包 Query packet

    浏览器 发送 **查询包** 来获取近期的服务器群状态数据
    查询种类type有: setting, quota, hardware, runtime, tasks
    服务端 返回相应的信息

```json
POST /query

// request
{
  "type": "setting",
}

// response
{
  "status_code": 200,
  "reason": "OK",
  "data": {       // setting.py
    "MASTER_SOCKET": ["127.0.0.1", 2333],
    "SLAVES_SOCKET": [ ],
    "DYNAMIC_REGISTER": true,
    "HERATBEAT_INTERVAL": -1,
    "UPDATE_INTERVAL": 10,
    "COMMIT_INTERVAL": 60,
    "DEAD_REVIVE_INTERVAL": 60,
    "COREDUMP_INTERVAL": 10,
    "FLUSH_INTERVAL": 10,
    "BACKUP_INTERVAL": 5,
    "STDATA_TRUNCATE_EXPIRE": 360,
    "RTDATA_TRUNCATE_EXPIRE": 21,
    "QUOTA_RULE_FILE": "quota_rule.txt",
    "DATA_PATH": "data",
    "LOG_PATH": "log",
    "DEBUG_MODE": true,
  }
}


// request
{
  "type": "quota",
  "username": "nobody",       // 默认全部
}

// response
{
  "status_code": 200,
  "reason": "OK",
  "data": {                   // 返回所有用户的可用配额 (int in seconds)
    "nobody": [666, 3000],     // [剩余, 总量]
    "yesbody": [233, 1500]
  },
}


// request
{
  "type": "hardware",
  "hostname": "nohost",       // 默认全部
}

// response
{
  "status_code": 200,
  "reason": "OK",
  "data": [
    {
      "hostname": "server1",
      "gpu": [
        {"name": "GeForce RTX 1040 Ti", "mem": 11019},
        {"name": "GeForce RTX 4160 Sb", "mem": 11019},
      ],
      "cuda": "11.1",
      "os": "Ubuntu 18.04.5 LTS",
      "cpu": {
        "name": "Intel(R) Xeon(R) Silver 5122 CPU @ 3.60GHz",
        "proc_num": 16,
        "clock_speed": 3677
      },
      "mem": 95161,
    },
    {
      "hostname": "server2",
      "gpu": [
        {"name": "GeForce RTX 3090 Au", "mem": 23333},
      ],
    }
  ]
}


// request
{
  "type": "runtime",
  "hostname": "nohost",       // 默认全部
  "start_ts": 1631766896,     // 默认一周前
  "end_ts": 1631766996,       // 默认当前
}

// response
{
  "status_code": 200,
  "reason": "OK",
  "data": {
    "server1": [{}],
    "server2": [{}],
  },
}


// request
{
  "type": "tasks",
  "hostname": "nohost",       // 默认全部
  "gpu_id": "nogpu",          // 默认全部
  "username": "nobody",       // 默认全部
  "command": "[code]*.py?",   // 可正则表达式
  "start_ts": 1631766896,     // 默认一周前
  "end_ts": 1631766996,       // 默认当前
}

// response
{
  "status_code": 200,
  "reason": "OK",
  "data": {
    "user1": [
      {"hostname": "server1", "gpu_id": 0, "command": "python nocode.py", "start_ts": 1631766896, "end_ts": 1631767896},
      {"hostname": "server1", "gpu_id": 1, "command": "python yescode.py", "start_ts": 1631765896, "end_ts": 1631768896}
    ],
    "user2": [
      {"hostname": "server2", "gpu_id": 0, "command": "python nocode.py", "start_ts": 1631765896, "end_ts": 1631767996},
    ]
  }
}
```

#### 资源重分配请求包 Realloc packet

    浏览器 发送 **资源重分配请求包** 来申请重分配GPU
    服务端 执行操作，返回相应的信息

```json
POST /realloc

// request
{
  "username": "nobody",      // Linux账户名
  "password": "P@asW0rd",   // Linux账户密码
  "gpu_cnt": 2,             // 申请的GPU数量
}

// response
{
  "status_code": 200,
  "reason": "OK",
  "data": {                 // 若成功，返回可用的GPU所在机器和id
    "server": "server1",
    "gpu_ids": [0, 2],
  },
}

{
  "status_code": 406,
  "reason": "Not Acceptable",
  "data": {                 // 若失败，返回更详细的原因
    "reason": "资源不够/进程kill失败/..."
  },
}
```

----

### 服务端响应

    服务端响应的格式是统一的Response，如有额外数据则全部放在`data`域

#### 响应包 Response packet

```json
// ReplyPacket
{
  "status_code": 200,       // 状态码
  "reason": "OK",           // 状态码解释
  "data": { },              // 额外数据, 根据不同的API而论格式不同
  "ts": 1631768896,         // 时间戳
}

// ResponsePacket
{
  "status_code": 400,
  "reason": "Bad Request",
  "ts": 1631768896,
}
```

#### 常见HTTP状态码

| status_code | reason | why |
| :----: | :----: | :----: |
| 200 | OK | 正常完成、信息已接受 |
| 400 | Bad Request | 数据包格式无法解析，或参数残缺、错误 |
| 401 | Unauthorized | 未注册的客户端访问register之外的服务；禁用了动态注册，申请注册的客户端不在受信的静态注册列表里 |
| 406 | Not Acceptable | 出于某些主观原因(如数据错误、资源不够)，处理不成功 |
| 500 | Internal Server Error | 内部处理出错(如抛出异常) |
| 501 | Not Implemented | 功能/服务未实现 |

----

### tools & references

  - [JSON在线格式化](https://www.bejson.com)
  - [HTTP状态码列表](https://blog.csdn.net/dddxxy/article/details/100291186)

----
Armit, 2021/9/16