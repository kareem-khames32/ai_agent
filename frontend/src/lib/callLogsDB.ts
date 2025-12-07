/**
 * IndexedDB Storage for Call Logs
 * Can store much more data than localStorage (50MB+ vs 5MB)
 */

export interface CallLogEntry {
  id: string;
  assistantId: string;
  assistantName: string;
  startTime: string;
  endTime: string;
  duration: number;
  status: string;
  transcript: Array<{ role: string; text: string; timestamp: string }>;
  metadata: {
    llmProvider: string;
    llmModel: string;
    ttsProvider: string;
    sttProvider: string;
    language: string;
  };
  cost?: {
    total_cost: number;
    call_duration: number;
    recording_id?: string;
    stt_cost?: number;
    llm_cost?: number;
    tts_cost?: number;
  };
  latency?: {
    avgResponseTime: number;
    sttLatency: number;
    llmLatency: number;
    ttsLatency: number;
  };
  waveform?: number[];
}

const DB_NAME = 'VoiceAICallLogs';
const DB_VERSION = 1;
const STORE_NAME = 'callLogs';

let db: IDBDatabase | null = null;

/**
 * Open/Create the IndexedDB database
 */
export async function openDB(): Promise<IDBDatabase> {
  if (db) return db;

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      console.error('Failed to open IndexedDB:', request.error);
      reject(request.error);
    };

    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result;

      // Create object store with id as key
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'id' });
        // Create indexes for searching
        store.createIndex('startTime', 'startTime', { unique: false });
        store.createIndex('assistantId', 'assistantId', { unique: false });
        store.createIndex('assistantName', 'assistantName', { unique: false });
      }
    };
  });
}

/**
 * Save a call log
 */
export async function saveCallLog(callLog: CallLogEntry): Promise<void> {
  const database = await openDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    const request = store.put(callLog);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

/**
 * Get all call logs (sorted by startTime descending)
 */
export async function getAllCallLogs(): Promise<CallLogEntry[]> {
  const database = await openDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const index = store.index('startTime');

    const request = index.openCursor(null, 'prev'); // Descending order
    const results: CallLogEntry[] = [];

    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        results.push(cursor.value);
        cursor.continue();
      } else {
        resolve(results);
      }
    };

    request.onerror = () => reject(request.error);
  });
}

/**
 * Get paginated call logs
 */
export async function getCallLogsPaginated(
  page: number = 1,
  pageSize: number = 100
): Promise<{ logs: CallLogEntry[]; total: number; totalPages: number }> {
  const allLogs = await getAllCallLogs();
  const total = allLogs.length;
  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;
  const logs = allLogs.slice(start, start + pageSize);

  return { logs, total, totalPages };
}

/**
 * Get a single call log by ID
 */
export async function getCallLog(id: string): Promise<CallLogEntry | null> {
  const database = await openDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    const request = store.get(id);

    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Delete a call log
 */
export async function deleteCallLog(id: string): Promise<void> {
  const database = await openDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    const request = store.delete(id);

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

/**
 * Delete multiple call logs
 */
export async function deleteCallLogs(ids: string[]): Promise<void> {
  const database = await openDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    let completed = 0;

    ids.forEach(id => {
      const request = store.delete(id);
      request.onsuccess = () => {
        completed++;
        if (completed === ids.length) resolve();
      };
      request.onerror = () => reject(request.error);
    });

    if (ids.length === 0) resolve();
  });
}

/**
 * Get total count of call logs
 */
export async function getCallLogsCount(): Promise<number> {
  const database = await openDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    const request = store.count();

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Clear all call logs
 */
export async function clearAllCallLogs(): Promise<void> {
  const database = await openDB();

  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    const request = store.clear();

    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

/**
 * Migrate from localStorage to IndexedDB (one-time migration)
 */
export async function migrateFromLocalStorage(): Promise<number> {
  if (typeof window === 'undefined') return 0;

  const existingLogs = localStorage.getItem('call_logs');
  if (!existingLogs) return 0;

  try {
    const logs: CallLogEntry[] = JSON.parse(existingLogs);

    for (const log of logs) {
      await saveCallLog(log);
    }

    // Clear localStorage after successful migration
    localStorage.removeItem('call_logs');
    console.log(`✅ Migrated ${logs.length} call logs to IndexedDB`);

    return logs.length;
  } catch (e) {
    console.error('Migration failed:', e);
    return 0;
  }
}

/**
 * Get storage estimate
 */
export async function getStorageEstimate(): Promise<{ used: number; quota: number }> {
  if (navigator.storage && navigator.storage.estimate) {
    const estimate = await navigator.storage.estimate();
    return {
      used: estimate.usage || 0,
      quota: estimate.quota || 0,
    };
  }
  return { used: 0, quota: 0 };
}
