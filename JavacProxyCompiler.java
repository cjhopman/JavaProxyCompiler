import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;
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

  public static class CompileResults {
    Boolean success;
    String output;

    CompileResults(Boolean s, String o) {
      success = s;
      output = o;
    }

    public Boolean success() { return success; }
    public String output() { return output; }
  }

  public static CompileResults compile(List<String> options, List<String> javaFiles) {
    Boolean success = false;
    String output = "";
    // TODO: The client should be able to de-interleave stdout and stderr if it wants.
    ByteArrayOutputStream output_stream = new ByteArrayOutputStream();

    try {
      System.setOut(new PrintStream(output_stream));
      System.setErr(new PrintStream(output_stream));

      JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
      StandardJavaFileManager fileManager = compiler.getStandardFileManager(null, null, null);

      Iterable<? extends JavaFileObject> fileObjects =
        fileManager.getJavaFileObjectsFromStrings(javaFiles);
      success = compiler.getTask(null, fileManager, null, options, null, fileObjects).call();
      fileManager.close();

    } catch (IOException e) {
      success = false;
    } finally {
      output = output_stream.toString();
      System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out)));
      System.setErr(new PrintStream(new FileOutputStream(FileDescriptor.err)));
    }

    sendMessage(COMPILE_END_SIGNAL);
    return new CompileResults(success, output);
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
