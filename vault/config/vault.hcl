storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8201"
  tls_disable = 1  # В production нужно включить TLS
}

api_addr = "http://vault:8201"
cluster_addr = "http://vault:8201"

ui = true

# Настройки для production
disable_mlock = false
default_lease_ttl = "168h"
max_lease_ttl = "720h"

# Настройки для стабильности
log_level = "debug"
cluster_name = "vault-cluster"

# В production нужно настроить seal
# seal "transit" {
#   address = "https://vault-transit:8200"
#   token   = "s.xxxxx"
#   disable_renewal = "false"
#   key_name = "autounseal"
#   mount_path = "transit/"
#   tls_skip_verify = "true"
# } 