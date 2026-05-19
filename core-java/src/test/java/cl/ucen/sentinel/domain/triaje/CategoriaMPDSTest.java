package cl.ucen.sentinel.domain.triaje;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Tests de {@link CategoriaMPDS}: orden natural, valores de texto y rechazo de valores inválidos.
 *
 * <p>Espeja {@code TestCategoriaMPDS} de {@code test_tipos.py}.
 */
@DisplayName("CategoriaMPDS")
class CategoriaMPDSTest {

  // --- Normal: orden estricto -----------------------------------------------

  @Test
  @DisplayName("N-01: orden estricto Alpha < Bravo < Charlie < Delta < Echo por ordinal")
  void ordenEstrictoAlphaAEcho() {
    // Criticidad creciente declarada en el SRS sec. 2.6-A.
    assertThat(CategoriaMPDS.ALPHA.ordinal()).isLessThan(CategoriaMPDS.BRAVO.ordinal());
    assertThat(CategoriaMPDS.BRAVO.ordinal()).isLessThan(CategoriaMPDS.CHARLIE.ordinal());
    assertThat(CategoriaMPDS.CHARLIE.ordinal()).isLessThan(CategoriaMPDS.DELTA.ordinal());
    assertThat(CategoriaMPDS.DELTA.ordinal()).isLessThan(CategoriaMPDS.ECHO.ordinal());
  }

  @Test
  @DisplayName("N-02: compareTo es transitivo (Alpha < Charlie < Echo)")
  void ordenEsTransitivo() {
    // Si Alpha < Charlie y Charlie < Echo entonces Alpha < Echo.
    assertThat(CategoriaMPDS.ALPHA).isLessThan(CategoriaMPDS.CHARLIE);
    assertThat(CategoriaMPDS.CHARLIE).isLessThan(CategoriaMPDS.ECHO);
    assertThat(CategoriaMPDS.ALPHA).isLessThan(CategoriaMPDS.ECHO);
  }

  // --- Borde: fromValor y valores de texto ----------------------------------

  @Test
  @DisplayName("B-01: fromValor devuelve la categoría correcta para cada valor de texto")
  void fromValorDevuelveCategoriaCorrecta() {
    assertThat(CategoriaMPDS.fromValor("Alpha")).isEqualTo(CategoriaMPDS.ALPHA);
    assertThat(CategoriaMPDS.fromValor("Bravo")).isEqualTo(CategoriaMPDS.BRAVO);
    assertThat(CategoriaMPDS.fromValor("Charlie")).isEqualTo(CategoriaMPDS.CHARLIE);
    assertThat(CategoriaMPDS.fromValor("Delta")).isEqualTo(CategoriaMPDS.DELTA);
    assertThat(CategoriaMPDS.fromValor("Echo")).isEqualTo(CategoriaMPDS.ECHO);
  }

  @Test
  @DisplayName("B-02: valor() devuelve el string de texto serializable equivalente al Python")
  void valorDevuelveStringCorrecto() {
    assertThat(CategoriaMPDS.ECHO.valor()).isEqualTo("Echo");
    assertThat(CategoriaMPDS.ALPHA.valor()).isEqualTo("Alpha");
  }

  // --- Error: rechazo de valores inválidos ----------------------------------

  @Test
  @DisplayName("E-01: fromValor lanza IllegalArgumentException para valor fuera del dominio")
  void fromValorRechazaValorInvalido() {
    // Espeja test_categoria_mpds_rechaza_valor_invalido del Python.
    assertThatThrownBy(() -> CategoriaMPDS.fromValor("Foxtrot"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Foxtrot");
  }

  @Test
  @DisplayName("E-02: el enum tiene exactamente cinco niveles MPDS")
  void enumTieneCincoNiveles() {
    assertThat(CategoriaMPDS.values()).hasSize(5);
  }
}
