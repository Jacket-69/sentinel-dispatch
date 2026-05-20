package cl.ucen.sentinel.domain.dispatch;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Tests de {@link EstadoUnidad}: valores de texto, fromValor y rechazo de valores inválidos.
 *
 * <p>Espeja {@code TestEstadoUnidad} del Python {@code test_tipos.py}.
 */
@DisplayName("EstadoUnidad")
class EstadoUnidadTest {

  // --- Normal: valores y count ------------------------------------------------

  @Test
  @DisplayName("N-01: el enum tiene exactamente cuatro estados operativos")
  void enumTieneCuatroValores() {
    assertThat(EstadoUnidad.values()).hasSize(4);
  }

  @Test
  @DisplayName("N-02: valor() devuelve el string serializable equivalente al Python")
  void valorDevuelveStringCorrecto() {
    assertThat(EstadoUnidad.DISPONIBLE.valor()).isEqualTo("Disponible");
    assertThat(EstadoUnidad.EN_RUTA.valor()).isEqualTo("EnRuta");
    assertThat(EstadoUnidad.EN_ESCENA.valor()).isEqualTo("EnEscena");
    assertThat(EstadoUnidad.TALLER.valor()).isEqualTo("Taller");
  }

  @Test
  @DisplayName("N-03: fromValor devuelve el estado correcto para cada valor de texto")
  void fromValorDevuelveCorrectoParaTodosLosEstados() {
    assertThat(EstadoUnidad.fromValor("Disponible")).isEqualTo(EstadoUnidad.DISPONIBLE);
    assertThat(EstadoUnidad.fromValor("EnRuta")).isEqualTo(EstadoUnidad.EN_RUTA);
    assertThat(EstadoUnidad.fromValor("EnEscena")).isEqualTo(EstadoUnidad.EN_ESCENA);
    assertThat(EstadoUnidad.fromValor("Taller")).isEqualTo(EstadoUnidad.TALLER);
  }

  // --- Borde: round-trip valor/fromValor ---------------------------------------

  @Test
  @DisplayName("B-01: fromValor(valor()) es identidad para todos los estados")
  void fromValorRoundTrip() {
    for (EstadoUnidad e : EstadoUnidad.values()) {
      assertThat(EstadoUnidad.fromValor(e.valor())).isEqualTo(e);
    }
  }

  // --- Error: rechazo de valores inválidos -------------------------------------

  @Test
  @DisplayName("E-01: fromValor lanza IllegalArgumentException para valor fuera del dominio")
  void fromValorRechazaValorInvalido() {
    assertThatThrownBy(() -> EstadoUnidad.fromValor("Apagado"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Apagado");
  }

  @Test
  @DisplayName("E-02: fromValor lanza IllegalArgumentException para string vacío")
  void fromValorRechazaStringVacio() {
    assertThatThrownBy(() -> EstadoUnidad.fromValor(""))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
