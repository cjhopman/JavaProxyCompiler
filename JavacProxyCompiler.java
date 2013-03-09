import java.io.IOException;
import java.net.ServerSocket;
import java.util.List;

import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import javax.tools.StandardJavaFileManager;
import javax.tools.JavaFileObject;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;


import py4j.GatewayServer;

class JavacProxyCompiler {
  public static final String COMPILE_END_SIGNAL = "-----COMPILE FINISHED-----";
  public static final String READY_SIGNAL = "-----COMPILER READY-----";
  public static final String DEAD_SIGNAL = "-----COMPILER DIED-----";
  public static final String PORT_SIGNAL = "-----PORT: %d-----";

  public static Boolean compile(List<String> options, List<String> java_files) throws IOException {
    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
    StandardJavaFileManager fileManager = compiler.getStandardFileManager(null, null, null);

    Iterable<? extends JavaFileObject> compilationUnits1 =
      fileManager.getJavaFileObjectsFromStrings(java_files);
    Boolean success = compiler.getTask(null, fileManager, null, options, null, compilationUnits1).call();
    fileManager.close();

    sendMessage(COMPILE_END_SIGNAL);
    return success;
  }

  public static void sendMessage(String message) {
    System.out.println(message);
    System.out.flush();
  }

  public static void main(String[] args) throws IOException {
    Runtime.getRuntime().addShutdownHook(new Thread() {
      public void run() {
        sendMessage(DEAD_SIGNAL);
      }
    });

    ServerSocket socket = new ServerSocket(0);
    int port = socket.getLocalPort();
    socket.close();

    GatewayServer gatewayServer = new GatewayServer(null, port);
    gatewayServer.start();
    sendMessage(READY_SIGNAL);
    sendMessage(String.format(PORT_SIGNAL, port));
  }
}
