package cl.ucen.sentinel.domain.triaje;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Tests de {@link RespuestaTriaje}: inmutabilidad, contrato de campos y rechazo de nulos.
 *
 * <p>Espeja {@code TestRespuestaTriaje} de {@code test_tipos.py} y {@code TestEnumsRespuesta}.
 */
@DisplayName("RespuestaTriaje")
class RespuestaTriajeTest {

  /** Factory con defaults seguros: paciente consciente, sin Chief Complaint activado. */
  private static RespuestaTriaje respuestaDefault() {
    return new RespuestaTriaje(
        true, true, NivelSangrado.NINGUNO, NivelDolorToracico.NINGUNO, false, GrupoEtario.ADULTO);
  }

  // --- Normal: construcción y acceso ----------------------------------------

  @Test
  @DisplayName("N-01: acepta los seis campos del SRS y los expone por accessors")
  void aceptaLosSeisCamposDelSrs() {
    RespuestaTriaje r =
        new RespuestaTriaje(
            true,
            true,
            NivelSangrado.MODERADO,
            NivelDolorToracico.NINGUNO,
            false,
            GrupoEtario.ADULTO);

    assertThat(r.consciente()).isTrue();
    assertThat(r.respiraNormal()).isTrue();
    assertThat(r.sangrado()).isEqualTo(NivelSangrado.MODERADO);
    assertThat(r.dolorToracico()).isEqualTo(NivelDolorToracico.NINGUNO);
    assertThat(r.dificultadRespiratoria()).isFalse();
    assertThat(r.grupoEtario()).isEqualTo(GrupoEtario.ADULTO);
  }

  @Test
  @DisplayName("N-02: dos instancias con los mismos campos son iguales (record equality)")
  void dosInstanciasIgualesConMismosValores() {
    RespuestaTriaje r1 = respuestaDefault();
    RespuestaTriaje r2 = respuestaDefault();
    assertThat(r1).isEqualTo(r2);
    assertThat(r1.hashCode()).isEqualTo(r2.hashCode());
  }

  // --- Borde: enums válidos -------------------------------------------------

  @Test
  @DisplayName("B-01: acepta grupo etario pediátrico (reservado en v1)")
  void aceptaGrupoEtarioPediatrico() {
    RespuestaTriaje r =
        new RespuestaTriaje(
            false,
            true,
            NivelSangrado.NINGUNO,
            NivelDolorToracico.NINGUNO,
            false,
            GrupoEtario.PEDIATRICO);
    assertThat(r.grupoEtario()).isEqualTo(GrupoEtario.PEDIATRICO);
  }

  @Test
  @DisplayName("B-02: NivelSangrado tiene exactamente cuatro niveles")
  void nivelSangradoTieneCuatroNiveles() {
    // Espeja test_nivel_sangrado_tiene_cuatro_niveles del Python.
    assertThat(NivelSangrado.values()).hasSize(4);
    assertThat(NivelSangrado.fromValor("Ninguno")).isEqualTo(NivelSangrado.NINGUNO);
    assertThat(NivelSangrado.fromValor("Moderado")).isEqualTo(NivelSangrado.MODERADO);
    assertThat(NivelSangrado.fromValor("Activo")).isEqualTo(NivelSangrado.ACTIVO);
    assertThat(NivelSangrado.fromValor("Peligroso")).isEqualTo(NivelSangrado.PELIGROSO);
  }

  // --- Error: nulos rechazados ----------------------------------------------

  @Test
  @DisplayName("E-01: lanza NullPointerException si sangrado es nulo")
  void lanzaNpeConSangradoNulo() {
    assertThatThrownBy(
            () ->
                new RespuestaTriaje(
                    true, true, null, NivelDolorToracico.NINGUNO, false, GrupoEtario.ADULTO))
        .isInstanceOf(NullPointerException.class);
  }

  @Test
  @DisplayName("E-02: lanza NullPointerException si dolorToracico es nulo")
  void lanzaNpeConDolorToracicoNulo() {
    assertThatThrownBy(
            () ->
                new RespuestaTriaje(
                    true, true, NivelSangrado.NINGUNO, null, false, GrupoEtario.ADULTO))
        .isInstanceOf(NullPointerException.class);
  }

  @Test
  @DisplayName("E-03: NivelSangrado.fromValor lanza IllegalArgumentException para valor inválido")
  void nivelSangradoRechazaValorInvalido() {
    // Espeja test_nivel_sangrado_rechaza_valor_invalido del Python.
    assertThatThrownBy(() -> NivelSangrado.fromValor("Inexistente"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("Inexistente");
  }
}
