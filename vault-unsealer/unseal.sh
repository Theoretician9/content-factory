#!/bin/bash

# Vault Unsealer Service
# Production-ready automatic unsealing for HashiCorp Vault

set -euo pipefail

# Configuration
VAULT_ADDR="${VAULT_ADDR:-http://vault:8201}"
MAX_RETRIES="${UNSEALER_MAX_RETRIES:-50}"
RETRY_DELAY="${UNSEALER_RETRY_DELAY:-5}"
MONITOR_INTERVAL="${UNSEALER_MONITOR_INTERVAL:-30}"
LOG_LEVEL="${UNSEALER_LOG_LEVEL:-INFO}"

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Structured logging function
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
    
    case $level in
        ERROR) echo -e "${RED}[$timestamp] ERROR: $message${NC}" >&2 ;;
        WARN)  echo -e "${YELLOW}[$timestamp] WARN:  $message${NC}" ;;
        INFO)  echo -e "${GREEN}[$timestamp] INFO:  $message${NC}" ;;
        DEBUG) [[ "$LOG_LEVEL" == "DEBUG" ]] && echo -e "${BLUE}[$timestamp] DEBUG: $message${NC}" ;;
    esac
}

# Check if unseal keys are provided
check_unseal_keys() {
    local keys_found=0
    for i in {1..5}; do
        local key_var="VAULT_UNSEAL_KEY_$i"
        local key_value=""
        eval "key_value=\${$key_var:-}"
        if [[ -n "$key_value" ]]; then
            ((keys_found++))
            log "DEBUG" "Found unseal key $i"
        else
            log "DEBUG" "Unseal key $i not set"
        fi
    done
    
    if [[ $keys_found -lt 3 ]]; then
        log "ERROR" "Insufficient unseal keys provided. Found: $keys_found, Required: at least 3"
        log "ERROR" "Please set VAULT_UNSEAL_KEY_1, VAULT_UNSEAL_KEY_2, VAULT_UNSEAL_KEY_3 in .env file"
        exit 1
    fi
    
    log "INFO" "Found $keys_found unseal keys"
    return 0
}

# Wait for Vault to be reachable
wait_for_vault() {
    local attempt=1
    log "INFO" "Waiting for Vault to be reachable at $VAULT_ADDR"
    
    while [[ $attempt -le $MAX_RETRIES ]]; do
        if curl -s --connect-timeout 5 --max-time 10 "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
            log "INFO" "Vault is reachable (attempt $attempt/$MAX_RETRIES)"
            return 0
        fi
        
        log "DEBUG" "Vault not reachable, attempt $attempt/$MAX_RETRIES"
        sleep $RETRY_DELAY
        ((attempt++))
    done
    
    log "ERROR" "Vault is not reachable after $MAX_RETRIES attempts"
    return 1
}

# Get Vault status
get_vault_status() {
    local status_response
    if status_response=$(curl -s --connect-timeout 5 --max-time 10 "$VAULT_ADDR/v1/sys/seal-status" 2>/dev/null); then
        echo "$status_response"
        return 0
    else
        log "ERROR" "Failed to get Vault status"
        return 1
    fi
}

# Check if Vault is sealed
is_vault_sealed() {
    local status
    if status=$(get_vault_status); then
        local sealed=$(echo "$status" | jq -r '.sealed')
        [[ "$sealed" == "true" ]]
    else
        return 1
    fi
}

# Check if Vault is initialized
is_vault_initialized() {
    local status
    if status=$(get_vault_status); then
        local initialized=$(echo "$status" | jq -r '.initialized')
        [[ "$initialized" == "true" ]]
    else
        return 1
    fi
}

# Perform unseal operation
unseal_vault() {
    log "INFO" "Starting Vault unseal process"
    
    # Check if Vault is initialized
    if ! is_vault_initialized; then
        log "ERROR" "Vault is not initialized. Manual initialization required."
        return 1
    fi
    
    # Check current seal status
    if ! is_vault_sealed; then
        log "INFO" "Vault is already unsealed"
        return 0
    fi
    
    local unseal_count=0
    local required_keys=3
    
    # Get current progress
    local status
    if status=$(get_vault_status); then
        local progress=$(echo "$status" | jq -r '.progress // 0')
        local threshold=$(echo "$status" | jq -r '.t // 3')
        required_keys=$threshold
        log "INFO" "Current unseal progress: $progress/$threshold"
    fi
    
    # Apply unseal keys
    for i in {1..5}; do
        local key_var="VAULT_UNSEAL_KEY_$i"
        local key=""
        eval "key=\${$key_var:-}"
        
        if [[ -n "$key" ]]; then
            log "DEBUG" "Applying unseal key $i"
            
            local unseal_response
            if unseal_response=$(curl -s --connect-timeout 10 --max-time 15 \
                -X POST \
                -H "Content-Type: application/json" \
                -d "{\"key\":\"$key\"}" \
                "$VAULT_ADDR/v1/sys/unseal" 2>/dev/null); then
                
                local sealed=$(echo "$unseal_response" | jq -r '.sealed // true')
                local progress=$(echo "$unseal_response" | jq -r '.progress // 0')
                local threshold=$(echo "$unseal_response" | jq -r '.t // 3')
                
                log "INFO" "Unseal progress: $progress/$threshold"
                ((unseal_count++))
                
                if [[ "$sealed" == "false" ]]; then
                    log "INFO" "✅ Vault successfully unsealed!"
                    return 0
                fi
                
                if [[ $unseal_count -ge $required_keys ]]; then
                    break
                fi
            else
                log "ERROR" "Failed to apply unseal key $i"
            fi
        fi
    done
    
    # Verify final status
    if ! is_vault_sealed; then
        log "INFO" "✅ Vault successfully unsealed!"
        return 0
    else
        log "ERROR" "❌ Failed to unseal Vault after applying $unseal_count keys"
        return 1
    fi
}

# Monitor Vault status continuously
monitor_vault() {
    log "INFO" "Starting continuous Vault monitoring (interval: ${MONITOR_INTERVAL}s)"
    
    while true; do
        if is_vault_sealed; then
            log "WARN" "🔒 Vault became sealed, attempting to unseal..."
            if unseal_vault; then
                log "INFO" "✅ Vault re-unsealed successfully"
            else
                log "ERROR" "❌ Failed to re-unseal Vault"
            fi
        else
            log "DEBUG" "🔓 Vault status: unsealed"
        fi
        
        sleep $MONITOR_INTERVAL
    done
}

# Signal handlers for graceful shutdown
cleanup() {
    log "INFO" "Unsealer service shutting down gracefully"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Main execution
main() {
    log "INFO" "🚀 Vault Unsealer Service starting up"
    log "INFO" "Configuration: VAULT_ADDR=$VAULT_ADDR, MAX_RETRIES=$MAX_RETRIES, RETRY_DELAY=${RETRY_DELAY}s"
    
    # Validate environment
    log "DEBUG" "Checking unseal keys..."
    if ! check_unseal_keys; then
        log "ERROR" "❌ Unseal keys validation failed"
        exit 1
    fi
    log "DEBUG" "Unseal keys validation passed"
    
    # Wait for Vault to be available
    log "DEBUG" "Waiting for Vault..."
    if ! wait_for_vault; then
        log "ERROR" "❌ Failed to connect to Vault"
        exit 1
    fi
    log "DEBUG" "Vault connection established"
    
    # Perform initial unseal
    log "DEBUG" "Starting initial unseal..."
    if unseal_vault; then
        log "INFO" "✅ Initial unseal completed successfully"
    else
        log "ERROR" "❌ Initial unseal failed"
        exit 1
    fi
    
    # Start monitoring
    log "DEBUG" "Starting monitoring loop..."
    monitor_vault
}

# Run main function
main "$@" 