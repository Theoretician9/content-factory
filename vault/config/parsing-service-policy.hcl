path "kv/data/parsing-service" {
  capabilities = ["read"]
}
path "kv/data/jwt" {
  capabilities = ["read"]
}
path "kv/data/integrations/telegram" {
  capabilities = ["read"]
}
path "kv/data/integration-service" {
  capabilities = ["read"]
}
path "kv/data/telegram-sessions/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
path "kv/metadata/parsing-service" {
  capabilities = ["read"]
}
path "kv/metadata/jwt" {
  capabilities = ["read"]
}
path "kv/metadata/integrations/telegram" {
  capabilities = ["read"]
}
path "kv/metadata/integration-service" {
  capabilities = ["read"]
}
path "kv/metadata/telegram-sessions/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
} 