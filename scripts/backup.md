# Backup and restore rehearsal

Treat the PostgreSQL database, `document_data` volume, and document-encryption key set as one recovery unit. Keep backups encrypted and access controlled; never put keys in the backup archive or repository.

1. Pause writes or coordinate a consistent snapshot window.
2. Dump PostgreSQL: `docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > medical-passport.dump`.
3. Snapshot the `document_data` volume with the host's encrypted volume backup tool. Record the application revision and key-set identifier (not key values).
4. Back up the active encryption keys separately in an approved secret store. Keep every old key needed by retained backups.
5. Rehearse restoration in an isolated network with public traffic and outbound email disabled. Restore the database and matching document volume, restore keys through the secret store, then run `alembic upgrade head` and check `/readyz`.
6. Read and decrypt a designated synthetic document, verify profile/timeline metadata, record recovery time and outcome, then destroy the rehearsal environment under the retention policy.
