.PHONY: help install test test-python test-java test-fast test-dataset \
        lint typecheck ci compare build-graph clean

# ===========================================================================
# Makefile raíz del monorepo Sentinel-Dispatch
#
# Orquesta los dos cores:
#   - core-python/  → implementación primaria (FastAPI + OSMnx + dominio puro)
#   - core-java/    → validación dual del núcleo (RT-01..RT-04)
#
# Para targets específicos de un core, hacer `cd core-python && make <target>`
# o `cd core-java && mvn <comando>`.
# ===========================================================================

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instalar dependencias en ambos cores
	$(MAKE) -C core-python install
	@echo "Para core-java: cd core-java && mvn dependency:resolve"

test: test-python test-java ## Correr tests de ambos cores

test-python: ## Tests de core-python (pytest)
	$(MAKE) -C core-python test

test-java: ## Tests de core-java (JUnit 5)
	cd core-java && mvn test

test-fast: ## Solo unit tests rápidos de ambos cores
	$(MAKE) -C core-python test-fast
	cd core-java && mvn test -Dgroups="unit"

test-dataset: ## Ejecutar dataset de 12 incidentes en ambos cores
	$(MAKE) -C core-python test-dataset
	cd core-java && mvn exec:java -Dexec.mainClass="cl.ucen.sentinel.cli.Main" \
		-Dexec.args="run-dataset --in ../data/dataset/incidentes.json \
		             --graph ../data/graphs/coquimbo.graphml \
		             --out /tmp/java-out/"

compare: ## Validación dual RT-02 — compara outputs Python vs Java
	uv run python tools/compare_outputs.py \
		--python /tmp/python-out/ \
		--java /tmp/java-out/ \
		--report docs/quality/rt-validation-report.md

lint: ## Lint en ambos cores
	$(MAKE) -C core-python lint
	cd core-java && mvn spotless:check

typecheck: ## Typecheck core-python (Java es typecheck-by-compile)
	$(MAKE) -C core-python typecheck

ci: ## Pipeline completo (lo que corre en GitHub Actions)
	$(MAKE) -C core-python ci
	cd core-java && mvn verify

build-graph: ## Pre-computar grafo OSM IV Región (~2 min, ~30-60 MB)
	$(MAKE) -C core-python build-graph

clean: ## Borrar caches y artifacts de ambos cores
	$(MAKE) -C core-python clean
	cd core-java && mvn clean
