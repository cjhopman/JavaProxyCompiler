import atexit
import collections
import optparse
import os
import pexpect
import pickle
import socket
import sys
import time
import traceback

from py4j import java_gateway
from py4j import java_collections

DEAD_SIGNAL = '-----COMPILER DIED-----'
READY_SIGNAL = '-----COMPILER READY-----'
PROXY_READY_SIGNAL = '-----PROXY READY-----'
PORT_SIGNAL = '-----PORT: ([0-9]*)-----'
SOCKET_SIGNAL = '-----SOCKET: %s-----'
SOCKET_SIGNAL_RE = '-----SOCKET: (\0[a-zA-Z0-9_]*)-----'
COMPILE_END_SIGNAL = '-----COMPILE FINISHED-----'

CLIENT_SOCKET_NAME = '\0javac_proxy_client_'
SERVER_SOCKET_NAME = '\0javac_proxy_server'
COMPILER_SOCKET_NAME = '\0javac_proxy_compiler_'

MIN_READY_COMPILERS = 8

is_server = False

class Log(object):
  @staticmethod
  def Debug(message):
    return
    print message
    if not is_server:
      SimpleSocket().Send(SERVER_SOCKET_NAME, PrintMessage(message))


class SimpleMessage(object):
  def __init__(self, command, return_socket=None):
    self.command = command
    self.return_socket = return_socket

  def Handle(self, handlers):
    raise Exception('Invalid Message')


class CompileMessage(SimpleMessage):
  def __init__(self, return_socket=None, cwd=None, args=None):
    SimpleMessage.__init__(self, 'compile', return_socket)
    self.cwd = cwd
    self.args = args

  def Handle(self, handlers):
    return handlers.Compile(self)


class CompilerFinishedMessage(SimpleMessage):
  def __init__(self, compiler_id, output=None):
    SimpleMessage.__init__(self, 'compiler_finished', None)
    self.compiler_id = compiler_id
    self.output = output

  def Handle(self, handlers):
    return handlers.CompilerFinished(self)


class CompileResultsMessage(SimpleMessage):
  def __init__(self, output=None, return_code=1):
    SimpleMessage.__init__(self, 'compile_results', None)
    self.output = output
    self.return_code = return_code

  def Handle(self, handlers):
    return handlers.CompileResults(self)


class AckMessage(SimpleMessage):
  def __init__(self, name):
    SimpleMessage.__init__(self, 'ack', None)
    self.name = name

  def Handle(self, handlers):
    return handlers.Ack(self)

class KillMessage(SimpleMessage):
  def Handle(self, handlers):
    return handlers.Kill(self)


class PrintMessage(SimpleMessage):
  def __init__(self, message):
    self.message = message

  def Handle(self, handlers):
    return handlers.Print(self)


class SimpleHandlers(object):
  def Ack(self, message):
    pass

  def Ping(self, message):
    SimpleSocket().Send(message.return_socket, AckMessage('pong'))

  def Print(self, message):
    print message.message

  def Kill(self, message):
    Log.Debug('Received kill message from: %s' % message.return_socket)
    sys.exit(1)



class SimpleSocket(object):
  def __init__(self):
    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

  def Listen(self, name):
    self.sock.bind(name)
    self.sock.setblocking(1)
    self.sock.listen(5)

  def Accept(self, handlers=SimpleHandlers(), timeout=None):
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
    finally:
      connection.close()

    message = pickle.loads(client_data)
    return message.Handle(handlers)

  def Send(self, name, message):
    self.sock.connect(name)
    try:
      self.sock.sendall(pickle.dumps(message))
    finally:
      self.sock.close()

  def Respond(self, message, response):
    if not message.return_socket:
      return
    self.Send(message.return_socket, response)

def Closer(process):
  def Func():
    process.terminate()
  return Func

def Spawn(*args, **kwargs):
  child = pexpect.spawn(*args, **kwargs)
  atexit.register(Closer(child))
  return child

class CompilerInstance(object):
  def __init__(self, id):
    self.id = id
    java_cmd = ['java', '-classpath', 'py4j0.7.jar:out:/usr/lib/jvm/java-6-sun/lib/tools.jar', 'JavacProxyCompiler']
    self.process = Spawn(' '.join(java_cmd))
    self.process.logfile = sys.stdout

    self._Expect(READY_SIGNAL)
    match = self._Expect(PORT_SIGNAL)
    self.port = int(match.group(1))

    self.gateway_client = java_gateway.GatewayClient(port=self.port)
    self.gateway = java_gateway.JavaGateway(gateway_client=self.gateway_client)

  def _Expect(self, signal):
    idx = self.process.expect([DEAD_SIGNAL, signal])
    if idx == 0:
      self.Kill('Got DEAD_SIGNAL. Expected: ' + signal)
    return self.process.match

  def Kill(self):
    raise Exception('Dead')

  def Compile(self, message):
    args = java_collections.ListConverter().convert(message.args, self.gateway._gateway_client)
    results = self.gateway.jvm.JavacProxyCompiler.compile(args, message.cwd)
    self._Expect(COMPILE_END_SIGNAL)
    return (results.output(), results.returnCode())


class CompilerHandlers(SimpleHandlers):
  def __init__(self, compiler):
    SimpleHandlers.__init__(self)
    self.compiler = compiler

  def Compile(self, message):
    SimpleSocket().Respond(message, AckMessage('compiler_compile'))
    response = CompileResultsMessage()
    try:
      #SimpleSocket().Respond(message, PrintMessage('Trying to compile...'))
      #SimpleSocket().Respond(message, PrintMessage(message.cwd))
      (response.output, response.return_code) = self.compiler.Compile(message)
      SimpleSocket().Respond(message, response)
      SimpleSocket().Send(SERVER_SOCKET_NAME, CompilerFinishedMessage(self.compiler.id))
    except:
      stacktrace = traceback.format_exc()
      SimpleSocket().Send(SERVER_SOCKET_NAME, PrintMessage(stacktrace))
      SimpleSocket().Respond(message, PrintMessage(stacktrace))
      sys.exit(1)


def RunCompiler(compiler_id):
  compiler = CompilerInstance(compiler_id)
  socket_name = COMPILER_SOCKET_NAME + str(os.getpid())
  sock = SimpleSocket()
  sock.Listen(socket_name)
  print SOCKET_SIGNAL % socket_name

  try:
    while True:
      sock.Accept(CompilerHandlers(compiler))
  except:
    stacktrace = traceback.format_exc()
    SimpleSocket().Send(SERVER_SOCKET_NAME, PrintMessage(stacktrace))
    sys.exit(1)



compilers = {}
next_compiler_id = 0

def CompilerId():
  global next_compiler_id
  ret = next_compiler_id
  next_compiler_id += 1
  return str(ret)

class CompilerProcess(object):
  def __init__(self):
    self.id = CompilerId()
    self.process = Spawn('python javac_proxy_server.py _run_compiler ' + self.id)
    self.process.logfile = sys.stdout
    self.process.expect(SOCKET_SIGNAL_RE)
    self.socket_name = self.process.match.group(1)
    compilers[self.id] = self

  def Compile(self, message):
    SimpleSocket().Send(self.socket_name, message)


ready_compilers = collections.deque()
warming_compilers = set()

def Compile(message):
  if ready_compilers:
    compiler = ready_compilers.popleft()
  else:
    compiler = CompilerProcess()

  compiler.Compile(message)

def RefreshCompilers():
  while ShouldSpinUpCompiler():
    SpinUpCompiler()

def ShouldSpinUpCompiler():
  return len(ready_compilers) + len(warming_compilers) < MIN_READY_COMPILERS

def SpinUpCompiler():
  WarmUpCompiler(CompilerProcess())

def WarmUpCompiler(compiler):
  warming_compilers.add(compiler.id)
  message = CompileMessage(args=['-d', 'out', 'WarmUp.java'], cwd=os.getcwd())
  compiler.Compile(message)

def CompilerFinished(compiler_id):
  print 'Compiler Finished: ' + compiler_id
  ready_compilers.appendleft(compilers[compiler_id])
  if compiler_id in warming_compilers:
    warming_compilers.remove(compiler_id)


class ServerHandlers(SimpleHandlers):
  def CompilerFinished(self, message):
    CompilerFinished(message.compiler_id)

  def Compile(self, message):
    SimpleSocket().Respond(message, AckMessage('server_compile'))
    Compile(message)

  def Kill(self, message):
    SimpleSocket().Respond(message, AckMessage('server_kill'))
    raise Exception('killing')


def RunServer():
  global is_server
  is_server = True
  sock = SimpleSocket()
  sock.Listen(SERVER_SOCKET_NAME)
  RefreshCompilers()
  while True:
    message = sock.Accept(ServerHandlers())
    RefreshCompilers()


def StartServer():
  pass


def KillServer():
  sock = SimpleSocket()
  socket_name = CLIENT_SOCKET_NAME + str(os.getpid())
  sock.Listen(socket_name)

  SimpleSocket().Send(SERVER_SOCKET_NAME, KillMessage(socket_name))
  sock.Accept(SimpleHandlers())
  print 'Server killed'


def RestartServer():
  pass

def PrintHelp():
  pass

class ClientHandlers(SimpleHandlers):
  def CompileResults(self, message):
    if message.output:
      print message.output
    sys.exit(message.return_code)

# Actual client
def ClientCompile(argv):
  response_sock = SimpleSocket()
  response_name = CLIENT_SOCKET_NAME + str(os.getpid())
  response_sock.Listen(response_name)

  message = CompileMessage(return_socket=response_name, args=argv[2:], cwd=os.getcwd())
  SimpleSocket().Send(SERVER_SOCKET_NAME, message)
  message_handlers = ClientHandlers()

  while True:
    response_sock.Accept(message_handlers)


def main(argv):
  if len(argv) < 1:
    PrintHelp()
    return 0

  command = argv[1]

  if command == '_run_compiler':
    return RunCompiler(argv[2])

  if command == '_run_server':
    return RunServer()

  if command == 'kill':
    return KillServer()

  if command == 'start':
    return StartServer()

  if command == 'restart':
    return RestartServer()

  if command == 'compile':
    return ClientCompile(argv)


if __name__ == '__main__':
  sys.exit(main(sys.argv))
