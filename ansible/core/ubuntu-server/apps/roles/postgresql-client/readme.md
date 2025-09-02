# Ansible Role: postgresql-client
This role installs the **PostgreSQL client tools** (pg_dump, psql, etc.) of a specific version
on Debian/Ubuntu using the official PostgreSQL Global Development Group (PGDG) repository.
## Variables

```yaml
pg_major: "16"  # PostgreSQL major version
pgdg_keyring_path: /etc/apt/keyrings/postgresql.gpg
pgdg_repo: "http://apt.postgresql.org/pub/repos/apt"