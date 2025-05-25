storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address = "0.0.0.0:8201"
  tls_disable = 1
}

log_level = "debug"
disable_mlock = true

api_addr = "http://0.0.0.0:8201"
cluster_addr = "https://0.0.0.0:8202"

ui = true 