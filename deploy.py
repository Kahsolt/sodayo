#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/18 

import os
import sys
from argparse import ArgumentParser

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sodayo'))


def deploy_one(host, port, role):
  pass


def deploy_all():
  pass


if __name__ == '__main__':
  parser = ArgumentParser()
  parser.add_argument('--all', action='store_true')
  parser.add_argument('--host', type=str, default='127.0.0.1')
  parser.add_argument('--port', type=int, default=2333)
  parser.add_argument('--role', type=str, default='client')
  args = parser.parse_args()

  if args.all: deploy_all()
  else:        deploy_one(args.host, args.port, args.role)
