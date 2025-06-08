FROM vault:1.13.3

COPY config.hcl /vault/config/config.hcl

RUN mkdir -p /vault/data && \
    chown -R vault:vault /vault/data

USER vault 