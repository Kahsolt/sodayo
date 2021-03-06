#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/16 

from time import sleep
from socket import gethostname
from threading import Thread, Timer, RLock
from traceback import format_exc
from flask import json

from requests import session
from requests.exceptions import RequestException
import gpustat

import settings as hp
from packets import *
from utils import *


__version__ = '0.1'     # 2021/09/18


##############################################################################
# [code layout]
#
#   Data Layer:       gloabals
#                     rtdata
#   Service Layer:    utils
#                     tasks
#   App:              daemon
#


##############################################################################
# globals

__role__ = 'client'

http = session()
lock = RLock()      # for r/w `runtime_info`
hostname = gethostname()


##############################################################################
# rtdata: 运行时数据
# NOTE: dumpable structs MUST named endswith '_info'
#       tranferable structs MUST typed in [dict, list] (aka. JSON roots)

hardware_info = {             
  'hostname': 'server1',
  'gpu': [
    {
      'gpu_id': 0, 
      'uuid': 'GPU-71b3c5d8-3c1c-0540-7b4b-883329390deb', 
      'name': 'GeForce RTX 2080 Ti', 
      'mem': 11019,              # int in MB 
    },
    {'gpu_id': 1, 'uuid': 'GPU-XXXX-xxx-fuckit', 'name': 'GeForce RTX 1040', 'mem': 6019}, 
  ],
  'cuda': 'v11.1',
  'os': 'Ubuntu 18.04.5 LTS',
  'cpu': {
    'name': 'Intel(R) Xeon(R) Silver 2008 CPU @ 1.60GHz',
    'proc_num': 16,              # processor (aka. thread) count
    'clock_speed': 3677.23       # float in MHz
  },
  'mem': 95161,             # int in MB
}

runtime_info = {            # one frame of status query
  'gpu': [
    {
      'gpu_id': 0, 
      'temp': 76,           # int in celsius
      'usage': 82,          # int in percentage
      'mem_usage': 7200,    # int in MB
      'procs': [            # this be a list, cos' someone loves high-high-stack
        {
          'username': 'nobody',
          'command': 'python nocode.py',
          'gpu_memory_usage': 132,      # int in MB
          'start_ts': 1631766896,       # int64 of timestamp
        },
      ],
    },
    {
      'gpu_id': 1, 
      'temp': 0, 
      'usage': 0, 
      'mem_usage': 0,
      'procs': [],
    },
  ],
  'loadavg': 0.25,          # float
  'cpu_usage': 75.0,        # float in percentage
  'mem_free': 12345,        # int in MB
  'ts': 1631665845,         # int64 of timestamp
}

running_tasks_info = {
  10856: {                  # key is pid
    'gpu_id': 0,
    'username': 'nobody',
    'command': 'python nocode.py',
    'start_ts': 1631766896,
  },
}


##############################################################################
# utils

@perf_timer
def startup():
  logger.info(f'[startup]')

  # clear fake demo data
  env = globals()
  for var in env:
    if var.endswith('_info') and isinstance(env[var], (list, dict)):
      env[var].clear()

  load_rtdata(globals(), prefix=__role__)

@perf_timer
def cleanup():
  logger.info(f'[cleanup]')

  dump_rtdata(globals(), prefix=__role__)


##############################################################################
# tasks

@perf_timer        # ~= 0.15s
def update_hardware_info():
  global hardware_info
  
  hardware_info['hostname'] = hostname
  
  gpu_info = None
  try:
    r = gpustat.new_query().jsonify()
    gpu_info = [ ]
    for gpu in r['gpus']:
      gpu_info.append({
        'gpu_id': gpu['index'],
        'uuid': gpu['uuid'],
        'name': gpu['name'],
        'mem': gpu['memory.total']
      })
  except: pass
  hardware_info['gpu'] = gpu_info
  
  cuda_info = None
  try:
    r = execute('nvcc --version')
    cuda_info = r[3].split(' ')[-1]
  except: pass
  hardware_info['cuda'] = cuda_info
  
  os_info = None
  try:
    r = execute('lsb_release -a 2&> /dev/null')
    os_info = r[1].split('\t')[-1]
  except: pass
  hardware_info['os'] = os_info
  
  cpu_info = None
  try:
    r = execute('lscpu')
    cpu_info = { }
    for s in r:
      if s.startswith('Model name'):
        cpu_info['name'] = s.split(':')[-1].strip()
      elif s.startswith('CPU(s)'):
        cpu_info['proc_num'] = s.split(':')[-1].strip()
      elif s.startswith('CPU MHz'): 
        cpu_info['clock_speed'] = s.split(':')[-1].strip()
  except: pass
  hardware_info['cpu'] = cpu_info
  
  mem_info = None
  try:
    r = execute('free -m')
    s = whitespace_collapse(r[1])
    mem_info = int(s.split(' ')[1])
  except: pass
  hardware_info['mem'] = mem_info

  logger.debug(hardware_info)

@perf_timer        # ~= 0.25s
@with_lock(lock)
def update_runtime_info() -> list:
  global runtime_info

  active_pids = [ ]   # collect info to return

  # collect newest
  gpu_info = None
  try:
    r = gpustat.new_query().jsonify()
    now_ts_freeze = now_ts()
    gpu_info = [ ]
    for gpu in r['gpus']:
      # collect scalar info
      gpu_info.append({
        'gpu_id': gpu['index'],
        'temp': gpu['temperature.gpu'],
        'usage': gpu['utilization.gpu'],
        'mem_usage': gpu['memory.used'],
        'procs': None,
      })

      # refine proc info
      procs = [proc for proc in gpu['processes'] if proc['username'] != 'root']   # FIXME: might we make a black/white list
      for i in range(len(procs)):
        pid = procs[i]['pid']
        del procs[i]['pid']         # for brower side security
        active_pids.append(pid)
        
        # NOTE: found new task, let's keep an eye on it !
        if pid not in running_tasks_info:
          # 'command' given by gpustat is far too brief, we make this clear if possible
          try: command = execute(f'cat /proc/{pid}/cmdline')[0].replace('\x00', ' ').strip()
          except: command = procs[i]['command']

          running_tasks_info[pid] = {
            'gpu_id': gpu['index'],
            'username': procs[i]['username'],
            'command': command,
            # NOTE: more precise impl refers to `/proc/<pid>/stat`, sed which's time costing 
            'start_ts': now_ts_freeze,   # sigil start_ts
          }

        # append 'start_ts' allowing browsers to draw out current running tasks
        procs[i]['start_ts'] = running_tasks_info[pid]['start_ts']
        procs[i]['command'] = running_tasks_info[pid]['command']
      
      gpu_info[-1]['procs'] = procs
  except: pass
  runtime_info['gpu'] = gpu_info

  loadavg_info = None
  cpu_usage_info = None
  try:
    # '-i -c' displays less lines, '-w' avoids line truncate
    r = execute('top -b -n 1 -i -c -w 512')
    loadavg_info = float(r[0].split(',')[-3].split(':')[1])
    cpu_usage_info = 100.0 - float(r[2].split(',')[-5].strip().split(' ')[0])  # = 1.0 - `idle(%)`
  except: pass
  runtime_info['loadavg'] = loadavg_info
  runtime_info['cpu_usage'] = cpu_usage_info

  mem_free_info = None
  try:
    r = execute('free -m')
    ss = whitespace_collapse(r[1]).split(' ')
    mem_free_info = int(ss[1]) - int(ss[2])    # = `total` - `used`
  except: pass
  runtime_info['mem_free'] = mem_free_info
  
  runtime_info['ts'] = now_ts()

  logger.debug(runtime_info)

  return active_pids

def check_running_tasks(active_pids:list):
  # look for finished tasks
  tasks, dead_pids = [ ], [ ]
  now_ts_freeze = now_ts()
  for pid in running_tasks_info:
    # NOTE: found finished task, let's keep an eye on it !
    if pid not in active_pids:
      tsk = running_tasks_info[pid]
      tsk['end_ts'] = now_ts_freeze     # sigil end_ts
      tsk['hostname'] = hostname
      tasks.append(tsk)
      dead_pids.append(pid)
  if tasks:
    for pid in dead_pids: del running_tasks_info[pid]
    # TODO: locally keep a copy in case of long time network failure ?
    # tasks info upload MUST be success ...
    _post('stats', StatsPacket(type='tasks', tasks=tasks), retry_status_ok=-1)

def heartbeat_task(cli):
  if hp.HERATBEAT_INTERVAL == -1: return
  logger.info('[heartbeat_task]')

  _post('heartbeat', HeartbeatPacket())

  cli.heartbeat_timer = Timer(hp.HERATBEAT_INTERVAL, heartbeat_task, (cli,))
  cli.heartbeat_timer.start()

def update_task(cli):
  logger.info('[update_task]')
  
  active_pids = update_runtime_info()
  if active_pids:
    thr = Thread(target=check_running_tasks, args=(active_pids,))
    thr.daemon = True       # FIXME: data will be lost if client crashed or got SIGINT
    thr.start()

  cli.update_timer = Timer(hp.UPDATE_INTERVAL, update_task, (cli,))
  cli.update_timer.start()

@with_lock(lock)
def commit_task(cli):
  logger.info('[commit_task]')

  _post('stats', StatsPacket(type='runtime', runtime=runtime_info))

  cli.commit_timer = Timer(hp.COMMIT_INTERVAL, commit_task, (cli,))
  cli.commit_timer.start()

@perf_timer        # ~= 0.1s
def coredump_task(cli):
  logger.info('[coredump_task]')

  dump_rtdata(globals(), prefix=__role__)

  cli.coredump_timer = Timer(min_to_sec(hp.COREDUMP_INTERVAL), coredump_task, (cli,))
  cli.coredump_timer.start()

def _post(api:str, packet:Packet, retry_http=5, retry_status_ok=1):
  url = f'http://{sock_to_hostport(hp.MASTER_SOCKET)}/{api}'
  jsondata = json.dumps(packet_to_dict(packet), ensure_ascii=False)
  HEADERS =  { 'User-Agent': 'sodayo-client' }
  
  def _try_post():
    for _ in range(retry_http):
      try:
        logger.debug(f'[post] {url} with {jsondata}')
        return http.post(url=url, headers=HEADERS, json=jsondata, timeout=30)
      except RequestException: logger.error(format_exc())
      except Exception as e:   raise e
      sleep(hp.COMMIT_INTERVAL // 2)

  retrial = retry_status_ok
  while retrial != 0:
    if retry_status_ok != -1: retrial -= 1
    res = _try_post()
    try:
      status_code = res.json().get('status_code')
      ok = res and (status_code == 200)
      if ok: return res
      logger.warning(f'[post] request not ok {status_code}: {res.json().get("reason")}')
    except:
      logger.error(format_exc())
    sleep(hp.COMMIT_INTERVAL)


##############################################################################
# daemon

class Client:

  def __init__(self):
    # NOTE: names of timers MUST endswith '_timer'
    self.heartbeat_timer  = Timer(hp.UPDATE_INTERVAL, heartbeat_task, (self,))
    self.update_timer     = Timer(0,                  update_task,    (self,))
    self.commit_timer     = Timer(hp.UPDATE_INTERVAL, commit_task,    (self,))
    self.coredump_timer   = Timer(hp.COMMIT_INTERVAL, coredump_task,  (self,))
  
  def start(self):
    # first heartbeat MUST be success for register
    _post('heartbeat', HeartbeatPacket(hostname=hostname), retry_status_ok=-1)

    # hardware SHOULD be success
    update_hardware_info()
    _post('stats', StatsPacket(type='hardware', hardware=hardware_info), retry_status_ok=100)

    # now other timers can be started
    for var in dir(self):
      if var.endswith('_timer'):
        timer = getattr(self, var)
        if isinstance(timer, Timer):
          timer.start()

  def stop(self):
    for var in dir(self):
      if var.endswith('_timer'):
        timer = getattr(self, var)
        if isinstance(timer, Timer):
          timer.cancel()


##############################################################################
# main entry

if __name__ == '__main__':
  init_logger(__role__)
  from utils import logger    # import again to fix non-init problem
  
  cli = Client()
  try:
    startup()
    cli.start()
    # we hang up main thread in case those timers gets QingHuangBuJie :(
    while True: sleep(hp.COMMIT_INTERVAL * 1000)
  except KeyboardInterrupt:
    logger.info('exit by Ctrl+C')
  except Exception:
    logger.error(format_exc())
  finally:
    cli.stop()
    cleanup()
