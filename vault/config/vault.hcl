storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8201"
  tls_disable = 1  # В production нужно включить TLS
  tcp_keep_alive = true
}

api_addr = "http://vault:8201"
cluster_addr = "http://vault:8201"

ui = true

# Настройки для production
disable_mlock = false
default_lease_ttl = "168h"
max_lease_ttl = "720h"

# В production нужно настроить seal
# seal "transit" {
#   address = "https://vault-transit:8200"
#   token   = "s.xxxxx"
#   disable_renewal = "false"
#   key_name = "autounseal"
#   mount_path = "transit/"
#   tls_skip_verify = "true"
# } 