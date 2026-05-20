package cl.ucen.sentinel.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/** Tests unitarios de {@link MotivoDespacho}. */
@DisplayName("MotivoDespacho")
class MotivoDespachoTest {

  // ---------------------------------------------------------------------------
  // Normal
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Normal")
  class Normal {

    @Test
    @DisplayName("N-01: hay exactamente cuatro motivos declarados")
    void hayExactamenteCuatroMotivos() {
      assertThat(MotivoDespacho.values()).hasSize(4);
    }

    @Test
    @DisplayName("N-02: cada valor() devuelve el string esperado")
    void cadaValorDevuelveStringEsperado() {
      assertThat(MotivoDespacho.OPTIMO.valor()).isEqualTo("optimo");
      assertThat(MotivoDespacho.PENALIZADO.valor()).isEqualTo("penalizado");
      assertThat(MotivoDespacho.SUBOPTIMO_RN02.valor()).isEqualTo("suboptimo_rn02");
      assertThat(MotivoDespacho.SATURACION.valor()).isEqualTo("saturacion");
    }
  }

  // ---------------------------------------------------------------------------
  // Borde
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Borde")
  class Borde {

    @Test
    @DisplayName("B-01: fromValor hace round-trip para cada constante")
    void fromValorHaceRoundTrip() {
      for (MotivoDespacho m : MotivoDespacho.values()) {
        assertThat(MotivoDespacho.fromValor(m.valor())).isSameAs(m);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Error
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Error")
  class Error {

    @Test
    @DisplayName("E-01: fromValor con valor desconocido lanza IllegalArgumentException con mensaje")
    void fromValorDesconocidoLanzaExcepcion() {
      assertThatThrownBy(() -> MotivoDespacho.fromValor("x"))
          .isInstanceOf(IllegalArgumentException.class)
          .hasMessageContaining("x");
    }
  }
}
