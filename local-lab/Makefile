# Optional synthetic exercise. See README.md before global reset.
.PHONY: help generate start seed test inspect report clean reset

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c

LAB_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
COMPOSE := docker compose -p open-table-formats-lab --project-directory "$(LAB_DIR)" -f "$(LAB_DIR)/docker-compose.yml"

help:
	@echo "make test      Generate data, run all mutations, and verify all formats"
	@echo "make inspect   List raw, table-data, and metadata objects in S3"
	@echo "make report    Print the latest compact evidence report"
	@echo "make clean     Stop containers but keep the S3 volume"
	@echo "make reset     Stop containers and delete the disposable S3 volume"

generate:
	$(COMPOSE) run --rm generator

start:
	$(COMPOSE) up -d --wait s3

seed: generate start
	$(COMPOSE) run --rm seed

test: seed
	mkdir -p "$(LAB_DIR)/evidence"
	$(COMPOSE) run --rm --build spark 2>&1 | tee "$(LAB_DIR)/evidence/observed-results.log"

inspect: start
	$(COMPOSE) run --rm --entrypoint /bin/sh seed -c \
	  'aws --endpoint-url=http://s3:4566 s3 ls "s3://$${S3_BUCKET}/" --recursive'

report:
	@sed -n '1,240p' "$(LAB_DIR)/evidence/lab1-report.md"

clean:
	$(COMPOSE) down

reset:
	$(COMPOSE) down --volumes --remove-orphans
