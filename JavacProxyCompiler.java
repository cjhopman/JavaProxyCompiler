import java.io.IOException;
import java.util.List;

import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;
import javax.tools.StandardJavaFileManager;
import javax.tools.JavaFileObject;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;

import py4j.GatewayServer;

class JavacProxyCompiler {
  static class SimpleDiagnostics {
    String message;
    boolean error;
    boolean warning;

    String getMessage() { return message; }
    boolean getError() { return error; }
    boolean getWarning() { return warning; }

    SimpleDiagnostics(List<Diagnostic<? extends JavaFileObject>> diagnostics) {
      message = "";
      for (Diagnostic<? extends JavaFileObject> d : diagnostics) {
        error = error || d.getKind() == Diagnostic.Kind.ERROR;
        warning = warning || d.getKind() == Diagnostic.Kind.WARNING || d.getKind() == Diagnostic.Kind.MANDATORY_WARNING;
        message += d.getMessage(null) + "\n";
      }
      System.out.println(getError());
      System.out.println(getWarning());
      System.out.println(getMessage());
    }
  }
  public static SimpleDiagnostics compile(List<String> options, List<String> java_files) throws IOException {
    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
    StandardJavaFileManager fileManager = compiler.getStandardFileManager(null, null, null);
    DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<JavaFileObject>();

    Iterable<? extends JavaFileObject> compilationUnits1 =
      fileManager.getJavaFileObjectsFromStrings(java_files);
    compiler.getTask(null, fileManager, diagnostics, options, null, compilationUnits1).call();
    SimpleDiagnostics ret = new SimpleDiagnostics(diagnostics.getDiagnostics());
    fileManager.close();
    return ret;
  }

  public static void main(String[] args) {
    for (String a: args)
      System.out.println(a);

    GatewayServer gatewayServer = new GatewayServer(null);
    gatewayServer.start();
    System.out.println("Gateway Server Started");
  }
}
