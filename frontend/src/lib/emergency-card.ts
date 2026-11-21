const DATABASE = "medical-passport-device-card";
const STORE = "cards";
const CARD_ID = "current";

type StoredCard = { id: string; salt: string; iv: string; ciphertext: string; lastSynced: string };
export type OfflineEmergencyCard = { data: Record<string, unknown>; lastSynced: string };

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function encode(data: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(data)));
}

function decode(value: string): Uint8Array<ArrayBuffer> {
  const decoded = atob(value);
  const bytes = new Uint8Array(decoded.length);
  for (let index = 0; index < decoded.length; index += 1) bytes[index] = decoded.charCodeAt(index);
  return bytes;
}

async function deriveKey(pin: string, salt: Uint8Array<ArrayBuffer>): Promise<CryptoKey> {
  const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(pin), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: 250_000, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

function saveRecord(record: StoredCard): Promise<void> {
  return openDatabase().then((database) => new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE, "readwrite");
    transaction.objectStore(STORE).put(record);
    transaction.oncomplete = () => { database.close(); resolve(); };
    transaction.onerror = () => { database.close(); reject(transaction.error); };
  }));
}

function readRecord(): Promise<StoredCard | undefined> {
  return openDatabase().then((database) => new Promise((resolve, reject) => {
    const request = database.transaction(STORE, "readonly").objectStore(STORE).get(CARD_ID);
    request.onsuccess = () => { database.close(); resolve(request.result as StoredCard | undefined); };
    request.onerror = () => { database.close(); reject(request.error); };
  }));
}

export async function saveEmergencyCard(pin: string, data: Record<string, unknown>): Promise<string> {
  if (pin.length < 6) throw new Error("Set a PIN with at least 6 characters.");
  if (!globalThis.crypto?.subtle || !globalThis.indexedDB) throw new Error("Encrypted device storage is not available in this browser.");
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(pin, salt);
  const lastSynced = new Date().toISOString();
  const plaintext = new TextEncoder().encode(JSON.stringify({ data, lastSynced }));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext);
  await saveRecord({ id: CARD_ID, salt: encode(salt.slice().buffer), iv: encode(iv.slice().buffer), ciphertext: encode(ciphertext), lastSynced });
  return lastSynced;
}

export async function unlockEmergencyCard(pin: string): Promise<OfflineEmergencyCard> {
  const record = await readRecord();
  if (!record) throw new Error("No emergency card is saved on this device.");
  const key = await deriveKey(pin, decode(record.salt));
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv: decode(record.iv), tagLength: 128 }, key, decode(record.ciphertext));
  return JSON.parse(new TextDecoder().decode(plaintext)) as OfflineEmergencyCard;
}

export async function removeEmergencyCard(): Promise<void> {
  const database = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE, "readwrite");
    transaction.objectStore(STORE).delete(CARD_ID);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  database.close();
}
