# Backup and restore checklist

Treat the database, document volume, and Fernet key set as one recovery unit. Schedule a quiet window or use coordinated snapshots so the database and files represent the same point in time.

1. Create an access-controlled destination outside the repository. Restrict outbound mail and public access during a restore rehearsal.
2. Dump PostgreSQL:

   ```sh
   docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > medical-passport.dump
   ```

3. Snapshot the Compose `document_data` volume read-only using the deployment's volume backup tooling. If using a tar archive, mount the actual Compose volume name read-only into a trusted backup job and write the archive to an encrypted destination.
4. Back up `SECRET_KEY` and every active or retained `DOCUMENT_ENCRYPTION_KEYS` version in the managed secret store. Keep key backups separately from database and volume archives. Never place secret values in this repository or backup logs.
5. Record the release commit, backup timestamp, volume/database pairing, and encryption key version identifiers. Verify archive checksums without printing or copying key values.
6. For a restore rehearsal, restore the dump and volume together into an isolated network, provide the matching keys through the secret store, and run `alembic upgrade head`, `/readyz`, a profile/timeline read, and a read/decrypt of a designated synthetic document.
7. Record the restore result and recovery time. Destroy the isolated copy under the retention policy. Keep the keys needed to decrypt every retained backup.

Do not treat a successful database dump alone as a complete Medical Passport backup. A metadata row without its document blob or required decryption key cannot be fully restored.
