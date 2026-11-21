(() => {
  const profileId = new URLSearchParams(window.location.search).get("profile");
  const form = document.querySelector("#unlock-form");
  const pinInput = document.querySelector("#pin");
  const status = document.querySelector("#status");
  const unlockPanel = document.querySelector("#unlock-panel");
  const cardPanel = document.querySelector("#card");
  const facts = document.querySelector("#facts");
  let unlockedCard = null;

  function showStatus(message) {
    status.textContent = message;
  }

  function addFact(title, value, { alert = false, contacts = false, note = "" } = {}) {
    const article = document.createElement("article");
    if (alert) article.classList.add("alert");
    const heading = document.createElement("h3");
    heading.textContent = title;
    article.append(heading);

    if (contacts) {
      if (Array.isArray(value) && value.length > 0) {
        for (const contact of value) {
          const paragraph = document.createElement("p");
          const phone = String(contact.phone_number || "");
          paragraph.textContent = `${contact.full_name || "Contact"}${contact.relationship_label ? ` · ${contact.relationship_label}` : ""} · ${phone}`;
          const link = document.createElement("a");
          link.href = `tel:${phone.replace(/[^\d+*#;,]/g, "")}`;
          link.textContent = `Call · कॉल करें`;
          article.append(paragraph, link);
        }
      } else {
        const paragraph = document.createElement("p");
        paragraph.textContent = "Not recorded · दर्ज नहीं है";
        article.append(paragraph);
      }
    } else {
      const paragraph = document.createElement("p");
      paragraph.textContent = value ? String(value) : "Not recorded · दर्ज नहीं है";
      article.append(paragraph);
    }

    if (note) {
      const hint = document.createElement("p");
      hint.className = "synced";
      hint.textContent = note;
      article.append(hint);
    }
    facts.append(article);
  }

  function renderCard(result) {
    const card = result.card;
    unlockedCard = card;
    document.querySelector("#patient-name").textContent = card.full_name || "Patient · मरीज़";
    const synced = new Date(result.lastSyncedAt);
    document.querySelector("#last-synced").textContent = Number.isNaN(synced.valueOf())
      ? "Last synced date unavailable · पिछली सिंक तिथि उपलब्ध नहीं"
      : `Last synced · पिछली सिंक: ${synced.toLocaleString()}`;
    facts.replaceChildren();
    const selected = new Set(card.fields || []);
    if (selected.has("blood_group")) addFact("Blood group · रक्त समूह", card.blood_group);
    if (selected.has("known_allergies")) addFact("Known allergies · ज्ञात एलर्जी", card.known_allergies, { alert: true });
    if (selected.has("major_conditions")) addFact("Conditions · स्वास्थ्य स्थितियाँ", card.major_conditions);
    if (selected.has("current_medications")) {
      addFact("Medications · दवाएँ", card.current_medications, {
        note: "Medication details may have changed. Verify before use. · दवाएँ बदल सकती हैं; पहले पुष्टि करें।",
      });
    }
    if (selected.has("emergency_contacts")) {
      addFact("Emergency contacts · आपातकालीन संपर्क", card.emergency_contacts, { contacts: true });
    }
    unlockPanel.hidden = true;
    cardPanel.hidden = false;
    showStatus("");
  }

  async function initialize() {
    if (!profileId) {
      showStatus("Open this page using the Offline card link in your signed-in Emergency profile. · अपने Emergency profile से Offline card लिंक खोलें।");
      form.querySelector("button").disabled = true;
      return;
    }
    if (!window.isSecureContext || !crypto.subtle || !window.indexedDB) {
      showStatus("Secure offline storage is unavailable in this browser. · इस ब्राउज़र में सुरक्षित ऑफलाइन संग्रह उपलब्ध नहीं है।");
      form.querySelector("button").disabled = true;
      return;
    }
    try {
      const exists = await window.MedicalPassportOfflineCard.hasCard(profileId);
      if (!exists) {
        showStatus("No offline card is saved for this profile on this device. · इस डिवाइस पर इस प्रोफ़ाइल का ऑफलाइन कार्ड सेव नहीं है।");
      }
    } catch {
      showStatus("Could not read offline storage. · ऑफलाइन संग्रह नहीं पढ़ सके।");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!profileId) return;
    try {
      const result = await window.MedicalPassportOfflineCard.unlock(profileId, pinInput.value);
      pinInput.value = "";
      renderCard(result);
    } catch {
      pinInput.value = "";
      showStatus("Card unavailable or PIN did not match. · कार्ड उपलब्ध नहीं है या PIN गलत है।");
      pinInput.focus();
    }
  });

  document.querySelector("#lock-button").addEventListener("click", () => {
    unlockedCard = null;
    facts.replaceChildren();
    document.querySelector("#patient-name").textContent = "";
    document.querySelector("#last-synced").textContent = "";
    cardPanel.hidden = true;
    unlockPanel.hidden = false;
    showStatus("Card locked. · कार्ड बंद है।");
    pinInput.focus();
  });

  document.querySelector("#remove-button").addEventListener("click", async () => {
    if (!profileId || !window.confirm("Remove this encrypted card from this device? · इस एन्क्रिप्टेड कार्ड को डिवाइस से हटाएँ?")) return;
    try {
      await window.MedicalPassportOfflineCard.remove(profileId);
      unlockedCard = null;
      facts.replaceChildren();
      cardPanel.hidden = true;
      unlockPanel.hidden = false;
      showStatus("Offline card removed from this device. · ऑफलाइन कार्ड इस डिवाइस से हटा दिया गया है।");
      form.querySelector("button").disabled = true;
    } catch {
      showStatus("Could not remove the offline card. · ऑफलाइन कार्ड नहीं हटा सके।");
    }
  });

  initialize();
})();
