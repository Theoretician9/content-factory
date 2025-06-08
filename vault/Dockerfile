FROM vault:1.15.6

COPY config.hcl /vault/config/config.hcl

RUN mkdir -p /vault/data && \
    chown -R vault:vault /vault/data

USER vault 