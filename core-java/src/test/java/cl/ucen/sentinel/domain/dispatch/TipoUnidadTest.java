package cl.ucen.sentinel.domain.dispatch;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Tests de {@link TipoUnidad}: valores de texto, fromValor y rechazo de valores inválidos.
 *
 * <p>Espeja {@code TestTipoUnidad} del Python {@code test_tipos.py}.
 */
@DisplayName("TipoUnidad")
class TipoUnidadTest {

  // --- Normal: valores y round-trip -------------------------------------------

  @Test
  @DisplayName("N-01: el enum tiene exactamente dos tipos de unidad")
  void enumTieneDosValores() {
    assertThat(TipoUnidad.values()).hasSize(2);
  }

  @Test
  @DisplayName("N-02: valor() devuelve el string serializable equivalente al Python")
  void valorDevuelveStringCorrecto() {
    assertThat(TipoUnidad.AVANZADA.valor()).isEqualTo("Avanzada");
    // El acento en "Básica" es esencial para la equivalencia con el Python StrEnum.
    assertThat(TipoUnidad.BASICA.valor()).isEqualTo("Básica");
  }

  @Test
  @DisplayName("N-03: fromValor devuelve el tipo correcto para cada valor de texto")
  void fromValorDevuelveCorrectoParaAmbosTipos() {
    assertThat(TipoUnidad.fromValor("Avanzada")).isEqualTo(TipoUnidad.AVANZADA);
    assertThat(TipoUnidad.fromValor("Básica")).isEqualTo(TipoUnidad.BASICA);
  }

  // --- Borde: round-trip valor/fromValor ---------------------------------------

  @Test
  @DisplayName("B-01: fromValor(valor()) es identidad para todos los tipos")
  void fromValorRoundTrip() {
    for (TipoUnidad t : TipoUnidad.values()) {
      assertThat(TipoUnidad.fromValor(t.valor())).isEqualTo(t);
    }
  }

  // --- Error: rechazo de valores inválidos -------------------------------------

  @Test
  @DisplayName("E-01: fromValor lanza IllegalArgumentException para valor fuera del dominio")
  void fromValorRechazaValorInvalido() {
    assertThatThrownBy(() -> TipoUnidad.fromValor("Intermedia"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Intermedia");
  }

  @Test
  @DisplayName("E-02: fromValor lanza IllegalArgumentException para string vacío")
  void fromValorRechazaStringVacio() {
    assertThatThrownBy(() -> TipoUnidad.fromValor("")).isInstanceOf(IllegalArgumentException.class);
  }
}
