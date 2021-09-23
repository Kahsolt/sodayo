#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/16 

import os
import sys
from runpy import run_module
from argparse import ArgumentParser
from traceback import print_exc

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sodayo'))


def run(modname):
  run_name = modname.replace(".", "-")

  # check privileges
  ok = os.access('/run', os.W_OK)
  if ok: pid_fp = f'/run/{run_name}.pid'
  else:  pid_fp = f'{run_name}.pid'

  # check pid file
  if os.path.exists(pid_fp):
    with open(pid_fp) as fh:
      pid = fh.read().strip()
    if os.path.exists(f'/proc/{pid}'):
      print(f'{run_name} already running at pid = {pid}!')
      exit(-2)
  
  # create pid file
  pid = os.getpid()
  try:
    with open(pid_fp, 'w') as fh:
      fh.write(str(pid))
  except:
    print_exc()
    exit(-3)

  # gogogo!
  run_module(modname, run_name='__main__')

  # TODO:
  # p = popen(modname)
  # with Timer.new(DEAD_REVIVE_INTERVAL) as t:
  #   if p.is_dead():
  #     p = popen(modname)
  #   else:
  #     t.reset()

  # clean pid file
  if os.path.exists(pid_fp):
    os.unlink(pid_fp)


if __name__ == '__main__':
  parser = ArgumentParser()
  parser.add_argument('--server', action='store_true')
  parser.add_argument('--client', action='store_true')
  args = parser.parse_args()

  run(args.server and 'sodayo.server' or 'sodayo.client')
