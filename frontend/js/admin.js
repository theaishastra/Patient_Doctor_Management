// State variables to hold records
let doctors = [];
let patients = [];
let assignments = [];
let currentUser = null;

// Initialize Admin Session and Load Dashboard
window.addEventListener("DOMContentLoaded", () => {
    currentUser = checkSession(["admin"]);
    if (currentUser) {
        document.getElementById("admin-name").innerText = currentUser.full_name;
        document.getElementById("admin-email").innerText = currentUser.email;
        loadDashboardStats();
    }
});

// Navigation handling
function showSection(sectionId) {
    // Close any active chat when switching sections
    if (sectionId !== "chatmonitor") {
        closeChatThread();
    }

    // Hide all sections
    document.querySelectorAll(".view-section").forEach(sec => {
        sec.style.display = "none";
    });

    // Remove active class from menu items
    document.querySelectorAll(".menu-item").forEach(item => {
        item.classList.remove("active");
    });

    // Show selected section
    document.getElementById(`section-${sectionId}`).style.display = "block";
    document.getElementById(`menu-${sectionId}`).classList.add("active");

    // Update Topbar Title
    const titleMap = {
        dashboard: "Dashboard Overview",
        doctors: "Manage Doctors",
        patients: "Manage Patients",
        assignments: "Doctor Assignments",
        chatmonitor: "Chat Monitor",
        logs: "System Audit Logs"
    };
    document.getElementById("page-title").innerText = titleMap[sectionId] || "Admin Dashboard";

    // Load data based on section
    if (sectionId === "dashboard") loadDashboardStats();
    else if (sectionId === "doctors") loadDoctors();
    else if (sectionId === "patients") loadPatients();
    else if (sectionId === "assignments") loadAssignments();
    else if (sectionId === "logs") loadAuditLogs();
    else if (sectionId === "chatmonitor") {
        backToChatMonitorList();
        loadChatMonitorList();
    }
}

// Modal management
function openModal(modalId) {
    document.getElementById(modalId).classList.add("active");
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove("active");
}

// ==========================================
// 1. DASHBOARD OVERVIEW LOAD
// ==========================================
async function loadDashboardStats() {
    try {
        const data = await API.get("/api/admin/dashboard-stats");
        
        document.getElementById("stat-doctors-count").innerText = data.stats.doctors;
        document.getElementById("stat-patients-count").innerText = data.stats.patients;
        document.getElementById("stat-treatments-count").innerText = data.stats.treatments;

        renderLogsTable(data.recent_logs, "recent-logs-table-body");
    } catch (error) {
        showToast("Error loading stats: " + error.message, "danger");
    }
}

function renderLogsTable(logs, tbodyId) {
    const tbody = document.getElementById(tbodyId);
    tbody.innerHTML = "";

    if (!logs || logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No activities recorded yet.</td></tr>`;
        return;
    }

    logs.forEach(log => {
        const row = document.createElement("tr");
        const date = new Date(log.created_at).toLocaleString();
        
        let roleBadge = `<span class="badge badge-patient">${log.role || 'system'}</span>`;
        if (log.role === 'admin') roleBadge = `<span class="badge badge-admin">admin</span>`;
        if (log.role === 'doctor') roleBadge = `<span class="badge badge-doctor">doctor</span>`;

        row.innerHTML = `
            <td>${date}</td>
            <td><strong>${log.user_name || 'System'}</strong></td>
            <td>${roleBadge}</td>
            <td><code>${log.action}</code></td>
            <td>${log.details || ''}</td>
        `;
        tbody.appendChild(row);
    });
}

// ==========================================
// 2. DOCTORS LOAD & EDIT
// ==========================================
async function loadDoctors() {
    try {
        doctors = await API.get("/api/admin/doctors");
        const tbody = document.getElementById("doctors-table-body");
        tbody.innerHTML = "";

        if (doctors.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No doctors registered yet.</td></tr>`;
            return;
        }

        doctors.forEach(doc => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td><strong>${doc.full_name}</strong></td>
                <td>${doc.email}</td>
                <td>${doc.specialization || '<span class="text-muted">Not specified</span>'}</td>
                <td><code>${doc.license_number || 'N/A'}</code></td>
                <td>${doc.contact_number || 'N/A'}</td>
                <td class="actions-cell">
                    <button class="action-btn" onclick="editDoctor('${doc.id}')" title="Edit Doctor Profile">✏️ Edit</button>
                    <button class="action-btn" onclick="openResetPasswordModal('${doc.id}', '${doc.full_name}')" title="Reset Password">🔑 Reset Password</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showToast("Error loading doctors: " + error.message, "danger");
    }
}

function editDoctor(docId) {
    const doc = doctors.find(d => d.id === docId);
    if (!doc) return;

    document.getElementById("edit-doc-id").value = doc.id;
    document.getElementById("edit-doc-name").value = doc.full_name;
    document.getElementById("edit-doc-spec").value = doc.specialization || "";
    document.getElementById("edit-doc-license").value = doc.license_number || "";
    document.getElementById("edit-doc-phone").value = doc.contact_number || "";
    document.getElementById("edit-doc-bio").value = doc.bio || "";

    openModal("doctor-modal");
}

async function saveDoctor(event) {
    event.preventDefault();
    const docId = document.getElementById("edit-doc-id").value;
    const body = {
        full_name: document.getElementById("edit-doc-name").value,
        specialization: document.getElementById("edit-doc-spec").value,
        license_number: document.getElementById("edit-doc-license").value,
        contact_number: document.getElementById("edit-doc-phone").value,
        bio: document.getElementById("edit-doc-bio").value
    };

    try {
        await API.put(`/api/admin/doctors/${docId}`, body);
        closeModal("doctor-modal");
        showToast("Doctor details updated successfully!", "success");
        loadDoctors();
    } catch (error) {
        showToast("Failed to update doctor: " + error.message, "danger");
    }
}

// ==========================================
// 3. PATIENTS LOAD & EDIT
// ==========================================
async function loadPatients() {
    try {
        patients = await API.get("/api/admin/patients");
        const tbody = document.getElementById("patients-table-body");
        tbody.innerHTML = "";

        if (patients.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="empty-state">No patients registered yet.</td></tr>`;
            return;
        }

        patients.forEach(pat => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td><strong>${pat.full_name}</strong></td>
                <td>${pat.email}</td>
                <td>${pat.date_of_birth || 'N/A'}</td>
                <td>${pat.gender || 'N/A'}</td>
                <td><span class="badge badge-patient">${pat.blood_group || 'N/A'}</span></td>
                <td>${pat.contact_number || 'N/A'}</td>
                <td>${pat.emergency_contact || 'N/A'}</td>
                <td class="actions-cell">
                    <button class="action-btn" onclick="editPatient('${pat.id}')" title="Edit Patient Details">✏️ Edit</button>
                    <button class="action-btn" onclick="openResetPasswordModal('${pat.id}', '${pat.full_name}')" title="Reset Password">🔑 Reset Password</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showToast("Error loading patients: " + error.message, "danger");
    }
}

function editPatient(patId) {
    const pat = patients.find(p => p.id === patId);
    if (!pat) return;

    document.getElementById("edit-pat-id").value = pat.id;
    document.getElementById("edit-pat-name").value = pat.full_name;
    document.getElementById("edit-pat-dob").value = pat.date_of_birth || "";
    document.getElementById("edit-pat-gender").value = pat.gender || "";
    document.getElementById("edit-pat-blood").value = pat.blood_group || "";
    document.getElementById("edit-pat-phone").value = pat.contact_number || "";
    document.getElementById("edit-pat-emergency").value = pat.emergency_contact || "";

    openModal("patient-modal");
}

async function savePatient(event) {
    event.preventDefault();
    const patId = document.getElementById("edit-pat-id").value;
    const body = {
        full_name: document.getElementById("edit-pat-name").value,
        date_of_birth: document.getElementById("edit-pat-dob").value,
        gender: document.getElementById("edit-pat-gender").value,
        blood_group: document.getElementById("edit-pat-blood").value,
        contact_number: document.getElementById("edit-pat-phone").value,
        emergency_contact: document.getElementById("edit-pat-emergency").value
    };

    try {
        await API.put(`/api/admin/patients/${patId}`, body);
        closeModal("patient-modal");
        showToast("Patient details updated successfully!", "success");
        loadPatients();
    } catch (error) {
        showToast("Failed to update patient: " + error.message, "danger");
    }
}

// ==========================================
// 4. ASSIGNMENTS LOAD, CREATE & DELETE
// ==========================================
async function loadAssignments() {
    try {
        assignments = await API.get("/api/admin/assignments");
        const tbody = document.getElementById("assignments-table-body");
        tbody.innerHTML = "";

        if (assignments.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="empty-state">No patient assignments found.</td></tr>`;
            return;
        }

        assignments.forEach(asg => {
            const row = document.createElement("tr");
            const date = new Date(asg.assigned_at).toLocaleDateString();
            row.innerHTML = `
                <td><strong>Dr. ${asg.doctor_name}</strong></td>
                <td>${asg.patient_name}</td>
                <td>${date}</td>
                <td class="actions-cell">
                    <button class="action-btn btn-delete" onclick="deleteAssignment('${asg.id}')" title="Remove Assignment">🗑️ Delete</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showToast("Error loading assignments: " + error.message, "danger");
    }
}

async function openAssignmentModal() {
    try {
        // Load doctors and patients if not already loaded
        doctors = await API.get("/api/admin/doctors");
        patients = await API.get("/api/admin/patients");

        const docSelect = document.getElementById("assign-doctor-select");
        const patSelect = document.getElementById("assign-patient-select");

        docSelect.innerHTML = '<option value="">-- Choose Doctor --</option>';
        patSelect.innerHTML = '<option value="">-- Choose Patient --</option>';

        doctors.forEach(doc => {
            const spec = doc.specialization ? ` (${doc.specialization})` : '';
            docSelect.innerHTML += `<option value="${doc.id}">Dr. ${doc.full_name}${spec}</option>`;
        });

        patients.forEach(pat => {
            patSelect.innerHTML += `<option value="${pat.id}">${pat.full_name}</option>`;
        });

        openModal("assignment-modal");
    } catch (error) {
        showToast("Failed to load options: " + error.message, "danger");
    }
}

async function saveAssignment(event) {
    event.preventDefault();
    const body = {
        doctor_id: document.getElementById("assign-doctor-select").value,
        patient_id: document.getElementById("assign-patient-select").value
    };

    if (!body.doctor_id || !body.patient_id) {
        showToast("Please select both a doctor and a patient.", "warning");
        return;
    }

    try {
        await API.post("/api/admin/assignments", body);
        closeModal("assignment-modal");
        showToast("Patient assigned to doctor successfully!", "success");
        loadAssignments();
    } catch (error) {
        showToast(error.message, "danger");
    }
}

async function deleteAssignment(asgId) {
    if (!confirm("Are you sure you want to remove this patient assignment? The doctor will lose access to this patient's medical records.")) {
        return;
    }

    try {
        await API.delete(`/api/admin/assignments/${asgId}`);
        showToast("Assignment removed successfully.", "success");
        loadAssignments();
    } catch (error) {
        showToast("Failed to delete assignment: " + error.message, "danger");
    }
}

// ==========================================
// 5. AUDIT LOGS LOAD
// ==========================================
async function loadAuditLogs() {
    try {
        const logs = await API.get("/api/admin/activity-logs");
        renderLogsTable(logs, "all-logs-table-body");
    } catch (error) {
        showToast("Error loading activity logs: " + error.message, "danger");
    }
}

// ==========================================
// 6. CHAT MONITOR
// ==========================================
async function loadChatMonitorList() {
    try {
        assignments = await API.get("/api/admin/assignments");
        const tbody = document.getElementById("chatmonitor-table-body");
        tbody.innerHTML = "";

        if (assignments.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="empty-state">No patient assignments found.</td></tr>`;
            return;
        }

        assignments.forEach(asg => {
            const row = document.createElement("tr");
            const date = new Date(asg.assigned_at).toLocaleDateString();
            row.innerHTML = `
                <td><strong>Dr. ${asg.doctor_name}</strong></td>
                <td>${asg.patient_name}</td>
                <td>${date}</td>
                <td class="actions-cell">
                    <button class="action-btn" onclick="openAdminChat('${asg.id}', '${asg.doctor_name}', '${asg.patient_name}')" title="Open Chat">💬 Open Chat</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        showToast("Error loading chats: " + error.message, "danger");
    }
}

function openAdminChat(assignmentId, doctorName, patientName) {
    document.getElementById("chatmonitor-list-view").style.display = "none";
    document.getElementById("chatmonitor-conversation-view").style.display = "block";
    document.getElementById("chatmonitor-partner-name").innerText = `Dr. ${doctorName} ↔ ${patientName}`;

    openChatThread({
        assignmentId: assignmentId,
        listEndpoint: `/api/admin/chats/${assignmentId}/messages`,
        sendEndpoint: `/api/admin/chats/${assignmentId}/messages`,
        mediaEndpointPrefix: `/api/admin/chats/messages/`,
        currentUserId: currentUser.id,
        canSend: true
    });
}

function backToChatMonitorList() {
    document.getElementById("chatmonitor-list-view").style.display = "block";
    document.getElementById("chatmonitor-conversation-view").style.display = "none";
    closeChatThread();
}

async function downloadChatZip() {
    if (!chatState || !chatState.assignmentId) return;
    try {
        const blob = await API.getFile(`/api/admin/chats/${chatState.assignmentId}/export`);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `chat_${chatState.assignmentId}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        showToast("Failed to download chat export: " + error.message, "danger");
    }
}

// ==========================================
// 7. RESET PASSWORD
// ==========================================
function openResetPasswordModal(userId, userName) {
    document.getElementById("reset-pw-user-id").value = userId;
    document.getElementById("reset-pw-username").innerText = userName;
    document.getElementById("reset-password-form").reset();
    document.getElementById("reset-pw-user-id").value = userId;
    openModal("reset-password-modal");
}

async function saveResetPassword(event) {
    event.preventDefault();
    const userId = document.getElementById("reset-pw-user-id").value;
    const newPassword = document.getElementById("reset-pw-new").value;

    try {
        await API.post(`/api/admin/users/${userId}/reset-password`, { new_password: newPassword });
        closeModal("reset-password-modal");
        showToast("Password reset successfully!", "success");
    } catch (error) {
        showToast("Failed to reset password: " + error.message, "danger");
    }
}

// ==========================================
// 8. CREATE DOCTOR / PATIENT ACCOUNTS
// ==========================================
function openCreateUserModal(role) {
    document.getElementById("create-user-form").reset();
    document.getElementById("create-user-role").value = role;
    document.getElementById("create-user-modal-title").innerText = role === "doctor" ? "Add Doctor" : "Add Patient";
    document.getElementById("create-user-btn-text").innerText = "Create Account";
    openModal("create-user-modal");
}

async function saveCreateUser(event) {
    event.preventDefault();
    const role = document.getElementById("create-user-role").value;
    const body = {
        full_name: document.getElementById("create-user-name").value,
        email: document.getElementById("create-user-email").value,
        password: document.getElementById("create-user-password").value,
        role: role
    };
    const btnText = document.getElementById("create-user-btn-text");

    btnText.disabled = true;
    btnText.innerHTML = '<div class="spinner"></div> Creating...';

    try {
        await API.post("/api/admin/users", body);
        closeModal("create-user-modal");
        showToast(`${role === "doctor" ? "Doctor" : "Patient"} account created successfully!`, "success");
        if (role === "doctor") loadDoctors();
        else loadPatients();
    } catch (error) {
        showToast("Failed to create account: " + error.message, "danger");
    } finally {
        btnText.disabled = false;
        btnText.innerText = "Create Account";
    }
}
