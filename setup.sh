#!/bin/bash

vault policy write python-hvac-demo - <<EOF
# postgres demo
path "postgres/creds/demo-role" {
  capabilities = ["read"]
}
EOF

# postgres
vault secrets disable postgres
vault secrets enable -path=postgres database
vault write postgres/config/postgres01 \
  plugin_name=postgresql-database-plugin \
  allowed_roles="demo-role" \
  connection_url="postgresql://{{username}}:{{password}}@${PGDBHOST}:5432/postgres?sslmode=disable" \
  username="${PGDB_VAULT_USER}" \
  password="${PGDB_VAULT_PASSWORD}"

vault write postgres/roles/demo-role \
    db_name=postgres01 \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}' INHERIT; \
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    default_ttl="2m" \
    max_ttl="24h"

# token role
curl -sk \
  --header "X-Vault-Token: ${VAULT_TOKEN}" \
  --request POST \
  --data @token-role-payload.json \
  ${VAULT_ADDR}/v1/auth/token/roles/python-hvac-demo
