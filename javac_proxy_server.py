import optparse
import os
import subprocess
import pexpect
import sys
import time

from py4j.java_gateway import JavaGateway
from py4j.java_collections import ListConverter

COMPILE_END_SIGNAL = "-----COMPILE FINISHED-----"
READY_SIGNAL = "-----COMPILER READY-----"
DEAD_SIGNAL = "-----COMPILER DIED-----"

class CompilerProcess(object):
  def __init__(self, port):
    self.port = port
    java_cmd = ['java', '-classpath', 'py4j0.7.jar:out', 'JavacProxyCompiler']
    self.process = pexpect.spawn(' '.join(java_cmd))
    self.process.logfile = sys.stdout
    self.ready = False

  def WaitForReady(self):
    idx = self.process.expect([READY_SIGNAL, DEAD_SIGNAL])
    if idx == 1:
      self.Kill()

  def Kill(self):
    raise Exception('Dead')

  def SanityCheck(self):
    pass


  def Compile(self, options, files):
    self.WaitForReady()
    self.SanityCheck()
    files = ListConverter().convert(files, self.gateway._gateway_client)
    options = ListConverter().convert(options)
    success = gateway.jvm.JavacProxyCompiler.compile(options, files)
    while True:
      output = self.process.stdout.readline()
      if output == COMPILE_END_SIGNAL:
        break
      print output
    print self.process.stdout.read()
    print success


def main(argv):
  compiler = CompilerProcess(0)
  compiler.Compile(['-classpath', 'out/Jar.jar'], ['JarUse.java'])
  compiler.compile()


if __name__ == '__main__':
  sys.exit(main(sys.argv))
