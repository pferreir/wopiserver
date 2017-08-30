#!/usr/bin/python
'''
wopi_grafana_feeder.py

A daemon pushing CERNBox WOPI monitoring data to Grafana.
TODO: make it a collectd plugin. References:
https://collectd.org/documentation/manpages/collectd-python.5.shtml
https://blog.dbrgn.ch/2017/3/10/write-a-collectd-python-plugin/
https://github.com/dbrgn/collectd-python-plugins

author: Giuseppe.LoPresti@cern.ch
CERN/IT-ST
'''

import fileinput
import socket
import time
import pickle
import struct
import datetime

CARBON_HOST = 'filer-carbon.cern.ch'
CARBON_TCPPORT = 2004
prefix = 'cernbox.wopi'
epoch = datetime.datetime(1970, 1, 1)

def send_metric(data):
  payload = pickle.dumps(data, protocol=2)
  header = struct.pack("!L", len(payload))
  message = header + payload
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.connect((CARBON_HOST, CARBON_TCPPORT))
  sock.sendall(message)
  sock.close()

# WOPI usage metrics
def get_wopi_metrics(data):
  for line in data:
    if data.isfirstline():
      logdate = line.split('T')[0].split('-')    # keeps the date until 'T', splits
      timestamp = (datetime.datetime(int(logdate[0]), int(logdate[1]), int(logdate[2])) - epoch).total_seconds() + time.altzone
      errors = 0
      users = {}
      openfiles = {}
      openfiles['docx'] = {}
      openfiles['xlsx'] = {}
      openfiles['pptx'] = {}
      openfiles['one'] = {}
      wrfiles = {}
      wrfiles['docx'] = {}
      wrfiles['xlsx'] = {}
      wrfiles['pptx'] = {}
      wrfiles['one'] = {}
      collab = 0
    try:
      if ' ERROR ' in line:
        errors += 1
      # all opened files
      elif 'CheckFileInfo' in line:
        # count of unique users
        l = line.split()
        u = l[4].split('=')[1]
        if u in users.keys():
          users[u] += 1
        else:
          users[u] = 1
        # count of open files per type: look for the file extension
        fname = line[line.find('filename=')+10:line.rfind('fileid=')-2]
        fext = fname[fname.rfind('.')+1:]
        if fext not in openfiles:
          openfiles[fext] = {}
        if fname in openfiles[fext]:
          openfiles[fext][fname] += 1
        else:
          openfiles[fext][fname] = 1
      # files opened for write
      elif 'successfully written' in line:
        # count of written files
        fname = line[line.find('filename=')+10:-2]
        fext = fname[fname.rfind('.')+1:]
        if fname in wrfiles[fext]:
          wrfiles[fext][fname] += 1
        else:
          wrfiles[fext][fname] = 1
      # collaborative editing sessions
      elif 'Collaborative' in line:
        collab += 1
        # we could extract the filename and the users list for further statistics
    except Exception:
      print 'Error occurred at line: %s' % line
      raise

  if 'timestamp' not in locals():
    # the file was empty, nothing to do
    return
  # prepare data for grafana
  output = []
  output.append(( prefix + '.errors', (int(timestamp), errors) ))
  output.append(( prefix + '.users', (int(timestamp), len(users)) ))
  # get the top user by sorting the users dict by values instead of by keys
  if len(users) > 0:
    top = sorted(users.iteritems(), key=lambda (k, v): (v, k))[-1][1]
    output.append(( prefix + '.topuser', (int(timestamp), int(top)) ))
  for fext in openfiles:
    output.append(( prefix + '.openfiles.' + fext, (int(timestamp), len(openfiles[fext])) ))
  for fext in wrfiles:
    output.append(( prefix + '.writtenfiles.' + fext, (int(timestamp), len(wrfiles[fext])) ))
  output.append(( prefix + '.collab', (int(timestamp), collab) ))
  # print and send all collected data
  send_metric(output)
  print output

if __name__ == '__main__':
  get_wopi_metrics(fileinput.input())
