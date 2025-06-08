FROM vault:1.13.3

COPY config.hcl /vault/config/config.hcl

RUN mkdir -p /vault/data

# Не меняем владельца, так как будем использовать user в docker-compose 