#!/bin/bash
# Backup original auth.rs
cp auth.rs auth.rs.bak

# Use sed to patch the auth.rs file
sed -i "217,218c/.if skip_auth {/if skip_auth || request.uri().path().contains(\"\\/webhook\") {\\n                return inner.call(request).await;\\n            }/" auth.rs
sed -i 's,// Skip authentication if configured (dev mode)// Skip auth for webhooks/' auth.rs
cd ..
cargo run --bin coderabbit-api-gateway > ../logs/api-gateway.log 2>&1 &
