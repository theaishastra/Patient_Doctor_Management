// Detect environment and set API base URL
const BASE_URL = (() => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;

    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://127.0.0.1:8000';
    }

    // Production (same domain)
    return `${protocol}//${hostname}`;
  }
  return 'http://127.0.0.1:8000'; // Fallback
})();

// ==========================================
// Supabase Realtime Client (for chat subscriptions)
// ==========================================
const SUPABASE_URL = "https://lycbzpjckxdzuvpmtmsr.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx5Y2J6cGpja3hkeng1dnBtdG1zciIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNzMwMzU0ODEwLCJleHAiOjE4ODgxMzI4MTB9.sJGfHdP8JFWiCN5c9CZXhGKr6xDqLkh-Ju3Z32bEKFE";

// Initialize Supabase client for realtime subscriptions
// Check if Supabase library loaded (it comes from CDN)
let supabase = null;
if (window.supabase && typeof window.supabase.createClient === 'function') {
    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
} else {
    console.warn("Supabase library not loaded yet. Realtime chat will use polling instead.");
}

// Helper to get JWT token
function getAuthToken() {
    return localStorage.getItem("access_token");
}

// Helper to set authorization headers
function getHeaders(isMultipart = false) {
    const headers = {};
    if (!isMultipart) {
        headers["Content-Type"] = "application/json";
    }
    const token = getAuthToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
}

// Main API request handler
async function request(endpoint, options = {}) {
    const url = `${BASE_URL}${endpoint}`;
    
    // Add headers to options
    const isMultipart = options.body instanceof FormData;
    options.headers = {
        ...getHeaders(isMultipart),
        ...(options.headers || {})
    };

    try {
        const response = await fetch(url, options);
        
        // Handle unauthorized session expiration
        if (response.status === 401) {
            localStorage.clear();
            if (!window.location.pathname.endsWith("index.html") && window.location.pathname !== "/") {
                showToast("Session expired. Please log in again.", "danger");
                setTimeout(() => {
                    window.location.href = "index.html";
                }, 1500);
            }
            throw new Error("Unauthorized");
        }

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Something went wrong");
        }

        return data;
    } catch (error) {
        console.error("API Request Error:", error);
        throw error;
    }
}

// Toast alerts utility
function showToast(message, type = "success") {
    let container = document.querySelector(".alert-container");
    if (!container) {
        container = document.createElement("div");
        container.className = "alert-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `alert-toast ${type}`;
    
    toast.innerHTML = `
        <span class="message">${message}</span>
        <button class="close-btn">&times;</button>
    `;

    toast.querySelector(".close-btn").addEventListener("click", () => {
        toast.remove();
    });

    container.appendChild(toast);

    // Auto-remove toast after 4 seconds
    setTimeout(() => {
        toast.remove();
    }, 4000);
}

// API methods exporter
const API = {
    get: (endpoint) => request(endpoint, { method: "GET" }),
    post: (endpoint, body) => request(endpoint, {
        method: "POST",
        body: JSON.stringify(body)
    }),
    put: (endpoint, body) => request(endpoint, {
        method: "PUT",
        body: JSON.stringify(body)
    }),
    delete: (endpoint) => request(endpoint, { method: "DELETE" }),
    upload: (endpoint, formData) => request(endpoint, {
        method: "POST",
        body: formData
    }),
    // Fetch a protected file (e.g. a medical document) as a Blob
    getFile: async (endpoint) => {
        const response = await fetch(`${BASE_URL}${endpoint}`, {
            method: "GET",
            headers: getHeaders(true)
        });
        if (!response.ok) {
            throw new Error("Failed to load document");
        }
        return await response.blob();
    }
};

// Open a document inline (in a new tab) via a short-lived blob URL,
// so files are only ever viewable through this app - never via a
// public/shareable storage link.
async function viewDocument(viewEndpoint, fileName) {
    try {
        const blob = await API.getFile(viewEndpoint);
        const objectUrl = URL.createObjectURL(blob);
        window.open(objectUrl, "_blank");
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    } catch (error) {
        showToast(`Failed to open "${fileName}": ${error.message}`, "danger");
    }
}

// Render a clickable filename that opens the document via viewDocument()
function renderDocumentLink(fileName, viewEndpoint) {
    const safeName = fileName.replace(/'/g, "\\'");
    return `<a href="javascript:void(0)" onclick="viewDocument('${viewEndpoint}', '${safeName}')" style="color:var(--accent-color); font-weight:600;">${fileName}</a>`;
}
