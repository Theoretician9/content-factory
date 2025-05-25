storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8202"
  tls_disable = 1  # В dev режиме отключаем TLS
}

api_addr = "http://0.0.0.0:8202"
cluster_addr = "https://0.0.0.0:8203"

ui = true
disable_mlock = true 