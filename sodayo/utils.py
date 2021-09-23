#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/16 

import os
import re
import logging
from shutil import copy2
from logging.handlers import TimedRotatingFileHandler
from time import time
from datetime import datetime
from threading import RLock
from collections import deque
import lzma
import pickle as pkl
from importlib import reload as reload_module
from typing import List, Tuple
from traceback import format_exc

import settings as hp


##############################################################################
# NOTE: utils are designed to be shared by server & clients
#       not always general purposed, may not be decoupled ...
#
# [section layout]
#
#   logging
#   datetime
#   string
#   socket
#   data file read/write
#   shell execute            (general purpose)
#   decorators               (general purpose)
#   private callback         (special)
#


# logging
LONG_LOGFMT  = logging.Formatter("%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s")
SHORT_LOGFMT = logging.Formatter("[%(levelname)s] %(filename)s:%(lineno)s %(message)s")
logger = None

def init_logger(endpoint:str='client'):
  global logger

  if endpoint not in ['client', 'server']: raise ValueError

  os.makedirs(hp.LOG_PATH, exist_ok=True)

  logger = logging.getLogger(f'sodayo-{endpoint}')
  logger.setLevel(level=logging.DEBUG)

  lf = TimedRotatingFileHandler(os.path.join(hp.LOG_PATH, f'{endpoint}-error.log'), encoding='utf8',
                                when='D', interval=30, backupCount=3)
  lf.setFormatter(LONG_LOGFMT)
  lf.setLevel(logging.WARN)
  logger.addHandler(lf)

  if hp.ENABLE_ACCESS_LOG:
    lf = TimedRotatingFileHandler(os.path.join(hp.LOG_PATH, f'{endpoint}-access.log'), encoding='utf8',
                                  when='D', interval=7, backupCount=10)
    lf.setFormatter(LONG_LOGFMT)
    lf.setLevel(logging.INFO)
    logger.addHandler(lf)

  if hp.DEBUG_MODE:
    con = logging.StreamHandler()
    con.setFormatter(SHORT_LOGFMT)
    con.setLevel(logging.DEBUG)
    logger.addHandler(con)


# datetime
TIME_FORMAT_STR = '%Y-%m-%d %H:%M:%S'

now_iso     = lambda: datetime.now().strftime(TIME_FORMAT_STR)
now_ts      = lambda: int(datetime.timestamp(datetime.now()))

min_to_sec  = lambda x: x * 60
hour_to_sec = lambda x: x * 60 * 60
day_to_sec  = lambda x: x * 60 * 60 * 24

def iso_to_ts(time_iso:str) -> int:
  return int(datetime.timestamp(datetime.fromisoformat(time_iso)))

def ts_to_iso(time_ts:int) -> str:
  return datetime.fromtimestamp(time_ts).strftime(TIME_FORMAT_STR)


# string
WHITESPACE_REGEX = re.compile(r'\s+')

def whitespace_collapse(s:str) -> str:
  return WHITESPACE_REGEX.sub(' ', s)


# socket
def sock_to_hostport(sock:Tuple[str, int]) -> str:
  return f'{sock[0]}:{sock[1]}'


# data file read/write
DUMPABLE_TYPES = (list, dict, set, deque)

class Record:                 # interface for stdata record classes

  # db_file:str = None        # auto set by metaclass
  objects: List[dict] = [ ]   # NOTE: length truncated by `STDATA_TRUNCATE_EXPIRE`
  
  @classmethod
  def load(cls):
    try:
      if os.path.exists(cls.db_file):
        cls.objects = load_pkl(cls.db_file)
        logger.debug(f'   load {cls.db_file}')
    except Exception:
      logger.error(format_exc())

  @classmethod
  def save(cls):
    try:
      save_pkl(cls.objects, cls.db_file)
      logger.debug(f'   dump {cls.db_file}')
    except Exception:
      logger.error(format_exc())

  @classmethod
  def add(cls, obj:dict):
    cls.objects.append(obj)

class RecordMeta(type):       # metaclass for stdata record classes
  
  objects = set()             # save regitered record classes

  def __init__(cls:type, name, bases, _dict):
    super().__init__(name, bases, _dict)
    RecordMeta.objects.add(cls)

    # FIXME: currently we only consider persist stdata at server side, so filename without prefix
    os.makedirs(hp.DATA_PATH, exist_ok=True)
    setattr(cls, 'db_file', os.path.join(hp.DATA_PATH, f'{name}.pkl'))

def load_pkl(fp:str) -> object:
  try:
    with lzma.open(fp, 'rb') as fh:
      return pkl.load(fh)
  except Exception as e:
    copy2(fp, f'{fp}.corrupted-{now_iso()}')
    raise e

def save_pkl(obj:object, fp:str):
  with lzma.open(fp, 'wb') as fh:
    pkl.dump(obj, fh)

def load_rtdata(env:dict, prefix:str):
  logger.debug('[load_rtdata]')

  os.makedirs(hp.DATA_PATH, exist_ok=True)
  try:
    for var in env:
      if var.endswith('_info') and isinstance(env[var], DUMPABLE_TYPES):
        fp = os.path.join(hp.DATA_PATH, f'{prefix}-{var}.pkl')
        if os.path.exists(fp):
          env[var] = load_pkl(fp)
          logger.debug(f'   load {fp}')
  except:
    logger.fatal(format_exc())
    exit(-1)

def dump_rtdata(env:dict, prefix:str):
  logger.debug('[dump_rtdata]')

  try:
    for var in env:
      if var.endswith('_info') and isinstance(env[var], DUMPABLE_TYPES):
        fp = os.path.join(hp.DATA_PATH, f'{prefix}-{var}.pkl')
        save_pkl(env[var], fp)
        logger.debug(f'   dump {fp}')
  except:
    logger.error(format_exc())

def load_stdata():
  logger.debug('[load_stdata]')

  try:
    for rec in RecordMeta.objects:
      rec.load()
  except:
    logger.fatal(format_exc())
    exit(-1)

def dump_stdata():
  logger.debug('[dump_stdata]')
  
  try:
    for rec in RecordMeta.objects:
      rec.save()
  except:
    logger.fatal(format_exc())
    exit(-1)

# shell execute
def execute(cmd:str) -> List[str]:
  rs = [ ]  
  for line in os.popen(cmd).read().split('\n'):
    ln = line.strip()
    if ln: rs.append(ln)
  return rs


# decorators
def perf_timer(fn):
  def wrapper(*args, **kwargs):
    start = time()
    r = fn(*args, **kwargs)
    end = time()
    logger.debug(f'[{fn.__name__}]: perf_timer {end - start:.4f}s')
    return r
  return wrapper

def with_lock(lock:RLock):
  def wrapper(fn):
    def wrapper(*args, **kwargs):
      lock.acquire()
      r = fn(*args, **kwargs)
      lock.release()
      return r
    return wrapper
  return wrapper


# ugly callback, used by `server.reload_settings`
def _reload_settings():
  global hp

  hp = reload_module(hp)
