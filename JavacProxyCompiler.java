import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.net.ServerSocket;
import java.util.List;

import com.sun.tools.javac.Main;

import py4j.GatewayServer;

class JavacProxyCompiler {
  public static final String COMPILE_END_SIGNAL = "-----COMPILE FINISHED-----";
  public static final String READY_SIGNAL = "-----COMPILER READY-----";
  public static final String DEAD_SIGNAL = "-----COMPILER DIED-----";
  public static final String PORT_SIGNAL = "-----PORT: %d-----";

  public static class CompileResults {
    int returnCode;
    String output;

    CompileResults(int rc, String o) {
      returnCode = rc;
      output = o;
    }

    public int returnCode() { return returnCode; }
    public String output() { return output; }
  }

  enum OptionType {
    None,
    Single,
    Multiple,
  }

  public static String Absolutize(String cwd, String path) {
      if (path.charAt(0) == '/') return path;
      return new File(cwd, path).getAbsolutePath();
  }


  public static CompileResults compile(List<String> options, String cwd) {
    int returnCode = 1;
    String output = "";
    // TODO: The client should be able to de-interleave stdout and stderr if it wants.
    ByteArrayOutputStream output_stream = new ByteArrayOutputStream();

    try {
      // I could find no way to set the working directory for
      // com.sun.tools.javac.Main.compile. For this reason, we parse the
      // options and files and absolutize the files.
      // TODO: It would be easier to just use javax.tools.JavaCompiler. The
      // main thing that would need to be done for that is to check that -X
      // options work and then we'd need to do our own options checking and
      // help message... maybe we can use com.sun.tools.javac.Main just for
      // that.
      System.setOut(new PrintStream(output_stream));
      System.setErr(new PrintStream(output_stream));

      String[] fixedOptions = new String[options.size() + 4];
      fixedOptions[0] = "-d";
      fixedOptions[1] = cwd;
      fixedOptions[2] = "-s";
      fixedOptions[3] = cwd;

      OptionType nextType = OptionType.Single;
      for (int i = 0; i < options.size(); i++) {
        String option = options.get(i);
        if (option.length() > 0 && option.charAt(0) == '-') {
          if (option == "-d" || option == "-s") {
            nextType = OptionType.Single;
          } else if (
              option.equals("-classpath") ||
              option.equals("-cp") ||
              option.equals("-sourcepath") ||
              option.equals("-bootclasspath") ||
              option.equals("-extdirs") ||
              option.equals("-endorseddirs") ||
              option.equals("-processorpath")
              ) {
            nextType = OptionType.Multiple;
          } else if (
              option.equals("-encoding") ||
              option.equals("-source") ||
              option.equals("-target")
              ) {
            nextType = OptionType.None;
          }
        } else if (nextType == OptionType.Single) {
          if (option.length() > 0 && option.charAt(0) != '/') {
            option = Absolutize(cwd, option);
          }
        } else if (nextType == OptionType.Multiple) {
            String abs_option = "";
            boolean first = true;
            for (String s: option.split(":")) {
                if (!first) {
                    abs_option += ":";
                }
                abs_option += Absolutize(cwd, s);
                first = false;
            }
            option = abs_option;
            nextType = OptionType.Single;
        } else if (nextType == OptionType.None) {
            nextType = OptionType.Single;
        }
        fixedOptions[i + 4] = option;
      }
      returnCode = com.sun.tools.javac.Main.compile(fixedOptions);
    } catch (Throwable e) {
      e.printStackTrace();
    } finally {
      output = output_stream.toString();
      System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out)));
      System.setErr(new PrintStream(new FileOutputStream(FileDescriptor.err)));
    }

    sendMessage(COMPILE_END_SIGNAL);
    return new CompileResults(returnCode, output);
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
