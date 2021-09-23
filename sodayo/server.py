#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/16 

import os
import signal
import re
from itertools import islice
from threading import RLock, Thread, Event
from importlib import reload as reload_module
from uuid import uuid4 as gen_uuid
from time import sleep
from traceback import format_exc

from flask import Flask, jsonify, request, session
from flask.json import loads
from flask_socketio import SocketIO, emit, send

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
#                     tasks
#                     services
#   Route Layer:      HTTP routes
#                     WebSocket events


##############################################################################
# globals

__role__ = 'server'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Kimi mo Sodayo!'
socketio = SocketIO(app)
lock = RLock()      # for r/w `runtime_info`
with open('index.html', encoding='utf-8') as fp:
  html_page = fp.read()


##############################################################################
# rtdata: 运行时数据
# NOTE: dumpable structs MUST named endswith '_info'
#       tranferable structs MUST typed in [dict, list] (aka. JSON roots)

# for `heatrbeat`
# NOTE: dynamic registered dead nodes are removed after 30 HEARTBEAT_INTERVAL
registry_info = {
  # '127.0.0.1': 'server1'
}

# for `stats`/`query`
hardware_info = {
  # 'server1': struct `client.hardware_info`
}

# for `stats`/`query`
# NOTE: length truncated by `RTDATA_TRUNCATE_EXPIRE`
runtime_info = {
  # 'server1': deque of struct `client.runtime_info`
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

# for (browser only) `streamming`, this is transient and need NOT be dumpable
ws_resources = {
  # 'uuid': ?
}

##############################################################################
# stdata: 持久存档数据
# NOTE: record class SHOULD named `xxRecord`, MUST subclassing from `Record` and **metaclassing** from `RecordMeta`

class TaskRecord(Record, metaclass=RecordMeta):

  # inherited from super
  # objects: List[dict] = [ Task ]
  # 
  # struct Task { 
  #   hostname: str
  #   gpu_id: int
  #   username: str
  #   command: str
  #   start_ts: int
  #   end_ts: int
  #   ts: int
  # }

  @classmethod
  @perf_timer
  def query(cls, hostname:str=None, gpu_id:int=None, username:str=None, 
                 start_ts:int=None, end_ts:int=None, command:str=None):
    rs = [ ]
    for t in cls.objects:
      try:
        if hostname and hostname != t['hostname']: continue
        if gpu_id   and gpu_id   != t['gpu_id']:   continue
        if username and username != t['username']: continue
        if start_ts and t['start_ts'] < start_ts:  continue
        if end_ts   and end_ts < t['end_ts']:      continue
        if command  and (command not in t['command']) \
                    and (not re.match(command, t['command'])): continue
        rs.append(t)
      except: pass
    rs.sort(key=lambda t: t['start_ts'])
    return rs


##############################################################################
# utils

@perf_timer
def startup():
  logger.info(f'[startup]')

  # prewatch for fixed slaves
  reload_quota_rule()
  for sock in hp.SLAVES_SOCKET:
    registry_info[sock] = 'unknown'

  load_stdata()
  load_rtdata(globals(), prefix=__role__)

@perf_timer
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
# tasks

def heartbeat(host:str, hostname:str) -> ResponsePacket:
  # if new client
  if host not in registry_info:
    registry_info[host] = hostname
  # if already registered
  else:
    hostname_old = registry_info[host]
    # host replaced, clear old data
    if hostname_old != hostname:
      registry_info[host] = hostname
      del hardware_info[hostname_old]
      del runtime_info[hostname_old]
      del last_ACK_info[hostname_old]

  return RESPONSE.OK()

def stats_hardware(hostname:str, data:dict=None) -> ResponsePacket:
  hardware = data.get('hardware')
  if None is hardware: return RESPONSE.BAD_REQUEST()

  hardware_info[hostname] = hardware
  return RESPONSE.OK()

@with_lock(lock)
def stats_runtime(hostname:str, data:dict=None) -> ResponsePacket:
  runtime = data.get('runtime')
  if None is runtime: return RESPONSE.BAD_REQUEST()

  # sanitize history
  if hostname not in runtime_info: runtime_info[hostname] = deque()
  now_ts_freeze = now_ts()
  if 'ts' not in runtime: runtime['ts'] = now_ts_freeze    # sigil if absent
  runtime_info[hostname].append(runtime)
  while runtime_info[hostname][0]['ts'] + day_to_sec(hp.RTDATA_TRUNCATE_EXPIRE) < now_ts_freeze:
    runtime_info[hostname].popleft()

  return RESPONSE.OK()

def stats_tasks(hostname:str, data:dict=None) -> ResponsePacket:
  tasks = data.get('tasks')
  if None is tasks: return RESPONSE.BAD_REQUEST()

  now_ts_freeze = now_ts()
  for task in tasks:
    task['ts'] = now_ts_freeze          # sigil ts
    try:    TaskRecord.add(task)
    except: logger.warning(format_exc())
  return RESPONSE.OK()

def query_settings(**kwargs) -> ReplyPacket:
  kv = {k: getattr(hp, k) for k in dir(hp) if not k.startswith('__')}
  return RESPONSE.OK(data=kv)

def query_quota(**kwargs) -> ReplyPacket:
  username = kwargs.get('username')
  
  if None is username:
    return RESPONSE.OK(data=quota_info)
  elif username in quota_info:
    return RESPONSE.OK(data={username: quota_info[username]})
  else:
    return RESPONSE.NOT_ACCEPTABLE(data=make_reason('requested user not found'))

def query_hardware(**kwargs) -> ReplyPacket:
  hostname = kwargs.get('hostname')

  if None is hostname:
    return RESPONSE.OK(data=hardware_info)
  elif hostname in hardware_info:
    return RESPONSE.OK(data={hostname: hardware_info[hostname]})
  else:
    return RESPONSE.NOT_ACCEPTABLE(data=make_reason('requested host not found'))

@with_lock(lock)
def query_runtime(**kwargs) -> ReplyPacket:
  hostname = kwargs.get('hostname')
  start_ts = kwargs.get('start_ts')
  end_ts = kwargs.get('end_ts')
  
  if hostname and hostname not in hardware_info:
    return RESPONSE.NOT_ACCEPTABLE(data=make_reason('requested host not found'))

  now_ts_freeze = now_ts()
  start_ts = start_ts or (now_ts_freeze - 7*24*60*60)
  end_ts = end_ts or now_ts_freeze
  if start_ts >= end_ts:
    return RESPONSE.NOT_ACCEPTABLE(data=make_reason('start_ts should before end_ts'))

  hostnames = hostname and [hostname] or registry_info.values()
  res = { }
  for name in hostnames:
    rtdata = runtime_info.get(name)    # type(rtdata) == Deque
    if not rtdata:
      res[name] = [ ]
      continue

    # FIXME: binary search gets wrong when len(rtdata)==1, IGNORED due to not frequent
    L, R,  = 0, len(rtdata) - 1
    i = -1
    while L < R:
      i = (L + R) // 2
      if start_ts <= rtdata[i]['ts']:
        R = i
      else:
        L = i + 1

    L, R,  = 0, len(rtdata) - 1
    j = -1
    while L < R:
      j = (L + R) // 2
      if j == L: break      # NOTE: a wired fixup
      if rtdata[j]['ts'] <= end_ts:
        L = j
      else:
        R = j - 1
    
    #logger.debug(f'slice rtdata[{i}, {j}]')
    res[name] = -1 < i < j and list(islice(rtdata, i, j)) or [ ]
  return RESPONSE.OK(data=res)

def query_tasks(**kwargs) -> ReplyPacket:
  res = TaskRecord.query(hostname=kwargs.get('hostname'),
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
# services

@packet_to_dict
def impl_heartbeat(jsondata:Union[str, dict]):
  # check post data existentiality
  try:
    data = isinstance(jsondata, str) and loads(jsondata) or jsondata
    logger.debug(f'/heartbeat with {data}')
  except:
    return RESPONSE.BAD_REQUEST()

  # check data field integrity
  host = request.remote_addr
  hostname = data.get('hostname')
  _refresh_last_ACK(hostname)

  try: return heartbeat(host, hostname)
  except:
    logger.error(format_exc())
    return RESPONSE.INTERNAL_SERVER_ERROR()

@packet_to_dict
def impl_stats(jsondata:Union[str, dict]):
  # check post data existentiality
  try:
    data = isinstance(jsondata, str) and loads(jsondata) or jsondata
    logger.debug(f'/stats with {data}')
  except:
    return RESPONSE.BAD_REQUEST()
  
  # assure registered
  host = request.remote_addr
  if host not in registry_info: return RESPONSE.UNAUTHORIZED()
  hostname = registry_info[host]
  _refresh_last_ACK(hostname)

  # check data field integrity
  fn = globals().get(f'stats_{data.get("type")}')
  if not fn: return RESPONSE.BAD_REQUEST()
  try:
    return fn(hostname, data)
  except:
    logger.error(format_exc())
    return RESPONSE.INTERNAL_SERVER_ERROR()

@packet_to_dict
def impl_query(jsondata:Union[str, dict]):
  # check post data existentiality
  try:
    data = isinstance(jsondata, str) and loads(jsondata) or jsondata
    logger.debug(f'/query with {data}')
  except:
    return RESPONSE.BAD_REQUEST()

  # check data field integrity
  fn = globals().get(f'query_{data.get("type")}')
  if not fn: return RESPONSE.BAD_REQUEST()
  try:
    return fn(**data)
  except:
    logger.error(format_exc())
    return RESPONSE.INTERNAL_SERVER_ERROR()

@packet_to_dict
def impl_realloc(jsondata:Union[str, dict]):
  # check post data existentiality
  try:
    data = isinstance(jsondata, str) and loads(jsondata) or jsondata
    logger.debug(f'/realloc with {data}')
  except:
    return RESPONSE.BAD_REQUEST()
  
  try: 
    return realloc(**data)
  except:
    logger.error(format_exc())
    return RESPONSE.INTERNAL_SERVER_ERROR()


##############################################################################
# HTTP routes: jsonstr in, jsonstr out

@app.route('/', methods=['GET'])
def root():
  return html_page

@app.route('/heartbeat', methods=['POST'])
def api_heartbeat():
  return jsonify(impl_heartbeat(request.json))

@app.route('/stats', methods=['POST'])
def api_stats():
  return jsonify(impl_stats(request.json))

@app.route('/query', methods=['POST'])
def api_query():
  return jsonify(impl_query(request.json))

@app.route('/realloc', methods=['POST'])
def api_realloc():
  return jsonify(impl_realloc(request.json))


##############################################################################
# websocket events: dict in, dict out

@socketio.on('heartbeat')
def ws_heartbeat(data:dict):
  emit('heartbeat', impl_heartbeat(data))

@socketio.on('stats')
def ws_stats(data:dict):
  # reply for clients
  emit('stat', impl_stats(data))

  # reply for browsers
  # NOTE: push differetial updates to browsers!
  emit('streaming:runtime', data, broadcast=True)
  emit('streaming:tasks',   data, broadcast=True)
  emit('streaming:quota',   data, broadcast=True)

@socketio.on('query')
def ws_query(data:dict):
  q_type = data.get('type')
  if not q_type: emit(f'error', packet_to_dict(RESPONSE.BAD_REQUEST()))
  
  emit(f'query:{q_type}', impl_query(data))

@socketio.on('realloc')
def ws_realloc(data:dict):
  emit('realloc', impl_realloc(data))

@socketio.on('connect')
def ws_connect():
  logger.debug('[ws_connect]')

  uuid = gen_uuid()
  session['uuid'] = uuid
  ws_resources[uuid] = 'some stuff'

@socketio.on('disconnect')
def ws_disconnect():
  logger.debug('[ws_disconnect]')

  uuid = session['uuid']
  _ = ws_resources[uuid]
  del ws_resources[uuid]

@socketio.on_error_default
def ws_error(e):
  logger.error(f'ws_error: {e}: {format_exc()}')


##############################################################################
# main entry

if __name__ == '__main__':
  # cactch signal SIGUSR1: supports dynamic setting reloading (only works on GNU/Linux
  if hasattr(signal, 'SIGUSR1'): signal.signal(signal.SIGUSR1, reload_settings)

  init_logger(__role__)
  from utils import logger    # import again to fix non-init problem

  try:
    startup()
    logger.info(f'[server] running at {sock_to_hostport(hp.MASTER_SOCKET)}')
    host, port = '0.0.0.0', hp.MASTER_SOCKET[1]
    # app.run(host=host, port=port, debug=False)
    socketio.run(app, host=host, port=port, debug=False)
  except KeyboardInterrupt:
    logger.info('exit by Ctrl+C')
  except Exception:
    logger.error(format_exc())
  finally:
    cleanup()
