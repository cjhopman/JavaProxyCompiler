import optparse
import os
import subprocess
import pexpect
import pickle
import socket
import sys
import time

from py4j import java_gateway
from py4j import java_collections

DEAD_SIGNAL = '-----COMPILER DIED-----'
READY_SIGNAL = '-----COMPILER READY-----'
PORT_SIGNAL = '-----PORT: ([0-9]*)-----'
SOCKET_SIGNAL = '-----SOCKET: %s-----'
SOCKET_SIGNAL_RE = '-----SOCKET: (\0[a-zA-Z0-9_]*)-----'
COMPILE_END_SIGNAL = '-----COMPILE FINISHED-----'

CLIENT_SOCKET_NAME = '\0javac_proxy_client_'
SERVER_SOCKET_NAME = '\0javac_proxy_server'
COMPILER_SOCKET_NAME = '\0javac_proxy_compiler_'

def TimeIt(func):
  def wrapper(*arg):
    t1 = time.time()
    res = func(*arg)
    t2 = time.time()
    print '%s took %0.3f ms' % (func.func_name, (t2 - t1) * 1000.0)
    return res
  return wrapper


class SimpleSocket(object):
  def __init__(self):
    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)


  def Listen(self, name):
    self.sock.bind(name)
    self.sock.setblocking(1)
    self.sock.listen(5)


  def Accept(self, timeout=None):
    self.sock.settimeout(timeout)
    connection, _ = self.sock.accept()
    try:
      client_data = ''
      while True:
        data = connection.recv(4096)
        if data:
          client_data += data
        else:
          break
      return pickle.loads(client_data)
    finally:
      connection.close()


  def Send(self, name, message):
    self.sock.connect(name)
    try:
      self.sock.sendall(pickle.dumps(message))
    finally:
      self.sock.close()


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

  def WarmUp(self):
    self.Compile(['-d', 'out', 'WarmUp.java'])


  @TimeIt
  def Compile(self, args, return_socket_name=None):
    idx = len(args)
    while idx > 0 and args[idx - 1].endswith('.java'):
      idx -= 1
    files = args[idx:]
    options = args[:idx]

    files = java_collections.ListConverter().convert(files, self.gateway._gateway_client)
    options = java_collections.ListConverter().convert(options, self.gateway._gateway_client)
    results = self.gateway.jvm.JavacProxyCompiler.compile(options, files)
    self.Expect(COMPILE_END_SIGNAL)

    if return_socket_name:
      return_sock = SimpleSocket()
      return_sock.Send(return_socket_name, (results.output(), 'stderr', results.success()))


def RunCompiler():
  compiler = CompilerProcess(0)
  compiler.WarmUp()

  socket_name = COMPILER_SOCKET_NAME + str(os.getpid())
  sock = SimpleSocket()
  sock.Listen(socket_name)
  print SOCKET_SIGNAL % socket_name
  while True:
    (return_socket, args) = sock.Accept()
    SimpleSocket().Send(return_socket, 'compiler_compile_ack')
    compiler.Compile(args, return_socket)


def RunServer():
  compiler_process = pexpect.spawn('python javac_proxy_server.py _run_compiler')
  compiler_process.logfile = sys.stdout
  compiler_process.expect(SOCKET_SIGNAL_RE)
  compiler_socket_name = compiler_process.match.group(1)

  sock = SimpleSocket()
  sock.Listen(SERVER_SOCKET_NAME)
  while True:
    (command, data) = sock.Accept()
    if command == 'kill':
      return
    if command == 'compile':
      (return_socket, _) = data
      SimpleSocket().Send(return_socket, 'server_compile_ack')
      SimpleSocket().Send(compiler_socket_name, data)
    if command == 'ping':
      SimpleSocket().Send(data, 'pong')


def StartCompilerProxy():
  pass


def KillCompilerProxy():
  pass

def PrintHelp():
  pass

def Compile(argv):
  response_sock = SimpleSocket()
  response_name = CLIENT_SOCKET_NAME + str(os.getpid())
  response_sock.Listen(response_name)

  SimpleSocket().Send(SERVER_SOCKET_NAME, ('compile', (response_name, argv[2:])))
  server_ack = response_sock.Accept(1.0)
  compiler_ack = response_sock.Accept(1.0)
  print server_ack, compiler_ack

  (stdout, stderr, success) = response_sock.Accept()
  if stdout:
    print stdout

  return 0 if success else 1

def main(argv):
  if len(argv) < 1:
    PrintHelp()
    return 0

  command = argv[1]

  if command == '_run_compiler':
    RunCompiler()

  if command == '_run_server':
    RunServer()

  if command == 'kill':
    KillCompilerProxy()

  if command == 'start':
    StartCompilerProxy()

  if command == 'compile':
    Compile(argv)


if __name__ == '__main__':
  sys.exit(main(sys.argv))
