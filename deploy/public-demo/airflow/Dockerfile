# Public-demo Airflow image: the pinned upstream Airflow image plus the two
# owner-repository packages and DAG files, each fetched by immutable commit
# and verified by SHA-256 before use. Nothing is copied from a local checkout.
#
# DAGs baked in (both schedule=None, is_paused_upon_creation=True):
#   brazil-public-data-map   dags/education_siope_annual_update.py
#   education-finance-mlops  dags/education_monitoring_demo.py
# Deliberately NOT included: brazil-public-data-map dags/pncp_incremental_update.py,
# which declares schedule="0 */6 * * *" and no is_paused_upon_creation.
#
# Packages are installed with --no-deps: the DAG modules only need pyarrow,
# which the Airflow image already provides (a newer major than the owner
# repositories declare; see compatibility-matrix.md).
ARG AIRFLOW_IMAGE
FROM ${AIRFLOW_IMAGE}

ARG DATA_MAP_REPO
ARG DATA_MAP_COMMIT
ARG DATA_MAP_ARCHIVE_SHA256
ARG MLOPS_REPO
ARG MLOPS_COMMIT
ARG MLOPS_ARCHIVE_SHA256

USER root
RUN mkdir -p /opt/public-demo/dags && chown airflow:0 /opt/public-demo/dags
USER airflow
RUN set -eu; \
    cd /tmp; \
    curl -fsSL -o data-map.tar.gz "https://codeload.github.com/${DATA_MAP_REPO}/tar.gz/${DATA_MAP_COMMIT}"; \
    curl -fsSL -o mlops.tar.gz "https://codeload.github.com/${MLOPS_REPO}/tar.gz/${MLOPS_COMMIT}"; \
    echo "${DATA_MAP_ARCHIVE_SHA256}  data-map.tar.gz" | sha256sum -c -; \
    echo "${MLOPS_ARCHIVE_SHA256}  mlops.tar.gz" | sha256sum -c -; \
    pip install --no-cache-dir --no-deps ./data-map.tar.gz ./mlops.tar.gz; \
    tar -xzf data-map.tar.gz --strip-components=2 -C /opt/public-demo/dags "${DATA_MAP_REPO#*/}-${DATA_MAP_COMMIT}/dags/education_siope_annual_update.py"; \
    tar -xzf mlops.tar.gz --strip-components=2 -C /opt/public-demo/dags "${MLOPS_REPO#*/}-${MLOPS_COMMIT}/dags/education_monitoring_demo.py"; \
    rm -f data-map.tar.gz mlops.tar.gz; \
    ls /opt/public-demo/dags
ENV AIRFLOW__CORE__DAGS_FOLDER=/opt/public-demo/dags
LABEL org.opencontainers.image.title="airflow-public-demo" \
      org.opencontainers.image.description="Pinned Airflow plus owner-repository DAGs at verified commits; local build"
