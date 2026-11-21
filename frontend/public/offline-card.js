const unlockButton = document.querySelector("#unlock");
const removeButton = document.querySelector("#remove");
const pinInput = document.querySelector("#pin");
const statusText = document.querySelector("#status");
const syncedText = document.querySelector("#synced");
const cardView = document.querySelector("#card");

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("medical-passport-device-card", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("cards", { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function decode(value) {
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
}

async function getCard() {
  const database = await openDb();
  return new Promise((resolve, reject) => {
    const request = database.transaction("cards", "readonly").objectStore("cards").get("current");
    request.onsuccess = () => { database.close(); resolve(request.result); };
    request.onerror = () => { database.close(); reject(request.error); };
  });
}

unlockButton.addEventListener("click", async () => {
  try {
    const record = await getCard();
    if (!record) throw new Error("No card is saved on this device.");
    const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(pinInput.value), "PBKDF2", false, ["deriveKey"]);
    const key = await crypto.subtle.deriveKey({ name: "PBKDF2", salt: decode(record.salt), iterations: 250000, hash: "SHA-256" }, material, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
    const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv: decode(record.iv), tagLength: 128 }, key, decode(record.ciphertext));
    const card = JSON.parse(new TextDecoder().decode(plaintext));
    cardView.textContent = JSON.stringify(card.data, null, 2);
    cardView.hidden = false;
    removeButton.hidden = false;
    syncedText.textContent = `Last synced: ${new Date(card.lastSynced).toLocaleString()}`;
    statusText.textContent = "Card unlocked on this device.";
  } catch {
    cardView.hidden = true;
    removeButton.hidden = true;
    statusText.textContent = "Could not unlock the card. Check your PIN or save a card while online.";
  }
});

removeButton.addEventListener("click", async () => {
  const database = await openDb();
  await new Promise((resolve, reject) => {
    const transaction = database.transaction("cards", "readwrite");
    transaction.objectStore("cards").delete("current");
    transaction.oncomplete = resolve;
    transaction.onerror = () => reject(transaction.error);
  });
  database.close();
  cardView.hidden = true;
  removeButton.hidden = true;
  syncedText.textContent = "";
  statusText.textContent = "Emergency card removed from this device.";
});
