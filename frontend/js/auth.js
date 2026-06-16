// Auth helpers

function saveSession(data) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    localStorage.setItem("user", JSON.stringify(data.user));
}

function clearSession() {
    localStorage.clear();
}

function getSessionUser() {
    const user = localStorage.getItem("user");
    return user ? JSON.parse(user) : null;
}

// Redirect if not authenticated, or if trying to access a page of a different role
function checkSession(allowedRoles = []) {
    const user = getSessionUser();
    const token = localStorage.getItem("access_token");

    if (!user || !token) {
        clearSession();
        window.location.href = "index.html";
        return null;
    }

    // Role check
    if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
        showToast("Access denied! Redirecting to your portal.", "warning");
        setTimeout(() => {
            if (user.role === "admin") window.location.href = "admin.html";
            else if (user.role === "doctor") window.location.href = "doctor.html";
            else window.location.href = "patient.html";
        }, 1500);
        return null;
    }

    return user;
}

// Global logout function
function logout() {
    clearSession();
    window.location.href = "index.html";
}

// Handle Login form submission
async function handleLogin(email, password) {
    try {
        const data = await API.post("/api/auth/login", { email, password });
        saveSession(data);
        showToast(`Welcome back, ${data.user.full_name}!`, "success");
        
        // Redirect based on role
        setTimeout(() => {
            if (data.user.role === "admin") {
                window.location.href = "admin.html";
            } else if (data.user.role === "doctor") {
                window.location.href = "doctor.html";
            } else {
                window.location.href = "patient.html";
            }
        }, 1000);
    } catch (error) {
        showToast(error.message || "Invalid credentials", "danger");
        throw error;
    }
}

// Handle Admin Login form submission (admin-login.html)
// Same /api/auth/login endpoint, but rejects non-admin accounts.
async function handleAdminLogin(email, password) {
    try {
        const data = await API.post("/api/auth/login", { email, password });

        if (data.user.role !== "admin") {
            showToast("Access denied. This portal is for administrators only.", "danger");
            throw new Error("Not an admin account");
        }

        saveSession(data);
        showToast(`Welcome back, ${data.user.full_name}!`, "success");

        setTimeout(() => {
            window.location.href = "admin.html";
        }, 1000);
    } catch (error) {
        if (error.message !== "Not an admin account") {
            showToast(error.message || "Invalid credentials", "danger");
        }
        throw error;
    }
}

// Handle Forgot Password form submission
async function handleForgotPassword(email) {
    try {
        const data = await API.post("/api/auth/forgot-password", { email });
        showToast(data.message || "If an account exists for this email, a reset link has been sent.", "success");
        return true;
    } catch (error) {
        showToast(error.message || "Failed to send reset link", "danger");
        throw error;
    }
}

// Handle Reset Password form submission
async function handleResetPassword(accessToken, newPassword) {
    try {
        const data = await API.post("/api/auth/reset-password", {
            access_token: accessToken,
            new_password: newPassword
        });
        showToast(data.message || "Password reset successfully!", "success");
        return true;
    } catch (error) {
        showToast(error.message || "Failed to reset password", "danger");
        throw error;
    }
}

// Handle Registration form submission
async function handleRegister(fullName, email, password, role) {
    try {
        await API.post("/api/auth/register", {
            full_name: fullName,
            email: email,
            password: password,
            role: role
        });
        showToast("Registration successful! You can now log in.", "success");
        return true;
    } catch (error) {
        showToast(error.message || "Registration failed", "danger");
        throw error;
    }
}
