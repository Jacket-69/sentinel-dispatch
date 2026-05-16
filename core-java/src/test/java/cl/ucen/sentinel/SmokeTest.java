package cl.ucen.sentinel;

import static org.assertj.core.api.Assertions.assertThat;

import cl.ucen.sentinel.cli.Main;
import org.junit.jupiter.api.Test;

class SmokeTest {

  @Test
  void mainClassIsLoadable() {
    assertThat(Main.class.getPackageName()).isEqualTo("cl.ucen.sentinel.cli");
  }
}
