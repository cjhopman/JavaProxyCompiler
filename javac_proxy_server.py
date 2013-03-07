import optparse
import os
import sys

from py4j.java_gateway import JavaGateway
from py4j.java_collections import ListConverter



def main(argv):
  gateway = JavaGateway()
  files = ListConverter().convert(gateway._gateway_client, ['JarUse.java'])
  gateway.jvm.JavacProxyCompiler.compile(options, files)


if __name__ == '__main__':
  sys.exit(main(sys.argv))
