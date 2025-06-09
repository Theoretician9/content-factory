#!/bin/bash

echo "=== Test Unsealer ==="
echo "VAULT_ADDR: $VAULT_ADDR"

# Test if environment variables are set
for i in {1..5}; do
    key_var="VAULT_UNSEAL_KEY_$i"
    eval "key_value=\${$key_var:-}"
    if [[ -n "$key_value" ]]; then
        echo "✅ $key_var is set (length: ${#key_value})"
    else
        echo "❌ $key_var is not set"
    fi
done

# Test Vault connectivity
echo "Testing Vault connectivity..."
if curl -s --connect-timeout 5 --max-time 10 "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
    echo "✅ Vault is reachable"
    
    # Get status
    echo "Getting Vault status..."
    status=$(curl -s "$VAULT_ADDR/v1/sys/seal-status")
    echo "Status: $status"
    
    sealed=$(echo "$status" | jq -r '.sealed // true')
    echo "Sealed: $sealed"
    
    if [[ "$sealed" == "true" ]]; then
        echo "🔒 Vault is sealed, attempting unseal..."
        
        # Try first key
        eval "key1=\${VAULT_UNSEAL_KEY_1:-}"
        if [[ -n "$key1" ]]; then
            echo "Trying first unseal key..."
            response=$(curl -s -X POST \
                -H "Content-Type: application/json" \
                -d "{\"key\":\"$key1\"}" \
                "$VAULT_ADDR/v1/sys/unseal")
            echo "Response: $response"
        fi
    else
        echo "🔓 Vault is already unsealed"
    fi
else
    echo "❌ Vault is not reachable"
fi

echo "=== Test Complete ===" 