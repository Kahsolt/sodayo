#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/16 

from dataclasses import dataclass, asdict
from types import FunctionType
from typing import Dict, List, Union

from utils import now_ts


@dataclass
class Packet:

  ts: int = None


@dataclass
class HeartbeatPacket(Packet):

  hostname: str = None


@dataclass
class StatsPacket(Packet):

  type: str = None

  # type == 'hardware'
  # NOTE: struct of `client.hardware_info`
  hardware: Dict = None

  # type == 'runtime'
  # NOTE: struct of `client.runtime_current_info`
  runtime: Dict = None

  # type == 'tasks'
  # NOTE: list of struct of `client.running_tasks_info.value`
  tasks: List[dict] = None


@dataclass
class QueryPacket(Packet):

  type: str = None

  # type == 'setting'

  # type == 'hardware'
  hostname: str = None

  # type == 'quota'
  username: str = None

  # type == 'runtime'
  start_ts: int = None
  end_ts: int = None

  # type == 'task'
  username: str = None
  command: str = None
  start_ts: int = None
  end_ts: int = None


@dataclass
class ReallocPacket(Packet):

  username: str = None
  password: str = None
  gpu_cnt: int = None


@dataclass
class ResponsePacket(Packet):

  status_code: int = None
  reason: str = None


@dataclass
class ReplyPacket(ResponsePacket):

  data: Union[List, Dict] = None


# short hand factory for ResponsePackets
class RESPONSE:

  OK =             lambda data=None: ReplyPacket(status_code=200, reason='OK', ts=now_ts(), data=data)
  BAD_REQUEST =           lambda: ResponsePacket(status_code=400, reason='Bad Request', ts=now_ts())
  UNAUTHORIZED =          lambda: ResponsePacket(status_code=401, reason='Unauthorized', ts=now_ts())
  NOT_ACCEPTABLE = lambda data=None: ReplyPacket(status_code=406, reason='Not Acceptable', ts=now_ts(), data=data)
  INTERNAL_SERVER_ERROR = lambda: ResponsePacket(status_code=500, reason='Internal Server Error', ts=now_ts())
  NOT_IMPLEMENTED =       lambda: ResponsePacket(status_code=501, reason='Not Implemented', ts=now_ts())


# packet optimize
def dict_remove_nullval(d:dict) -> dict:
  ks = [k for k, v in d.items() if v is None]
  for k in ks: del d[k]
  return d

def packet_to_dict(packet:Union[Packet, FunctionType]) -> dict:
  if isinstance(packet, Packet):
    return dict_remove_nullval(asdict(packet))
  elif isinstance(packet, FunctionType):
    def wrapper(*args, **kwargs):
      return packet_to_dict(packet(*args, **kwargs))
    return wrapper
  else: raise ValueError

def make_reason(reason:str) -> dict:
  return {'reason': reason}
