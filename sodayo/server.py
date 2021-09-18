#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/16 

import os
import re
import signal
from importlib import reload as reload_module
from traceback import format_exc

from flask import Flask, jsonify, request

import settings as hp
from packets import *
from utils import *


__version__ = '0.1'     # 2021/09/18


##############################################################################
# [code layout]
#
#   Data Layer:       gloabals
#                     rtdata
#                     stdata
#   Service Layer:    utils
#                     services
#   Route Layer:      HTTP routes
#


##############################################################################
# globals

__role__ = 'server'

app = Flask(__name__)
with open('index.html', encoding='utf-8') as fp:
  html_page = fp.read()


##############################################################################
# rtdata: 运行时数据
# NOTE: dumpable structs MUST named endswith '_info'
#       tranferable structs MUST typed in [dict, list] (aka. JSON roots)

# for `heatrbeat`
# NOTE: dead nodes checked every `DYNAMIC_UNREGISTER_WAIT`
registry_info = {
  # ('127.0.0.1', 6666): 'server1'
}

# for `stats`/`query`
hardware_info = {
  # 'server1': struct of `client.hardware_info`
}

# for `stats`/`query`
# NOTE: length truncated by `RTDATA_TRUNCATE_EXPIRE`
runtime_info = {
  # 'server1': struct of `client.runtime_info`
}

# for `heatrbeat`
last_ACK_info = {
  # 'server1': 1631766896
}

# for `query`
# NOTE: reset at beginning of each month
quota_info = {
  # 'nobody': [233*60, 1500*60]    # [available, total], int in minutes
}


##############################################################################
# stdata: 持久存档数据
# NOTE: record class SHOULD named `xxRecord`, MUST subclassing from `Record`
#       manager class SHOULD named `xxRecords`, MUST subclassing from `Records` and **metaclassing** from `RecordsMeta`

class TaskRecord(Record):

  hostname: str
  gpu_id: int
  username: str
  command: str
  start_ts: int
  end_ts: int

class TaskRecords(Records, metaclass=RecordsMeta):

  @classmethod
  def load(cls):
    try:
      if os.path.exists(cls.db_file):
        cls.objects = load_pkl(cls.db_file)
    except Exception:
      logger.error(format_exc())

  @classmethod
  def save(cls):
    try:
      save_pkl(cls.objects, cls.db_file)
    except Exception:
      logger.error(format_exc())

  @classmethod
  def add(cls, record:TaskRecord):
    cls.objects.append(record)

  @classmethod
  @perf_timer
  def query(cls, hostname:str=None, gpu_id:int=None, username:str=None, 
                 start_ts:int=None, end_ts:int=None, command:str=None):
    rs = [ ]
    for t in cls.objects:
      if hostname and hostname != t.hostname: continue
      if gpu_id and gpu_id != t.gpu_id: continue
      if username and username != t.username: continue
      if start_ts and t.start_ts < start_ts: continue
      if end_ts and end_ts < t.end_ts: continue
      if command and (command not in t.command) and (not re.match(command, t.command)): continue
      rs.append(t)
    rs.sort(key=lambda t: t.start_ts)
    return rs


##############################################################################
# utils

def startup():
  logger.info(f'[startup]')

  # prewatch for fixed slaves
  reload_quota_rule()
  for sock in hp.SLAVES_SOCKET:
    registry_info[sock] = 'unknown'

  load_stdata()
  load_rtdata(globals(), prefix=__role__)

def cleanup():
  logger.info(f'[cleanup]')

  dump_stdata()
  dump_rtdata(globals(), prefix=__role__)

def reload_quota_rule():
  if not os.path.exists(hp.QUOTA_RULE_FILE):
    logger.warning('[parse_quota_rule] quota rule not found :(')
    return
  
  with open(hp.QUOTA_RULE_FILE) as fh:
    for line in fh.read().split('\n'):
      if line.startswith('#') or not line.strip(): continue
      try:
        username, quota = whitespace_collapse(line.strip()).split(' ')
        quota = int(quota)
        if username in quota_info: quota_info[username][1] = quota * 60
        else:                      quota_info[username] = [quota * 60, quota * 60]
      except:
        logger.warning(f'[parse_quota_rule] cannot parse line {line:!r}, ignored')

def reload_settings(signum, frame):
  logger.info('[reload_settings]')

  reload_quota_rule()

  global hp
  hp = reload_module(hp)
  from utils import _reload_settings
  _reload_settings()


##############################################################################
# services

def heartbeat(socket:Tuple[str, int], hostname:str) -> ResponsePacket:
  # if new client
  if socket not in registry_info:
    registry_info[socket] = hostname
  # if already registered
  else:
    hostname_old = registry_info[socket]
    # host replaced, clear old data
    if hostname_old != hostname:
      registry_info[socket] = hostname
      del hardware_info[hostname_old]
      del runtime_info[hostname_old]
      del last_ACK_info[hostname_old]

  return RESPONSE.OK()

def stats_hardware(hostname:str, data:dict=None) -> ResponsePacket:
  hardware = data.get('hardware')
  if None is hardware: return RESPONSE.BAD_REQUEST()

  hardware_info[hostname] = hardware
  return RESPONSE.OK()

def stats_runtime(hostname:str, data:dict=None) -> ResponsePacket:
  runtime = data.get('runtime')
  if None is runtime: return RESPONSE.BAD_REQUEST()

  # sanitize history
  if hostname not in runtime_info: runtime_info[hostname] = deque()
  if 'ts' not in runtime: runtime['ts'] = now_ts()    # sigil if absent
  runtime_info[hostname].append(runtime)
  if len(runtime_info[hostname]):
    now_ts_freeze = now_ts()
    while runtime_info[hostname][0]['ts'] + day_to_sec(hp.RTDATA_TRUNCATE_EXPIRE) < now_ts_freeze:
      runtime_info[hostname].popleft()

  return RESPONSE.OK()

def stats_tasks(hostname:str, data:dict=None) -> ResponsePacket:
  tasks = data.get('hardware')
  if None is tasks: return RESPONSE.BAD_REQUEST()

  for task in data.get('tasks'):
    TaskRecords.add(TaskRecord(**task))

  return RESPONSE.OK()

def query_settings(**kwargs) -> ReplyPacket:
  return jsonify(RESPONSE.OK(data=dict(hp)))

def query_quota(**kwargs) -> ReplyPacket:
  username = kwargs.get('username')
  
  if None is username:
    return RESPONSE.OK(data=quota_info)
  elif username in quota_info:
    return RESPONSE.OK(data={username: quota_info[username]})
  else:
    return RESPONSE.NOT_ACCEPTABLE(data={'reason': 'requested user no found'})

def query_hardware(**kwargs) -> ReplyPacket:
  hostname = kwargs.get('hostname')

  if None is hostname:
    return RESPONSE.OK(data=hardware_info)
  elif hostname in hardware_info:
    return RESPONSE.OK(data={hostname: hardware_info[hostname]})
  else:
    return RESPONSE.NOT_ACCEPTABLE(data={'reason': 'requested host no found'})

def query_runtime(**kwargs) -> ReplyPacket:
  hostname = kwargs.get('hostname')
  start_ts = kwargs.get('start_ts')
  end_ts = kwargs.get('end_ts')
  
  now_ts_freeze = now_ts()
  start_ts = None is start_ts and (now_ts_freeze - 7*24*60*60) or start_ts
  end_ts = None is end_ts and now_ts_freeze or start_ts
  if start_ts >= end_ts:
    return RESPONSE.NOT_ACCEPTABLE(data={'reason': 'start_ts should before end_ts'})

  hostnames = None is hostname and hardware_info.values() or [hostname]
  res = { }
  for name in hostnames:
    rtdata = runtime_info[name]
    # TODO: use binary search!
    i = 0
    while rtdata[i]['ts'] < start_ts: i += 1
    j = len(rtdata) - 1
    while end_ts < rtdata[j]['ts']: j -= 1
    res[name] = rtdata[i:j]
  return RESPONSE.OK(data=res)

def query_tasks(**kwargs) -> ReplyPacket:
  res = TaskRecords.query(hostname=kwargs.get('hostname'),
                          gpu_id=kwargs.get('gpu_id'),
                          username=kwargs.get('username'),
                          start_ts=kwargs.get('start_ts'),
                          end_ts=kwargs.get('end_ts'),
                          command=kwargs.get('command'))

  return RESPONSE.OK(data=res)

def realloc(**kwargs) -> ReplyPacket:
  username = kwargs.get('username')
  password = kwargs.get('password')
  try: gpu_count = int(kwargs.get('gpu_count'))
  except: gpu_count = None
  if None in [username, password, gpu_count]:
    return RESPONSE.BAD_REQUEST()
  
  # TODO:
  return RESPONSE.NOT_IMPLEMENTED()

def _refresh_last_ACK(hostname:str):
  # NOTE: this should been called at beginning of `stats` or `heartbeat` at server layer
  # but we move them to route layer to reduce code lines
  last_ACK_info[hostname] = now_ts()


##############################################################################
# HTTP routes

@app.route('/', methods=['GET'])
def root():
  return html_page


@app.route('/heartbeat', methods=['POST'])
def api_heartbeat():
  # check post data existentiality
  data = request.form.to_dict()
  logger.debug(f'/heartbeat with {data}')
  if None is data: return jsonify(RESPONSE.BAD_REQUEST())

  # check data field integrity
  socket = (request.remote_addr, request.environ.get('REMOTE_PORT'))
  hostname = data.get('hostname')
  _refresh_last_ACK(hostname)

  return jsonify(heartbeat(socket, hostname))


@app.route('/stats', methods=['POST'])
def api_stats():
  # check post data existentiality
  data = request.form.to_dict()
  logger.debug(f'/stats with {data}')
  if None is data: return jsonify(RESPONSE.BAD_REQUEST())

  # assure registered
  socket = (request.remote_addr, request.environ.get('REMOTE_PORT'))
  if socket not in registry_info: return jsonify(RESPONSE.UNAUTHORIZED())
  hostname = registry_info.get(socket)
  _refresh_last_ACK(hostname)

  # check data field integrity
  fn = locals().get(f'stats_{request.get("type")}')
  if fn: return jsonify(fn(hostname, data))
  else:  return jsonify(RESPONSE.BAD_REQUEST())


@app.route('/query', methods=['POST'])
def api_query():
  # check post data existentiality
  data = request.form.to_dict()
  logger.debug(f'/query with {data}')
  if None is data: return jsonify(RESPONSE.BAD_REQUEST())

  # check data field integrity
  fn = locals().get(f'query_{request.get("type")}')
  if fn: return jsonify(fn(**data))
  else:  return jsonify(RESPONSE.BAD_REQUEST())


@app.route('/realloc', methods=['POST'])
def api_realloc():
  # check post data existentiality
  data = request.form.to_dict()
  logger.debug(f'/realloc with {data}')
  if None is data: return jsonify(RESPONSE.BAD_REQUEST())
  
  return jsonify(realloc(**data))


##############################################################################
# main entry

if __name__ == '__main__':
  # cactch signal SIGUSR1: supports dynamic setting reloading (only works on GNU/Linux
  if hasattr(signal, 'SIGUSR1'): signal.signal(signal.SIGUSR1, reload_settings)

  init_logger(__role__)
  from utils import logger    # import again to fix non-init problem

  try:
    startup()
    host, port = hp.MASTER_SOCKET
    app.run(host=host, port=port, debug=False)
  except KeyboardInterrupt:
    logger.info('exit by Ctrl+C')
  except Exception:
    logger.error(format_exc())
  finally:
    cleanup()
