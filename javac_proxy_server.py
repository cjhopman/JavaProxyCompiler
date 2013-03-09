import optparse
import os
import subprocess
import pexpect
import sys
import time

from py4j import java_gateway
from py4j import java_collections

DEAD_SIGNAL = "-----COMPILER DIED-----"
READY_SIGNAL = "-----COMPILER READY-----"
PORT_SIGNAL = "-----PORT: ([0-9]*)-----"
COMPILE_END_SIGNAL = "-----COMPILE FINISHED-----"

class CompilerProcess(object):
  def __init__(self, port):
    self.port = port
    java_cmd = ['java', '-classpath', 'py4j0.7.jar:out', 'JavacProxyCompiler']
    self.process = pexpect.spawn(' '.join(java_cmd))
    self.process.logfile = sys.stdout

    self.Expect(READY_SIGNAL)
    match = self.Expect(PORT_SIGNAL)
    self.port = int(match.group(1))

    self.gateway_client = java_gateway.GatewayClient(port=self.port)
    self.gateway = java_gateway.JavaGateway(gateway_client=self.gateway_client)


  def Expect(self, signal):
    idx = self.process.expect([DEAD_SIGNAL, signal])
    if idx == 0:
      self.Kill('Got DEAD_SIGNAL. Expected: ' + signal)
    return self.process.match


  def Kill(self):
    raise Exception('Dead')


  def Compile(self, options, files):
    files = java_collections.ListConverter().convert(files, self.gateway._gateway_client)
    options = java_collections.ListConverter().convert(options, self.gateway._gateway_client)
    success = self.gateway.jvm.JavacProxyCompiler.compile(options, files)
    idx = self.process.expect([COMPILE_END_SIGNAL, DEAD_SIGNAL])
    if idx == 1:
      self.Kill()
      return

    print '!!!'


def main(argv):
  compiler = CompilerProcess(0)
  options = argv[1:]
  compiler.Compile(['-classpath', 'out/Jar.jar', '-d', 'out'], ['JarUse.java'])


if __name__ == '__main__':
  sys.exit(main(sys.argv))
