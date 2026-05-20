package cl.ucen.sentinel.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.offset;

import cl.ucen.sentinel.domain.dispatch.EstadoUnidad;
import cl.ucen.sentinel.domain.dispatch.TipoUnidad;
import cl.ucen.sentinel.domain.dispatch.Unidad;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * Tests unitarios de {@link Saturacion#detectar} (RN-08, CP-10).
 *
 * <p>Espeja {@code test_saturacion.py} 1:1. Casos normativos cubiertos: RN-08, CP-10.
 */
@DisplayName("Saturacion")
class SaturacionTest {

  // ---------------------------------------------------------------------------
  // Helper de construcción
  // ---------------------------------------------------------------------------

  private static Unidad u(String id, EstadoUnidad estado) {
    return new Unidad(
        id,
        "AMB-" + id.substring(1),
        TipoUnidad.AVANZADA,
        "Hospital test",
        -29.9077,
        -71.2535,
        estado);
  }

  // ---------------------------------------------------------------------------
  // Normal — hay al menos un DISPONIBLE
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Normal")
  class Normal {

    @Test
    @DisplayName("N-01: una DISPONIBLE basta → saturada=false, candidatas vacías")
    void unaDisponibleRetornaNoSaturadaSinCandidatas() {
      List<Unidad> flota = List.of(u("U01", EstadoUnidad.DISPONIBLE));
      EstadoSaturacion r = Saturacion.detectar(flota, null);
      assertThat(r.saturada()).isFalse();
      assertThat(r.candidatasRedireccion()).isEmpty();
    }

    @Test
    @DisplayName("N-02: dos DISPONIBLES y una EN_RUTA → no saturada, candidatas vacías")
    void dosDisponiblesYUnaEnRutaNoSatura() {
      List<Unidad> flota =
          List.of(
              u("U01", EstadoUnidad.DISPONIBLE),
              u("U02", EstadoUnidad.DISPONIBLE),
              u("U03", EstadoUnidad.EN_RUTA));
      EstadoSaturacion r = Saturacion.detectar(flota, Map.of("U03", 0.5));
      assertThat(r.saturada()).isFalse();
      assertThat(r.candidatasRedireccion()).isEmpty();
    }
  }

  // ---------------------------------------------------------------------------
  // Borde
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Borde")
  class Borde {

    @Test
    @DisplayName("B-01: flota vacía → saturada=true, candidatas vacías")
    void flotaVaciaRetornaSaturadaSinCandidatas() {
      EstadoSaturacion r = Saturacion.detectar(List.of(), null);
      assertThat(r.saturada()).isTrue();
      assertThat(r.candidatasRedireccion()).isEmpty();
    }

    @Test
    @DisplayName("B-02: flota toda TALLER → saturada=true, candidatas vacías (no hay EN_RUTA)")
    void flotaTodaTallerRetornaSaturadaSinCandidatas() {
      List<Unidad> flota = List.of(u("U05", EstadoUnidad.TALLER), u("U06", EstadoUnidad.TALLER));
      EstadoSaturacion r = Saturacion.detectar(flota, null);
      assertThat(r.saturada()).isTrue();
      assertThat(r.candidatasRedireccion()).isEmpty();
    }

    @Test
    @DisplayName("B-03: una sola EN_RUTA sin progreso → default 0.0")
    void unaEnRutaSinProgresoUsaDefaultCero() {
      List<Unidad> flota = List.of(u("U04", EstadoUnidad.EN_RUTA));
      EstadoSaturacion r = Saturacion.detectar(flota, null);
      assertThat(r.saturada()).isTrue();
      assertThat(r.candidatasRedireccion()).hasSize(1);
      assertThat(r.candidatasRedireccion().get(0).unidad().id()).isEqualTo("U04");
      assertThat(r.candidatasRedireccion().get(0).progresoPct()).isCloseTo(0.0, offset(1e-9));
    }

    @Test
    @DisplayName("B-04: progresoPorUnidad=null tratado como mapa vacío → todos con progreso=0.0")
    void progresoPorUnidadNullTratadoComoMapaVacio() {
      List<Unidad> flota = List.of(u("U02", EstadoUnidad.EN_RUTA), u("U08", EstadoUnidad.EN_RUTA));
      EstadoSaturacion r = Saturacion.detectar(flota, null);
      assertThat(r.saturada()).isTrue();
      // Ambas con progreso 0.0; desempate lex → U02 primero
      assertThat(r.candidatasRedireccion()).hasSize(2);
      assertThat(r.candidatasRedireccion().get(0).unidad().id()).isEqualTo("U02");
      assertThat(r.candidatasRedireccion().get(0).progresoPct()).isCloseTo(0.0, offset(1e-9));
    }
  }

  // ---------------------------------------------------------------------------
  // Regla de Negocio CP-10 — orden de candidatasRedireccion
  // ---------------------------------------------------------------------------

  @Nested
  @DisplayName("Regla de Negocio")
  class ReglaDeNegocio {

    @Test
    @DisplayName("RN-01: CP-10 progreso 0.6 y 0.3 → ordenadas por progreso ascendente")
    void cp10OrdenPorProgresoAscendente() {
      List<Unidad> flota = List.of(u("U03", EstadoUnidad.EN_RUTA), u("U08", EstadoUnidad.EN_RUTA));
      Map<String, Double> progreso = Map.of("U03", 0.6, "U08", 0.3);
      EstadoSaturacion r = Saturacion.detectar(flota, progreso);
      assertThat(r.saturada()).isTrue();
      assertThat(r.candidatasRedireccion()).hasSize(2);
      // U08 primero (0.3 < 0.6)
      assertThat(r.candidatasRedireccion().get(0).unidad().id()).isEqualTo("U08");
      assertThat(r.candidatasRedireccion().get(0).progresoPct()).isCloseTo(0.3, offset(1e-9));
      assertThat(r.candidatasRedireccion().get(1).unidad().id()).isEqualTo("U03");
      assertThat(r.candidatasRedireccion().get(1).progresoPct()).isCloseTo(0.6, offset(1e-9));
    }

    @Test
    @DisplayName("RN-02: CP-10 empate de progreso → desempate lexicográfico por id")
    void cp10EmpateDeProgresoDesempateLexico() {
      List<Unidad> flota = List.of(u("U05", EstadoUnidad.EN_RUTA), u("U02", EstadoUnidad.EN_RUTA));
      Map<String, Double> progreso = Map.of("U05", 0.3, "U02", 0.3);
      EstadoSaturacion r = Saturacion.detectar(flota, progreso);
      assertThat(r.saturada()).isTrue();
      assertThat(r.candidatasRedireccion()).hasSize(2);
      // U02 < U05 lexicográficamente
      assertThat(r.candidatasRedireccion().get(0).unidad().id()).isEqualTo("U02");
      assertThat(r.candidatasRedireccion().get(1).unidad().id()).isEqualTo("U05");
    }

    @Test
    @DisplayName("RN-03: EN_RUTA sin entrada en el mapa → default 0.0")
    void enRutaSinEntradaEnMapaUsaDefault() {
      List<Unidad> flota = List.of(u("U02", EstadoUnidad.EN_RUTA), u("U08", EstadoUnidad.EN_RUTA));
      // Solo U08 tiene entrada; U02 cae al default 0.0
      EstadoSaturacion r = Saturacion.detectar(flota, Map.of("U08", 0.5));
      assertThat(r.saturada()).isTrue();
      Map<String, Double> porId = new java.util.HashMap<>();
      for (CandidataRedireccion c : r.candidatasRedireccion()) {
        porId.put(c.unidad().id(), c.progresoPct());
      }
      assertThat(porId.get("U02")).isCloseTo(0.0, offset(1e-9));
      assertThat(porId.get("U08")).isCloseTo(0.5, offset(1e-9));
    }
  }
}
