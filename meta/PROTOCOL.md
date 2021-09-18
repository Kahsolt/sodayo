# 协议与实现

    Just go atail and loop forever :)

----

### 客户端协议

#### 从节点协议

```python
# init stage
client.connect(MASTER_SOCKET)
client.request(REGISTER_PACKGE)

# monitor stage
while True:
  # if time to gather runtime stats
  if UPDATE_INTERVAL ticks:
    stats = get_runtime_stats()
    # if found newly finished task, report urgently
    for task in detect_finished_tasks(stats):
      cli.request(STATS_PACKGE(type=task))

  # if time to report runtime stats
  if COMMIT_INTERVAL ticks:
    cli.request(STATS_PACKET(type=stat))
```

#### 浏览器协议

```javascript
// init stage
client.connect(server)

```

### 服务端/主节点协议

```python
# register table
socket_to_hostname = {
  ('192.168.0.1', 11400): 'server1',
  ('192.168.2.7', 51400): 'server2',
}
# main rt data
rtdata = {
   # for each identifiable server
  'server1': {
    # Part A: dynamic socket info on register
    "ip": '192.168.0.1',
    "port": 11400,
    "last_ACK_info": "2021-09-16 12:34:56",
    # Part B: static hardware info copied from register packet
    "gpu": [
      {"name": "GeForce RTX 2080 Ti", "mem": 11019},
      {"name": "GeForce RTX 2080 Ti", "mem": 11019},
    ],
    "cuda": "11.1",
    "os": "Ubuntu 18.04.5 LTS",
    "cpu": {
      "name": "Intel(R) Xeon(R) Gold 5122 CPU @ 3.60GHz",
      "proc_num": 16,
      "clock_speed": 3677
    },
    "mem": 95161,
    # Part C: dynamic runtime info copied from stats::stat packet
    "gpu_stats": [
      {
        "temp": 76,
        "usage": 82,
        "mem_usage": 7200,
        "procs": [
          {
            "username": "nobody",
            "command": "python nocode.py --gpu 0 --dataset no_data --model_path ./o_model"
          }
        ]
      },
      {"temp": 0, "usage": 0, "mem_usage": 0, "procs": []},
    ],
    "cpu_usage": 75,
    "mem_free": 12345,
  },
  # yet another server
  'server2': ...
}

# init stage
if file(rtdata) exists:
  rtdata = load_coredump()
for cli in SLAVES_SOCKET:
  register_up(cli)
server.listen()

# monitor stage
while True:
  # if there are new clients
  cli = recieve_register()
  if cli in SLAVES_SOCKET or DYNAMIC_REGISTER:
    register_init(cli)

  # if there are regitered clients to heartbeat
  cli = recieve_heartbeat()
    register_refresh(cli)

  # if there are regitered clients to report stats
  cli, stats = recieve_stats()
  if stats:
    register_refresh(cli)
    update_rtdata(stats)
    update_db(stats)

  # if there are http requests to query stats 
  req = get_query_request()
  if req:
    stats = gather_stats_data(req.type)
    cli.response(RESP_PACKET(data=stats))

  # if there are http requests to alloc GPU 
  req = get_alloc_request()
  if req:
    gpu_ids = kill_and_realloc_gpu(req.alloc_cnt)
    cli.response(RESP_PACKET(data=gpu_ids))

  # if time to force flush db
  if FLUSH_INTERVAL ticks:
    flush_stdata()

  # if time to core dump
  if COREDUMP_INTERVAL ticks:
    save_coredump(rtdata)
    # try to clear out zombies
    for cli in registered_clis:
      if cli not in SLAVES_SOCKET and now() - cli.last_ACK_info > DYNAMIC_UNREGISTER_WAIT:
        registered_clis.remove(cli)
```

----
Armit, 2021/09/16 
