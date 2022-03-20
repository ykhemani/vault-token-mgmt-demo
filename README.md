# Vault Token Management in Python

When we integrate [HashiCorp](https://hashicorp.com) [Vault](https://vaultproject.io) into an application, we need to manage the renewal of our Vault token and leases for dynamic secrets.

This repo includes some sample code for applications written in [Python](https://www.python.org/) and using the [HVAC](https://hvac.readthedocs.io/en/stable/overview.html) library.

## Requirements

### Vault Cluster

We will need access to a Vault cluster on which we can create policies, mount a database secret engine, configure that secret engine, and create roles on that secret engine.

Set the `VAULT_ADDR` environment variable to the address of the Vault cluster.

Set the `VAULT_TOKEN` environment variable to the token that has privileges described above.

### Postgresql Database

We will need a Postgressql database server on which we can create dynamic, short-lived users.

Set the `PGDBHOST` environment variable to the hostname of the Postgresql server.
Set the `PGDB_VAULT_USER` environment variable to the user Vault will use to manage roles and grants on the database server.
Set the `PGDB_VAULT_PASSWORD` environment variable to the password of the Vault Postgresql user.

## Setup

The [setup.sh](setup.sh) script creates a creates a database secrets engine, configures is to talk to the Postgresql database, creates a role for creating dynamic users on that database, creates a policy enabling our Python application to use that role, and creates a token role that will be used to generate a token that our Python application will use to authenticate with Vault.

## Running the application

The [run.sh](run.sh) script will create a token using the token role created in the setup script, and run the Python application.

## Lease management in Python

When our application authenticates with Vault, it gets a token that has associated with it a certain validity period or time to live (TTL).

When we reach the half-life of that token (ttl/2), a Timer thread will renew that token.

```
    t_renew_token = Timer(ttl/2, renew_token)
    t_renew_token.daemon = True
    t_renew_token.start()
```

### `renew_token` function
```
def renew_token():
  logging.info("Renewing token")
  client.auth.token.renew_self()
  token = client.auth.token.lookup_self()
  ttl = token['data']['ttl']
  logging.info("Token TTL after renewal: %s", ttl)
  Timer(ttl/2,renew_token).start()
```

When the token is renewed, another Timer thread is created that will call the `renew_token` function when the half-life of the token is reached.

Similarly, when our application obtains a dynamic credential, the lease associated with that dynamic credential must be renewed. 

In our application, when we reach the half-life of that lease, a Timer thread renews the lease.

```
  t_renew_lease = Timer(postgres_ttl/2, renew_lease, [postgres_lease_id])
  t_renew_lease.daemon = True
  t_renew_lease.start()
```

### `renew_lease` function

```
def renew_lease(lease_id):
  logging.info("Renewing lease %s", lease_id)
  renew = client.sys.renew_lease(lease_id=lease_id)
  ttl = renew["lease_duration"]
  logging.info("Renewed lease %s. New TTL: %s", lease_id, ttl)
  Timer(ttl/2, renew_lease,[lease_id]).start()
```

When the lease is renewed, another Timer thread is created that will call the `renew_lease` function when the half-life of the lease is reached.

## `token_watch` and `lease_watch`

You'll note that we also have the `token_watch` and `lease_watch` functions. We don't need to implement these in our real application. They are there as part of this demo so that we can see the TTL count down over time.

## Sample Output

```
$ ./run.sh 
2022-03-20 02:03:34 UTC: Starting vault-token-mgmt-demo.py
2022-03-20 02:03:34 UTC: token_watch_enabled: True
2022-03-20 02:03:34 UTC: Token TTL at creation: 60
2022-03-20 02:03:34 UTC: Token TTL: 59
2022-03-20 02:03:34 UTC: Starting token watch.
2022-03-20 02:03:34 UTC: Postgres dynamic database credentials obtained.
2022-03-20 02:03:34 UTC: Postgres Lease ID:  postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc
2022-03-20 02:03:34 UTC: Postgres Lease TTL: 120
 * Serving Flask app 'vault-token-mgmt-demo' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
2022-03-20 02:03:34 UTC:  * Running on all addresses.
   WARNING: This is a development server. Do not use it in a production deployment.
2022-03-20 02:03:34 UTC:  * Running on http://192.168.51.68:80/ (Press CTRL+C to quit)
2022-03-20 02:03:39 UTC: token_watch: Token TTL: 54
2022-03-20 02:03:39 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 115
2022-03-20 02:03:44 UTC: token_watch: Token TTL: 49
2022-03-20 02:03:44 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 110
2022-03-20 02:03:49 UTC: token_watch: Token TTL: 44
2022-03-20 02:03:49 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 105
2022-03-20 02:03:54 UTC: token_watch: Token TTL: 39
2022-03-20 02:03:54 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 100
2022-03-20 02:03:59 UTC: token_watch: Token TTL: 34
2022-03-20 02:03:59 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 95
2022-03-20 02:04:03 UTC: Renewing token
2022-03-20 02:04:03 UTC: Token TTL after renewal: 59
2022-03-20 02:04:04 UTC: token_watch: Token TTL: 59
2022-03-20 02:04:04 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 90
2022-03-20 02:04:09 UTC: token_watch: Token TTL: 54
2022-03-20 02:04:09 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 85
2022-03-20 02:04:14 UTC: token_watch: Token TTL: 49
2022-03-20 02:04:14 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 79
2022-03-20 02:04:19 UTC: token_watch: Token TTL: 44
2022-03-20 02:04:19 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 74
2022-03-20 02:04:24 UTC: token_watch: Token TTL: 39
2022-03-20 02:04:24 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 69
2022-03-20 02:04:29 UTC: token_watch: Token TTL: 33
2022-03-20 02:04:29 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 64
2022-03-20 02:04:33 UTC: Renewing token
2022-03-20 02:04:33 UTC: Token TTL after renewal: 60
2022-03-20 02:04:34 UTC: Renewing lease postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc
2022-03-20 02:04:34 UTC: Renewed lease postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. New TTL: 120
2022-03-20 02:04:34 UTC: token_watch: Token TTL: 58
2022-03-20 02:04:34 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 119
2022-03-20 02:04:39 UTC: token_watch: Token TTL: 53
2022-03-20 02:04:39 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 114
2022-03-20 02:04:44 UTC: token_watch: Token TTL: 48
2022-03-20 02:04:44 UTC: lease_watch: postgres/creds/demo-role/TeQSRYJpJL6LLjy5HUPNOXgc. TTL: 109
^C2022-03-20 02:04:44 UTC: CTRL-C pressed.
2022-03-20 02:04:44 UTC: Revoking Vault token.
2022-03-20 02:04:45 UTC: Exiting.
```

## Sample Output with Watches Disabled

```
$ ./run.sh 
2022-03-20 02:05:31 UTC: Starting vault-token-mgmt-demo.py
2022-03-20 02:05:31 UTC: token_watch_enabled: False
2022-03-20 02:05:31 UTC: Token TTL at creation: 60
2022-03-20 02:05:31 UTC: Token TTL: 59
2022-03-20 02:05:32 UTC: Postgres dynamic database credentials obtained.
2022-03-20 02:05:32 UTC: Postgres Lease ID:  postgres/creds/demo-role/E6iDpM4zchfYvkOYx18iK1Ev
2022-03-20 02:05:32 UTC: Postgres Lease TTL: 120
 * Serving Flask app 'vault-token-mgmt-demo' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
2022-03-20 02:05:32 UTC:  * Running on all addresses.
   WARNING: This is a development server. Do not use it in a production deployment.
2022-03-20 02:05:32 UTC:  * Running on http://192.168.51.68:80/ (Press CTRL+C to quit)
2022-03-20 02:06:01 UTC: Renewing token
2022-03-20 02:06:01 UTC: Token TTL after renewal: 59
2022-03-20 02:06:31 UTC: Renewing token
2022-03-20 02:06:31 UTC: Token TTL after renewal: 60
2022-03-20 02:06:32 UTC: Renewing lease postgres/creds/demo-role/E6iDpM4zchfYvkOYx18iK1Ev
2022-03-20 02:06:32 UTC: Renewed lease postgres/creds/demo-role/E6iDpM4zchfYvkOYx18iK1Ev. New TTL: 120
2022-03-20 02:07:01 UTC: Renewing token
2022-03-20 02:07:01 UTC: Token TTL after renewal: 60
2022-03-20 02:07:31 UTC: Renewing token
2022-03-20 02:07:31 UTC: Token TTL after renewal: 60
2022-03-20 02:07:32 UTC: Renewing lease postgres/creds/demo-role/E6iDpM4zchfYvkOYx18iK1Ev
2022-03-20 02:07:32 UTC: Renewed lease postgres/creds/demo-role/E6iDpM4zchfYvkOYx18iK1Ev. New TTL: 120
2022-03-20 02:08:01 UTC: Renewing token
2022-03-20 02:08:01 UTC: Token TTL after renewal: 60
^C2022-03-20 02:08:08 UTC: CTRL-C pressed.
2022-03-20 02:08:08 UTC: Revoking Vault token.

```

---
