import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import java.util.List;

import py4j.GatewayServer;

class JavaxProxyCompiler {
  public static void compile(List<String> options, List<String> java_files) {
    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
    StandardJavaFileManager fileManager = compiler.getStandardFileManager(null, null, null);

    Iterable<? extends JavaFileObject> compilationUnits1 =
      fileManager.getJavaFileObjectsFromStrings(java_files);
    compiler.getTask(null, fileManager, null, null, null, compilationUnits1).call();
    fileManager.close();
  }

  public static void main(String[] args) {
    for (String a: args)
      System.out.println(a);

    GatewayServer gatewayServer = new GatewayServer(null);
    gatewayServer.start();
    System.out.println("Gateway Server Started");
  }
}
