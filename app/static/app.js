let currentBarcode = null;
let currentPhotoBase64 = null;
let html5QrCode = null;
let isScanning = false;

// 1. IndexedDB Initialization
const DB_NAME = "FieldKitLocalDB";
const STORE_NAME = "pending_scans";

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "client_uuid" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getQueueCount() {
  const db = await openDatabase();
  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const countReq = tx.objectStore(STORE_NAME).count();
    countReq.onsuccess = () => resolve(countReq.result);
  });
}

async function updateQueueCounter() {
  const count = await getQueueCount();
  document.getElementById("queue-count").textContent = count;
}

// 2. Network State Listeners & Automatic Offline Flush
window.addEventListener("online", () => {
  const badge = document.getElementById("network-badge");
  badge.textContent = "Online";
  badge.className = "badge online";
  showNotification("Network restored. Syncing offline records...", "#10b981");
  flushQueue();
});

window.addEventListener("offline", () => {
  const badge = document.getElementById("network-badge");
  badge.textContent = "Offline";
  badge.className = "badge offline";
  showNotification("Network lost. Working in offline cache mode.", "#ef4444");
});

// 3. Camera Barcode / QR Scanner
function toggleScanner() {
  const btn = document.getElementById("btn-scan");
  if (isScanning) {
    if (html5QrCode) {
      html5QrCode.stop().then(() => {
        isScanning = false;
        btn.textContent = "Start Camera Scan";
      });
    }
    return;
  }

  html5QrCode = new Html5Qrcode("reader");
  const config = { fps: 10, qrbox: { width: 220, height: 220 } };

  html5QrCode.start(
    { facingMode: "environment" },
    config,
    (decodedText) => {
      currentBarcode = decodedText;
      document.getElementById("scan-result").textContent = decodedText;
      html5QrCode.stop().then(() => {
        isScanning = false;
        btn.textContent = "Start Camera Scan";
      });
    }
  ).catch((err) => {
    console.warn("Camera init failed:", err);
    showNotification("Camera access denied or unavailable.", "#ef4444");
  });

  isScanning = true;
  btn.textContent = "Stop Camera";
}

// 4. Photo Capture & Base64 Compression
function onPhotoSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    currentPhotoBase64 = e.target.result;
    document.getElementById("photo-preview").innerHTML = `<img src="${currentPhotoBase64}" alt="Site Photo Preview" />`;
  };
  reader.readAsDataURL(file);
}

// 5. Submit Handler (Online Direct + Offline Queue Fallback)
async function handleSubmit() {
  if (!currentBarcode) {
    showNotification("Please scan a barcode or QR code first.", "#ef4444");
    return;
  }

  const record = {
    client_uuid: crypto.randomUUID(),
    barcode: currentBarcode,
    photo_payload: currentPhotoBase64 || null,
    timestamp: new Date().toISOString(),
    source: "mobile_field_pwa",
    type: "site_inspection"
  };

  if (navigator.onLine) {
    try {
      const res = await sendPayload(record);
      if (res.ok) {
        showNotification("Record synced directly to backend!", "#10b981");
        resetForm();
        return;
      }
    } catch (err) {
      console.warn("Direct upload failed despite online flag. Queuing locally.", err);
    }
  }

  // Save to IndexedDB
  const db = await openDatabase();
  const tx = db.transaction(STORE_NAME, "readwrite");
  tx.objectStore(STORE_NAME).put(record);
  tx.oncomplete = () => {
    showNotification("Stored offline in local queue. Will sync on network recovery.", "#f59e0b");
    updateQueueCounter();
    resetForm();
  };
}

async function sendPayload(payload) {
  return await fetch("/api/field/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

// 6. Queue Flush Routine
async function flushQueue() {
  const db = await openDatabase();
  const tx = db.transaction(STORE_NAME, "readonly");
  const store = tx.objectStore(STORE_NAME);
  const getAllReq = store.getAll();

  getAllReq.onsuccess = async () => {
    const items = getAllReq.result;
    if (items.length === 0) return;

    for (const item of items) {
      try {
        const res = await sendPayload(item);
        if (res.ok) {
          const deleteTx = db.transaction(STORE_NAME, "readwrite");
          deleteTx.objectStore(STORE_NAME).delete(item.client_uuid);
        }
      } catch (err) {
        console.warn("Failed syncing queue item:", err);
        break; // Stop iteration if connection drops again
      }
    }
    updateQueueCounter();
  };
}

function resetForm() {
  currentBarcode = null;
  currentPhotoBase64 = null;
  document.getElementById("scan-result").textContent = "None";
  document.getElementById("photo-preview").innerHTML = "";
}

function showNotification(msg, color) {
  const el = document.getElementById("status-msg");
  el.textContent = msg;
  el.style.display = "block";
  el.style.background = color;
  el.style.color = "#fff";
  setTimeout(() => { el.style.display = "none"; }, 4000);
}

// Initialize on load
updateQueueCounter();