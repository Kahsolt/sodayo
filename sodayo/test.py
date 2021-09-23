#!/usr/bin/env python3
# Author: Armit
# Create Time: 2021/09/18 

# I only write scripts free of bugs :)
# tests are leaving for you to confirm of. 


from json import dumps
from requests import session

import settings as hp
from packets import *
from sodayo.utils import sock_to_hostport


API_BASE = f'http://{sock_to_hostport(hp.MASTER_SOCKET)}'


def assert_recode(resp, retcode=200):
  try:
    assert resp.json().get('status_code') == retcode 
    print('>> ok')
  except:
    print('<< failed')


def test_server():
  http = session()

  data = {
    'hostname': 'nohost',
  }
  r = http.post('/heartbeat', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'hardware',
    'hardware': {
      'gpu': [
        { 'gpu_id': 0 }
      ]
    }
  }
  r = http.post('/stats', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'runtime',
    'runtime': {
      
    }
  }
  r = http.post('/stats', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'tasks',
    'tasks': [
      {

      }
    ]
  }
  r = http.post('/stats', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'settings',
  }
  r = http.post('/query', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'quota',
  }
  r = http.post('/query', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'hardware',
  }
  r = http.post('/query', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'runtime',
  }
  r = http.post('/query', json=dumps(data))
  assert_recode(r)

  data = {
    'type': 'tasks',
  }
  r = http.post('/query', json=dumps(data))
  assert_recode(r)

  data = {
    'username': 'nobody',
    'password': 'nopwd',
    'gpu_count': 1,
  }
  r = http.post('/realloc', json=dumps(data))
  assert_recode(r)


if __name__ == '__main__':
  test_server()
