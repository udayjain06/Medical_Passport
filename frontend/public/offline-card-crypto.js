(() => {
  const DATABASE = "medical-passport-offline-v1";
  const STORE = "cards";
  const ITERATIONS = 310000;
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();

  function openDatabase() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DATABASE, 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore(STORE, { keyPath: "profileId" });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function readRecord(profileId) {
    const database = await openDatabase();
    try {
      return await new Promise((resolve, reject) => {
        const request = database.transaction(STORE, "readonly").objectStore(STORE).get(profileId);
        request.onsuccess = () => resolve(request.result || null);
        request.onerror = () => reject(request.error);
      });
    } finally {
      database.close();
    }
  }

  async function writeRecord(record) {
    const database = await openDatabase();
    try {
      await new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE, "readwrite");
        transaction.objectStore(STORE).put(record);
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
      });
    } finally {
      database.close();
    }
  }

  async function deriveKey(pin, salt) {
    const material = await crypto.subtle.importKey(
      "raw",
      encoder.encode(pin),
      "PBKDF2",
      false,
      ["deriveKey"],
    );
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: ITERATIONS, hash: "SHA-256" },
      material,
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt", "decrypt"],
    );
  }

  async function hasCard(profileId) {
    return Boolean(await readRecord(profileId));
  }

  async function metadata(profileId) {
    const record = await readRecord(profileId);
    return record
      ? { fields: record.fields, lastSyncedAt: record.lastSyncedAt }
      : null;
  }

  async function save(profileId, card, pin) {
    if (!/^\d{8,64}$/.test(pin)) throw new Error("PIN must contain at least 8 digits.");
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(pin, salt);
    const cleartext = encoder.encode(JSON.stringify(card));
    const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, cleartext);
    await writeRecord({
      profileId,
      salt,
      iv,
      iterations: ITERATIONS,
      ciphertext,
      fields: card.fields,
      lastSyncedAt: card.lastSyncedAt,
      version: 1,
    });
  }

  async function unlock(profileId, pin) {
    const record = await readRecord(profileId);
    if (!record || record.version !== 1 || record.iterations !== ITERATIONS) {
      throw new Error("Card unavailable.");
    }
    const key = await deriveKey(pin, record.salt);
    const cleartext = await crypto.subtle.decrypt({ name: "AES-GCM", iv: record.iv }, key, record.ciphertext);
    return {
      card: JSON.parse(decoder.decode(cleartext)),
      lastSyncedAt: record.lastSyncedAt,
    };
  }

  async function remove(profileId) {
    const database = await openDatabase();
    try {
      await new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE, "readwrite");
        transaction.objectStore(STORE).delete(profileId);
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
      });
    } finally {
      database.close();
    }
  }

  window.MedicalPassportOfflineCard = Object.freeze({ hasCard, metadata, save, unlock, remove });
})();
