// ==========================================
// Shared WhatsApp-style chat conversation logic
// Used by patient.html, doctor.html, admin.html
// ==========================================

let chatState = {
    assignmentId: null,
    listEndpoint: null,
    sendEndpoint: null,
    mediaEndpointPrefix: null,
    currentUserId: null,
    canSend: true,
    pollInterval: null,
    lastMessageCount: 0
};

let mediaRecorder = null;
let recordedChunks = [];
let recordingStartTime = null;
let recordingTimerInterval = null;

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    const div = document.createElement("div");
    div.innerText = text;
    return div.innerHTML;
}

// Open a chat thread and start polling for message updates
function openChatThread(config) {
    closeChatThread();
    chatState = {
        assignmentId: config.assignmentId,
        listEndpoint: config.listEndpoint,
        sendEndpoint: config.sendEndpoint,
        mediaEndpointPrefix: config.mediaEndpointPrefix,
        currentUserId: config.currentUserId,
        canSend: config.canSend !== false,
        pollInterval: null,
        lastMessageCount: 0
    };

    const inputBar = document.getElementById("chat-input-bar");
    if (inputBar) {
        inputBar.style.display = chatState.canSend ? "flex" : "none";
    }

    loadChatMessages();

    // Poll for message updates every 2 seconds (faster than before, still efficient)
    chatState.pollInterval = setInterval(() => {
        if (chatState.assignmentId) {
            loadChatMessages();
        }
    }, 2000);
}

// Stop polling and reset state
function closeChatThread() {
    // Stop the polling interval
    if (chatState.pollInterval) {
        clearInterval(chatState.pollInterval);
    }

    chatState = {
        assignmentId: null,
        listEndpoint: null,
        sendEndpoint: null,
        mediaEndpointPrefix: null,
        currentUserId: null,
        canSend: true,
        pollInterval: null,
        lastMessageCount: 0
    };

    const container = document.getElementById("chat-messages-container");
    if (container) container.innerHTML = "";
}

async function loadChatMessages() {
    // Guard: don't load if chat is not active
    if (!chatState.listEndpoint || !chatState.assignmentId) return;

    try {
        const messages = await API.get(chatState.listEndpoint);
        // Only re-render if message count changed
        if (messages.length !== chatState.lastMessageCount) {
            chatState.lastMessageCount = messages.length;
            renderChatMessages(messages);
        }
    } catch (error) {
        console.error("Failed to load chat messages:", error.message);
    }
}

function renderChatMessages(messages) {
    const container = document.getElementById("chat-messages-container");
    if (!container) return;
    container.innerHTML = "";

    if (!messages || messages.length === 0) {
        container.innerHTML = `<div class="empty-state">No messages yet. Say hello!</div>`;
        return;
    }

    messages.forEach(msg => {
        const bubble = document.createElement("div");
        const isOwn = msg.sender_id === chatState.currentUserId;
        const isAdmin = msg.sender_role === "admin";

        let classes = "chat-bubble " + (isOwn ? "sent" : "received");
        if (isAdmin) classes += " chat-bubble-admin";
        bubble.className = classes;

        const time = new Date(msg.created_at).toLocaleString();
        let bodyHtml = "";

        if (isAdmin) {
            bodyHtml += `<span class="chat-bubble-label">Admin${isOwn ? "" : " - " + escapeHtml(msg.sender_name)}</span>`;
        } else if (!isOwn) {
            bodyHtml += `<span class="chat-bubble-label">${escapeHtml(msg.sender_name)}</span>`;
        }

        if (msg.message_type === "text") {
            bodyHtml += `<div class="chat-bubble-text">${escapeHtml(msg.content)}</div>`;
        } else {
            const mediaId = `chat-media-${msg.id}`;
            bodyHtml += `<div id="${mediaId}" class="chat-file-attachment">${getMediaIcon(msg.message_type)} ${escapeHtml(msg.file_name)}</div>`;
        }

        bodyHtml += `<div class="chat-bubble-meta">${time}</div>`;
        bubble.innerHTML = bodyHtml;
        container.appendChild(bubble);

        if (msg.message_type !== "text") {
            renderChatMedia(msg);
        }
    });

    scrollChatToBottom();
}

function getMediaIcon(type) {
    switch (type) {
        case "image": return "🖼️";
        case "video": return "🎬";
        case "audio": return "🎤";
        default: return "📎";
    }
}

async function renderChatMedia(msg) {
    const mediaId = `chat-media-${msg.id}`;
    const el = document.getElementById(mediaId);
    if (!el) return;

    try {
        const blob = await API.getFile(`${chatState.mediaEndpointPrefix}${msg.id}/media`);
        const objectUrl = URL.createObjectURL(blob);

        if (msg.message_type === "image") {
            el.innerHTML = `<img src="${objectUrl}" alt="${escapeHtml(msg.file_name)}">`;
        } else if (msg.message_type === "video") {
            el.innerHTML = `<video controls src="${objectUrl}"></video>`;
        } else if (msg.message_type === "audio") {
            el.innerHTML = `<audio controls src="${objectUrl}"></audio>`;
        } else {
            el.innerHTML = `<a href="${objectUrl}" download="${escapeHtml(msg.file_name)}">📎 ${escapeHtml(msg.file_name)}</a>`;
        }
    } catch (error) {
        el.innerHTML = `⚠️ Failed to load attachment: ${escapeHtml(msg.file_name)}`;
    }
}

async function sendChatText(event) {
    event.preventDefault();
    const input = document.getElementById("chat-text-input");
    const text = input.value.trim();
    if (!text || !chatState.sendEndpoint) return;

    const formData = new FormData();
    formData.append("content", text);

    try {
        input.value = "";
        await API.upload(chatState.sendEndpoint, formData);
        // Realtime subscription will auto-load new message, but reload as fallback
        setTimeout(loadChatMessages, 100);
    } catch (error) {
        showToast("Failed to send message: " + error.message, "danger");
    }
}

async function sendChatFile(fileInput) {
    if (!fileInput.files || fileInput.files.length === 0 || !chatState.sendEndpoint) return;

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
        await API.upload(chatState.sendEndpoint, formData);
        // Realtime subscription will auto-load new message, but reload as fallback
        setTimeout(loadChatMessages, 100);
    } catch (error) {
        showToast("Failed to send attachment: " + error.message, "danger");
    } finally {
        fileInput.value = "";
    }
}

function scrollChatToBottom() {
    const container = document.getElementById("chat-messages-container");
    if (container) container.scrollTop = container.scrollHeight;
}

// ==========================================
// Voice note recording
// ==========================================
async function toggleVoiceRecording() {
    const micBtn = document.getElementById("chat-mic-btn");
    if (!micBtn) return;

    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        recordedChunks = [];
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach(track => track.stop());
            clearInterval(recordingTimerInterval);
            micBtn.classList.remove("recording");
            micBtn.innerHTML = "🎤";

            const blob = new Blob(recordedChunks, { type: "audio/webm" });
            const file = new File([blob], `voice_note_${Date.now()}.webm`, { type: "audio/webm" });

            const formData = new FormData();
            formData.append("file", file);

            try {
                await API.upload(chatState.sendEndpoint, formData);
                // Realtime subscription will auto-load new message, but reload as fallback
                setTimeout(loadChatMessages, 100);
            } catch (error) {
                showToast("Failed to send voice note: " + error.message, "danger");
            }
        };

        mediaRecorder.start();
        recordingStartTime = Date.now();
        micBtn.classList.add("recording");

        recordingTimerInterval = setInterval(() => {
            const seconds = Math.floor((Date.now() - recordingStartTime) / 1000);
            micBtn.innerHTML = `⏹️ ${seconds}s`;
        }, 1000);
    } catch (error) {
        showToast("Microphone access denied or unavailable: " + error.message, "danger");
    }
}
