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
        echo "🔒 Vault is sealed, attempting full unseal..."
        
        # Apply all 3 keys
        for i in {1..3}; do
            key_var="VAULT_UNSEAL_KEY_$i"
            eval "key=\${$key_var:-}"
            if [[ -n "$key" ]]; then
                echo "Trying unseal key $i..."
                response=$(curl -s -X POST \
                    -H "Content-Type: application/json" \
                    -d "{\"key\":\"$key\"}" \
                    "$VAULT_ADDR/v1/sys/unseal")
                echo "Response: $response"
                
                # Check if unsealed
                sealed_status=$(echo "$response" | jq -r '.sealed')
                progress=$(echo "$response" | jq -r '.progress // 0')
                threshold=$(echo "$response" | jq -r '.t // 3')
                echo "Progress: $progress/$threshold, Sealed: $sealed_status"
                
                if [[ "$sealed_status" == "false" ]]; then
                    echo "🎉 SUCCESS! Vault unsealed with key $i"
                    break
                fi
            fi
        done
        
        # Final check
        echo "Final status check..."
        final_status=$(curl -s "$VAULT_ADDR/v1/sys/seal-status")
        final_sealed=$(echo "$final_status" | jq -r '.sealed')
        if [[ "$final_sealed" == "false" ]]; then
            echo "✅ Vault is UNSEALED!"
        else
            echo "❌ Vault is still SEALED"
        fi
    else
        echo "🔓 Vault is already unsealed"
    fi
else
    echo "❌ Vault is not reachable"
fi

echo "=== Starting continuous monitoring (test mode) ==="

# Continuous monitoring loop for test mode
while true; do
    sleep 30
    echo "[$(date)] Checking Vault status..."
    
    status=$(curl -s "$VAULT_ADDR/v1/sys/seal-status")
    sealed=$(echo "$status" | jq -r '.sealed')
    
    if [[ "$sealed" == "false" ]]; then
        echo "✅ Vault is unsealed"
    else
        echo "⚠️  Vault became sealed, would attempt re-unseal..."
    fi
done 