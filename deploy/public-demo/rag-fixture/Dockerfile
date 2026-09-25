# LOCAL FIXTURE STAND-IN for the ai-platform-rag-observability image.
# It reuses this repository's runtime image and serves the same HTTP contract
# (POST /v1/answer, GET /healthz) from runtime_lab/rag_fixture.py. Replace it
# with the pinned RAG release digest in versions.env when one exists.
ARG RUNTIME_IMAGE
FROM ${RUNTIME_IMAGE}
LABEL org.opencontainers.image.title="rag-gateway-fixture" \
      org.opencontainers.image.description="Deterministic local stand-in for the RAG gateway contract; not the real RAG service"
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "runtime_lab.rag_fixture"]
