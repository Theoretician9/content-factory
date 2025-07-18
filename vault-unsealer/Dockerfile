FROM alpine:3.18

# Install required packages
RUN apk add --no-cache \
    bash \
    curl \
    jq \
    ca-certificates

# Create non-root user
RUN adduser -D -s /bin/bash unsealer

# Create working directory
WORKDIR /app

# Copy unsealing script
COPY unseal.sh /app/unseal.sh
COPY test-unseal.sh /app/test-unseal.sh
RUN chmod +x /app/unseal.sh /app/test-unseal.sh

# Switch to non-root user
USER unsealer

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://vault:8201/v1/sys/health || exit 1

# Run unsealing script or test script
CMD ["/bin/sh", "-c", "if [ \"$UNSEALER_TEST_MODE\" = \"true\" ]; then /app/test-unseal.sh; else /app/unseal.sh; fi"] 