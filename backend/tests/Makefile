#
# Makefile für Docker Compose
# Ondics, 2025
#

# aktuelles Dir ist docker-compose project name
mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))

DC_BIN = docker compose
DC_FILE = docker-compose.yml
DC_PROJECT = ${current_dir}

DC = ${DC_BIN} -f ${DC_FILE} -p ${DC_PROJECT}

# help-systematik
# build muss phony sein (forcierter build), weil es 
# als verzeichnis existiert und sonst nie gebaut werden würde
.PHONY: help build

help:
	@echo "# Docker-Helferlein"
	@echo "# Ondics, 2025"
	@echo Befehle: make ...
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help

# hier die befehle
up:	## alle Container starten
	${DC} up -d  --remove-orphans

down: ## alle Container stoppen
	${DC} down --remove-orphans
	
down-volumes: ## alle Container stoppen und Volumes löschen
	${DC} down --remove-orphans -v
	
build: ## alle Container bauen
	#${DC} build --progress plain
	${DC} build

ps: ## was läuft?
	${DC} ps

bash: ## Die bash im php Container starten
	#${DC} exec app bash
	${DC} run --rm ckan-mcp-server bash

logs: ## Alle stdout's aller Container zeigen
	${DC} logs -f -t

images: ## Alle Images zeigen
	${DC} images

config: ## show docker-compose expanded
	${DC} config

