package py4j.examples;

import java.util.LinkedList;
import java.util.List;

public class Stack {
  private List<String> list = new LinkedList<String>();

  public void push(String el) {
    list.add(0, el);
  }

  public String pop() {
    return list.remove(0);
  }

  public List<String> getList() {
    return list;
  }

  public void pushAll(List<String> els) {
    for (String el: els)
      push(el);
  }
}
