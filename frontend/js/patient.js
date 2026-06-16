let currentPatient = null;
let patientData = null;

// Initialize Patient Session and Load Dashboard
window.addEventListener("DOMContentLoaded", () => {
    currentPatient = checkSession(["patient"]);
    if (currentPatient) {
        document.getElementById("patient-name").innerText = currentPatient.full_name;
        document.getElementById("patient-email").innerText = currentPatient.email;
        loadDashboard();
    }
});

// Navigation handling
function showSection(sectionId) {
    // Close any active chat when switching sections
    if (sectionId !== "chat") {
        closeChatThread();
    }

    document.querySelectorAll(".view-section").forEach(sec => {
        sec.style.display = "none";
    });

    document.querySelectorAll(".menu-item").forEach(item => {
        item.classList.remove("active");
    });

    document.getElementById(`section-${sectionId}`).style.display = "block";
    document.getElementById(`menu-${sectionId}`).classList.add("active");

    const titleMap = {
        healthcard: "My Health Card",
        documents: "My Documents",
        profile: "Update Vitals",
        chat: "Chat with Doctor",
        credentials: "Credentials"
    };
    document.getElementById("page-title").innerText = titleMap[sectionId] || "Patient Dashboard";

    if (sectionId === "healthcard") loadDashboard();
    else if (sectionId === "documents") loadDocuments();
    else if (sectionId === "profile") populateProfileForm();
    else if (sectionId === "chat") {
        backToPatientChatList();
        loadPatientChats();
    }
}

// ==========================================
// 1. HEALTH CARD & TIMELINE
// ==========================================
async function loadDashboard() {
    try {
        patientData = await API.get("/api/patient/dashboard");

        // 1. Update Vitals Header Card
        const info = patientData.patient_info;
        document.getElementById("vital-name").innerText = info.full_name;
        document.getElementById("vital-email").innerText = info.email;
        document.getElementById("vital-dob").innerText = info.date_of_birth || 'N/A';
        document.getElementById("vital-gender").innerText = info.gender || 'N/A';
        document.getElementById("vital-blood").innerText = info.blood_group || 'N/A';
        document.getElementById("vital-phone").innerText = info.contact_number || 'N/A';
        document.getElementById("vital-emergency").innerText = info.emergency_contact || 'N/A';

        // 2. Render Assigned Doctors
        renderAssignedDoctors(patientData.assigned_doctors);

        // 3. Render Treatments Timeline
        renderTreatmentsTimeline(patientData.treatments);
    } catch (error) {
        showToast("Error loading health card: " + error.message, "danger");
    }
}

function renderAssignedDoctors(doctors) {
    const container = document.getElementById("assigned-doctors-list");
    container.innerHTML = "";

    if (!doctors || doctors.length === 0) {
        container.innerHTML = `<div class="empty-state" style="padding:1.5rem 0;">No doctors assigned to your chart yet.</div>`;
        return;
    }

    doctors.forEach(doc => {
        const card = document.createElement("div");
        card.className = "doctor-card";
        card.innerHTML = `
            <h4 style="color: var(--accent-hover);">Dr. ${doc.full_name}</h4>
            <p style="font-size:0.875rem; font-weight:600; color: var(--text-secondary); margin-bottom: 0.25rem;">
                Specialization: ${doc.specialization || 'General Practitioner'}
            </p>
            ${doc.contact_number ? `<p style="font-size:0.8rem; color:var(--text-muted);">📞 ${doc.contact_number}</p>` : ''}
            ${doc.bio ? `<p style="font-size:0.825rem; font-style:italic; margin-top:0.5rem; color:var(--text-secondary); border-top:1px solid var(--border-color); padding-top:0.5rem;">${doc.bio}</p>` : ''}
        `;
        container.appendChild(card);
    });
}

function renderTreatmentsTimeline(treatments) {
    const container = document.getElementById("treatments-timeline");
    container.innerHTML = "";

    if (!treatments || treatments.length === 0) {
        container.innerHTML = `<div class="empty-state">No recorded treatments or medicines from your doctors yet.</div>`;
        return;
    }

    treatments.forEach(treat => {
        const card = document.createElement("div");
        card.className = "treatment-detail-card";
        const date = new Date(treat.created_at).toLocaleString();
        
        card.innerHTML = `
            <div class="treatment-meta">
                <span>Prescribed by: <strong>Dr. ${treat.doctor_name}</strong></span>
                <span>${date}</span>
            </div>
            <div class="treatment-field">
                <div class="treatment-label">Diagnosis</div>
                <div class="treatment-value" style="font-weight: 600; color: var(--accent-hover);">${treat.diagnosis}</div>
            </div>
            <div class="treatment-field">
                <div class="treatment-label">Treatment Plan / Suggestions</div>
                <div class="treatment-value">${treat.treatment_plan}</div>
            </div>
            <div class="treatment-field">
                <div class="treatment-label">Prescribed Medicines</div>
                <div class="treatment-value" style="background-color: var(--accent-light); font-weight: 500; color: var(--primary-color);">💊 ${treat.suggested_medicines}</div>
            </div>
            ${treat.notes ? `
                <div class="treatment-field">
                    <div class="treatment-label">Doctor Instructions</div>
                    <div class="treatment-value" style="font-style: italic;">${treat.notes}</div>
                </div>
            ` : ''}
        `;
        container.appendChild(card);
    });
}

// ==========================================
// 2. MEDICAL DOCUMENTS MANAGEMENT
// ==========================================
async function loadDocuments() {
    try {
        const docs = await API.get("/api/patient/documents");
        const tbody = document.getElementById("documents-tbody");
        tbody.innerHTML = "";

        if (docs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="empty-state">No medical documents uploaded yet.</td></tr>`;
            return;
        }

        docs.forEach(doc => {
            const row = document.createElement("tr");
            const date = new Date(doc.uploaded_at).toLocaleString();
            row.innerHTML = `
                <td>${renderDocumentLink(doc.file_name, `/api/patient/documents/${doc.id}/view`)}</td>
                <td>${doc.description || '<span class="text-muted">No description</span>'}</td>
                <td>${date}</td>
                <td class="actions-cell">
                    <button class="action-btn btn-delete" onclick="deleteDocument('${doc.id}')" title="Delete Document">🗑️ Delete</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showToast("Error loading documents: " + error.message, "danger");
    }
}

function onFileSelected(input) {
    const filenameSpan = document.getElementById("selected-filename");
    const dropzoneText = document.getElementById("dropzone-text");

    if (input.files && input.files.length > 0) {
        const file = input.files[0];
        filenameSpan.innerText = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        dropzoneText.innerText = "🔄 Change selected file";
    } else {
        filenameSpan.innerText = "";
        dropzoneText.innerText = "📂 Click to browse or select file";
    }
}

async function uploadDocumentFile(event) {
    event.preventDefault();
    const fileInput = document.getElementById("doc-file-input");
    const description = document.getElementById("doc-description").value;
    const btn = document.getElementById("upload-btn");

    if (!fileInput.files || fileInput.files.length === 0) {
        showToast("Please choose a file to upload first.", "warning");
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);
    if (description) {
        formData.append("description", description);
    }

    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Uploading...';

    try {
        await API.upload("/api/patient/documents", formData);
        showToast("Document uploaded successfully!", "success");
        
        // Reset form & dropzone UI
        document.getElementById("upload-doc-form").reset();
        document.getElementById("selected-filename").innerText = "";
        document.getElementById("dropzone-text").innerText = "📂 Click to browse or select file";
        
        loadDocuments();
    } catch (error) {
        showToast("Upload failed: " + error.message, "danger");
    } finally {
        btn.disabled = false;
        btn.innerHTML = "Upload Document";
    }
}

async function deleteDocument(docId) {
    if (!confirm("Are you sure you want to permanently delete this document? Your doctors will no longer be able to view it.")) {
        return;
    }

    try {
        await API.delete(`/api/patient/documents/${docId}`);
        showToast("Document deleted successfully.", "success");
        loadDocuments();
    } catch (error) {
        showToast("Delete failed: " + error.message, "danger");
    }
}

// ==========================================
// 3. PROFILE / VITALS EDIT
// ==========================================
function populateProfileForm() {
    if (!patientData || !patientData.patient_info) return;
    const info = patientData.patient_info;

    document.getElementById("set-pat-name").value = info.full_name;
    document.getElementById("set-pat-email").value = info.email;
    document.getElementById("set-pat-dob").value = info.date_of_birth || "";
    document.getElementById("set-pat-gender").value = info.gender || "";
    document.getElementById("set-pat-blood").value = info.blood_group || "";
    document.getElementById("set-pat-phone").value = info.contact_number || "";
    document.getElementById("set-pat-emergency").value = info.emergency_contact || "";
}

async function saveProfileSettings(event) {
    event.preventDefault();
    const body = {
        date_of_birth: document.getElementById("set-pat-dob").value || null,
        gender: document.getElementById("set-pat-gender").value || null,
        blood_group: document.getElementById("set-pat-blood").value || null,
        contact_number: document.getElementById("set-pat-phone").value || null,
        emergency_contact: document.getElementById("set-pat-emergency").value || null
    };

    try {
        await API.put("/api/patient/profile", body);
        showToast("Vitals updated successfully!", "success");
        // Reload dashboard data
        const freshDashboard = await API.get("/api/patient/dashboard");
        patientData = freshDashboard;
        populateProfileForm();
    } catch (error) {
        showToast("Failed to update vitals: " + error.message, "danger");
    }
}

// ==========================================
// 4. CHAT WITH DOCTOR
// ==========================================
async function loadPatientChats() {
    try {
        const chats = await API.get("/api/patient/chats");
        const container = document.getElementById("chat-doctor-list");
        container.innerHTML = "";

        if (!chats || chats.length === 0) {
            container.innerHTML = `<div class="empty-state">Chat will be available once an admin assigns you a doctor.</div>`;
            return;
        }

        chats.forEach(chat => {
            const card = document.createElement("div");
            card.className = "chat-thread-card";
            const lastMsg = chat.last_message_preview
                ? chat.last_message_preview
                : "No messages yet";
            card.innerHTML = `
                <h4 style="color: var(--accent-hover);">Dr. ${chat.doctor_name}</h4>
                <p style="font-size:0.8rem; color:var(--text-secondary);">${chat.specialization || 'General Practitioner'}</p>
                <p class="text-muted" style="font-size:0.825rem; margin-top:0.25rem;">${lastMsg}</p>
            `;
            card.onclick = () => openPatientChat(chat.assignment_id, chat.doctor_name);
            container.appendChild(card);
        });
    } catch (error) {
        showToast("Error loading chats: " + error.message, "danger");
    }
}

function openPatientChat(assignmentId, doctorName) {
    document.getElementById("chat-doctor-list-view").style.display = "none";
    document.getElementById("chat-conversation-view").style.display = "block";
    document.getElementById("chat-partner-name").innerText = "Dr. " + doctorName;

    openChatThread({
        assignmentId: assignmentId,
        listEndpoint: `/api/patient/chats/${assignmentId}/messages`,
        sendEndpoint: `/api/patient/chats/${assignmentId}/messages`,
        mediaEndpointPrefix: `/api/patient/chats/messages/`,
        currentUserId: currentPatient.id,
        canSend: true
    });
}

function backToPatientChatList() {
    document.getElementById("chat-doctor-list-view").style.display = "block";
    document.getElementById("chat-conversation-view").style.display = "none";
    closeChatThread();
}

// ==========================================
// 5. CREDENTIALS
// ==========================================
async function changeOwnPassword(event) {
    event.preventDefault();
    const currentPassword = document.getElementById("cred-current-password").value;
    const newPassword = document.getElementById("cred-new-password").value;
    const confirmPassword = document.getElementById("cred-confirm-password").value;

    if (newPassword !== confirmPassword) {
        showToast("New password and confirmation do not match.", "warning");
        return;
    }

    try {
        await API.post("/api/patient/change-password", {
            current_password: currentPassword,
            new_password: newPassword
        });
        showToast("Password updated successfully!", "success");
        document.getElementById("change-password-form").reset();
    } catch (error) {
        showToast("Failed to update password: " + error.message, "danger");
    }
}
