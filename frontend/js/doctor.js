// State variables
let assignedPatients = [];
let selectedPatient = null;
let currentDoctor = null;

// Initialize Doctor Session and Load My Patients
window.addEventListener("DOMContentLoaded", () => {
    currentDoctor = checkSession(["doctor"]);
    if (currentDoctor) {
        document.getElementById("doctor-name").innerText = currentDoctor.full_name;
        document.getElementById("doctor-email").innerText = currentDoctor.email;
        loadAssignedPatients();
    }
});

// View switching
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
        patients: "Assigned Patients",
        settings: "Profile Settings",
        chat: "Patient Chats"
    };
    document.getElementById("page-title").innerText = titleMap[sectionId] || "Doctor Dashboard";

    if (sectionId === "patients") {
        backToPatientList(); // Reset back to table list if they navigation click
    } else if (sectionId === "settings") {
        loadProfileSettings();
    } else if (sectionId === "chat") {
        backToChatList();
        loadDoctorChats();
    }
}

function backToPatientList() {
    document.getElementById("patient-list-view").style.display = "block";
    document.getElementById("patient-detail-view").style.display = "none";
    selectedPatient = null;
}

// Modal management
function openModal(modalId) {
    document.getElementById(modalId).classList.add("active");
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove("active");
    document.getElementById("treatment-form").reset();
    document.getElementById("treatment-id").value = "";
    document.getElementById("treatment-modal-title").innerText = "Record New Treatment";
}

// ==========================================
// 1. ASSIGNED PATIENTS
// ==========================================
async function loadAssignedPatients() {
    try {
        assignedPatients = await API.get("/api/doctor/patients");
        const tbody = document.getElementById("assigned-patients-tbody");
        tbody.innerHTML = "";

        if (assignedPatients.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No patients assigned to you yet. Contact administrator to make assignments.</td></tr>`;
            return;
        }

        assignedPatients.forEach(pat => {
            const row = document.createElement("tr");
            const date = new Date(pat.assigned_at).toLocaleDateString();
            row.innerHTML = `
                <td><strong>${pat.full_name}</strong></td>
                <td>${pat.gender || 'N/A'}</td>
                <td><span class="badge badge-patient">${pat.blood_group || 'N/A'}</span></td>
                <td>${pat.date_of_birth || 'N/A'}</td>
                <td>${date}</td>
                <td>
                    <button class="btn btn-secondary" onclick="viewPatientDetails('${pat.id}')">View Chart 📁</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showToast("Error loading patients: " + error.message, "danger");
    }
}

// ==========================================
// 2. PATIENT HISTORY & DOCUMENT VIEWING
// ==========================================
async function viewPatientDetails(patientId) {
    try {
        const history = await API.get(`/api/doctor/patients/${patientId}/history`);
        selectedPatient = history.patient;

        // Populate header details
        document.getElementById("det-patient-name").innerText = selectedPatient.full_name;
        document.getElementById("det-patient-email").innerText = selectedPatient.email;
        document.getElementById("det-patient-dob").innerText = selectedPatient.date_of_birth || 'N/A';
        document.getElementById("det-patient-gender").innerText = selectedPatient.gender || 'N/A';
        document.getElementById("det-patient-blood").innerText = selectedPatient.blood_group || 'N/A';
        document.getElementById("det-patient-phone").innerText = selectedPatient.contact_number || 'N/A';
        document.getElementById("det-patient-emergency").innerText = selectedPatient.emergency_contact || 'N/A';

        // Render Uploaded Documents
        const docsTbody = document.getElementById("det-patient-docs-tbody");
        docsTbody.innerHTML = "";
        if (history.documents.length === 0) {
            docsTbody.innerHTML = `<tr><td colspan="3" class="empty-state">No medical reports uploaded by patient.</td></tr>`;
        } else {
            history.documents.forEach(doc => {
                const docRow = document.createElement("tr");
                const uploadDate = new Date(doc.uploaded_at).toLocaleDateString();
                docRow.innerHTML = `
                    <td>${renderDocumentLink(doc.file_name, `/api/doctor/documents/${doc.id}/view`)}</td>
                    <td>${doc.description || '<span class="text-muted">None</span>'}</td>
                    <td>${uploadDate}</td>
                `;
                docsTbody.appendChild(docRow);
            });
        }

        // Render Treatments History List
        renderTreatmentsList(history.treatments);

        // Toggle layout visibility
        document.getElementById("patient-list-view").style.display = "none";
        document.getElementById("patient-detail-view").style.display = "block";
    } catch (error) {
        showToast("Failed to fetch patient chart: " + error.message, "danger");
    }
}

function renderTreatmentsList(treatments) {
    const listContainer = document.getElementById("det-patient-treatments-list");
    listContainer.innerHTML = "";

    if (treatments.length === 0) {
        listContainer.innerHTML = `<div class="empty-state">No historical treatments recorded.</div>`;
        return;
    }

    treatments.forEach(treat => {
        const card = document.createElement("div");
        card.className = "history-card";
        const date = new Date(treat.created_at).toLocaleString();

        const isPrescribedByMe = treat.doctor_id === currentDoctor.id;
        const editButtonHtml = isPrescribedByMe 
            ? `<button class="action-btn" onclick="editTreatment('${treat.id}', '${treat.diagnosis}', \`${treat.treatment_plan}\`, \`${treat.suggested_medicines}\`, \`${treat.notes || ''}\`)" style="position: absolute; top:1.25rem; right:1.25rem;">✏️ Edit</button>`
            : '';

        card.innerHTML = `
            <div class="history-card-header">
                <span>Prescribed by: <strong>Dr. ${treat.doctor_name}</strong> ${isPrescribedByMe ? '(You)' : ''}</span>
                <span>${date}</span>
            </div>
            ${editButtonHtml}
            <div class="treatment-field">
                <div class="treatment-label">Diagnosis</div>
                <div class="treatment-value" style="font-weight:600; color: var(--accent-hover);">${treat.diagnosis}</div>
            </div>
            <div class="treatment-field">
                <div class="treatment-label">Treatment Plan / Instructions</div>
                <div class="treatment-value">${treat.treatment_plan}</div>
            </div>
            <div class="treatment-field">
                <div class="treatment-label">Suggested Medicines</div>
                <div class="treatment-value" style="background-color: var(--accent-light); font-weight: 500;">💊 ${treat.suggested_medicines}</div>
            </div>
            ${treat.notes ? `
            <div class="treatment-field">
                <div class="treatment-label">Doctor's Notes (Private)</div>
                <div class="treatment-value" style="font-style: italic;">${treat.notes}</div>
            </div>
            ` : ''}
        `;
        listContainer.appendChild(card);
    });
}

// ==========================================
// 3. ADD/EDIT TREATMENT PLAN
// ==========================================
function openTreatmentModal() {
    document.getElementById("treatment-modal-title").innerText = "Record New Treatment";
    document.getElementById("treatment-id").value = "";
    document.getElementById("treatment-form").reset();
    openModal("treatment-modal");
}

function editTreatment(id, diagnosis, plan, meds, notes) {
    document.getElementById("treatment-modal-title").innerText = "Edit Treatment Record";
    document.getElementById("treatment-id").value = id;
    document.getElementById("treat-diagnosis").value = diagnosis;
    document.getElementById("treat-plan").value = plan;
    document.getElementById("treat-meds").value = meds;
    document.getElementById("treat-notes").value = notes;
    openModal("treatment-modal");
}

async function saveTreatment(event) {
    event.preventDefault();
    const treatId = document.getElementById("treatment-id").value;
    
    const body = {
        diagnosis: document.getElementById("treat-diagnosis").value,
        treatment_plan: document.getElementById("treat-plan").value,
        suggested_medicines: document.getElementById("treat-meds").value,
        notes: document.getElementById("treat-notes").value || null
    };

    try {
        if (treatId) {
            // Edit existing treatment
            await API.put(`/api/doctor/treatments/${treatId}`, body);
            showToast("Treatment updated successfully!", "success");
        } else {
            // Create new treatment
            body.patient_id = selectedPatient.id;
            await API.post("/api/doctor/treatments", body);
            showToast("New treatment recorded successfully!", "success");
        }
        
        closeModal("treatment-modal");
        
        // Refresh details
        if (selectedPatient) {
            viewPatientDetails(selectedPatient.id);
        }
    } catch (error) {
        showToast("Error saving treatment: " + error.message, "danger");
    }
}

// ==========================================
// 4. PROFILE SETTINGS
// ==========================================
async function loadProfileSettings() {
    try {
        const docProfile = await API.get("/api/doctor/profile");
        document.getElementById("set-doc-name").value = docProfile.full_name;
        document.getElementById("set-doc-email").value = docProfile.email;
        document.getElementById("set-doc-spec").value = docProfile.specialization || "";
        document.getElementById("set-doc-license").value = docProfile.license_number || "";
        document.getElementById("set-doc-phone").value = docProfile.contact_number || "";
        document.getElementById("set-doc-bio").value = docProfile.bio || "";
    } catch (error) {
        showToast("Failed to load profile details: " + error.message, "danger");
    }
}

async function saveProfileSettings(event) {
    event.preventDefault();
    const body = {
        specialization: document.getElementById("set-doc-spec").value,
        license_number: document.getElementById("set-doc-license").value,
        contact_number: document.getElementById("set-doc-phone").value,
        bio: document.getElementById("set-doc-bio").value
    };

    try {
        await API.put("/api/doctor/profile", body);
        showToast("Profile settings updated successfully!", "success");
        loadProfileSettings();
    } catch (error) {
        showToast("Failed to update profile settings: " + error.message, "danger");
    }
}

// ==========================================
// 5. PATIENT CHATS
// ==========================================
async function loadDoctorChats() {
    try {
        const chats = await API.get("/api/doctor/chats");
        const container = document.getElementById("chat-patient-list");
        container.innerHTML = "";

        if (!chats || chats.length === 0) {
            container.innerHTML = `<div class="empty-state">No patients assigned to you yet.</div>`;
            return;
        }

        chats.forEach(chat => {
            const card = document.createElement("div");
            card.className = "chat-thread-card";
            const lastMsg = chat.last_message_preview
                ? chat.last_message_preview
                : "No messages yet";
            card.innerHTML = `
                <h4 style="color: var(--accent-hover);">${chat.patient_name}</h4>
                <p class="text-muted" style="font-size:0.825rem; margin-top:0.25rem;">${lastMsg}</p>
            `;
            card.onclick = () => openDoctorChat(chat.assignment_id, chat.patient_name);
            container.appendChild(card);
        });
    } catch (error) {
        showToast("Error loading chats: " + error.message, "danger");
    }
}

function openDoctorChat(assignmentId, patientName) {
    document.getElementById("chat-patient-list-view").style.display = "none";
    document.getElementById("chat-conversation-view").style.display = "block";
    document.getElementById("chat-partner-name").innerText = patientName;

    openChatThread({
        assignmentId: assignmentId,
        listEndpoint: `/api/doctor/chats/${assignmentId}/messages`,
        sendEndpoint: `/api/doctor/chats/${assignmentId}/messages`,
        mediaEndpointPrefix: `/api/doctor/chats/messages/`,
        currentUserId: currentDoctor.id,
        canSend: true
    });
}

function backToChatList() {
    document.getElementById("chat-patient-list-view").style.display = "block";
    document.getElementById("chat-conversation-view").style.display = "none";
    closeChatThread();
}

// ==========================================
// 6. CREDENTIALS
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
        await API.post("/api/doctor/change-password", {
            current_password: currentPassword,
            new_password: newPassword
        });
        showToast("Password updated successfully!", "success");
        document.getElementById("change-password-form").reset();
    } catch (error) {
        showToast("Failed to update password: " + error.message, "danger");
    }
}
