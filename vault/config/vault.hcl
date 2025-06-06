storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8201"
  tls_disable = 1
}

ui = true

api_addr = "http://0.0.0.0:8201"

default_lease_ttl = "168h"
max_lease_ttl = "720h" 