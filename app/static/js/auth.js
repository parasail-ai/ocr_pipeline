// Authentication utilities
async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth/session');
        if (response.ok) {
            const data = await response.json();
            return data;
        }
    } catch (error) {
        console.error('Failed to check auth status:', error);
    }
    return { is_authenticated: false, is_admin: false };
}

async function logout() {
    try {
        const response = await fetch('/api/auth/logout', { method: 'POST' });
        if (response.ok) {
            window.location.href = '/';
        }
    } catch (error) {
        console.error('Logout failed:', error);
    }
}

// Update navbar based on auth status
async function updateNavbar() {
    const authStatus = await checkAuthStatus();
    const navMenu = document.querySelector('.nav-menu');
    
    if (!navMenu) return;
    
    // Remove existing login/logout/profile links
    const existingAuthLinks = navMenu.querySelectorAll('[data-auth-link]');
    existingAuthLinks.forEach(link => link.remove());
    
    // Hide/show admin-only links based on admin status
    const adminLinks = navMenu.querySelectorAll('.admin-only');
    adminLinks.forEach(link => {
        link.style.display = authStatus.is_admin ? '' : 'none';
    });

    const modelsLink = navMenu.querySelector('a[href="/models"]');
    if (modelsLink) {
        modelsLink.style.display = authStatus.is_admin ? '' : 'none';
    }

    const analyticsLink = navMenu.querySelector('a[href="/analytics"]');
    if (analyticsLink) {
        analyticsLink.style.display = authStatus.is_admin ? '' : 'none';
    }

    const usersLink = navMenu.querySelector('a[href="/users"]');
    if (usersLink) {
        usersLink.style.display = authStatus.is_admin ? '' : 'none';
    }
    
    // Add Login or Profile Dropdown
    if (authStatus.is_authenticated) {
        // Create profile dropdown container
        const profileContainer = document.createElement('div');
        profileContainer.className = 'profile-dropdown';
        profileContainer.setAttribute('data-auth-link', 'true');
        
        // Profile button
        const profileButton = document.createElement('button');
        profileButton.className = 'profile-button';
        profileButton.innerHTML = `
            <div class="profile-icon">👤</div>
            <span>${authStatus.email || 'Profile'}</span>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M2 4L6 8L10 4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
        `;
        
        // Dropdown menu
        const dropdownMenu = document.createElement('div');
        dropdownMenu.className = 'profile-dropdown-menu';
        dropdownMenu.innerHTML = `
            <a href="/docs" class="profile-dropdown-item" target="_blank">
                <span>📚</span> API Docs
            </a>
            <div class="profile-dropdown-divider"></div>
            <a href="#" class="profile-dropdown-item" onclick="event.preventDefault(); openChangePasswordModal();">
                <span>🔒</span> Change Password
            </a>
            <a href="#" class="profile-dropdown-item" onclick="event.preventDefault(); openApiKeyModal();">
                <span>🔑</span> API Keys
            </a>
            <div class="profile-dropdown-divider"></div>
            <a href="#" class="profile-dropdown-item" onclick="event.preventDefault(); logout();">
                <span>🚪</span> Logout
            </a>
        `;
        
        // Toggle dropdown on click
        profileButton.addEventListener('click', (e) => {
            e.stopPropagation();
            profileContainer.classList.toggle('active');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!profileContainer.contains(e.target)) {
                profileContainer.classList.remove('active');
            }
        });
        
        profileContainer.appendChild(profileButton);
        profileContainer.appendChild(dropdownMenu);
        navMenu.appendChild(profileContainer);
        
        // Initialize modals
        createChangePasswordModal();
        createApiKeyModal();
    } else {
        // Add Login link for unauthenticated users
        const loginLink = document.createElement('a');
        loginLink.href = '/login';
        loginLink.className = 'nav-link';
        loginLink.setAttribute('data-auth-link', 'true');
        loginLink.textContent = 'Login';
        
        // Add active class if on login page
        if (window.location.pathname === '/login') {
            loginLink.classList.add('active');
        }
        
        navMenu.appendChild(loginLink);
    }
}

// Create Change Password Modal
function createChangePasswordModal() {
    if (document.getElementById('changePasswordModal')) return;
    
    const modal = document.createElement('div');
    modal.id = 'changePasswordModal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeChangePasswordModal()"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h2>🔒 Change Password</h2>
                <button class="modal-close" onclick="closeChangePasswordModal()">×</button>
            </div>
            <form id="changePasswordForm" class="modal-body">
                <div class="form-group">
                    <label for="currentPassword">Current Password</label>
                    <input type="password" id="currentPassword" required autocomplete="current-password">
                </div>
                <div class="form-group">
                    <label for="newPassword">New Password</label>
                    <input type="password" id="newPassword" required autocomplete="new-password" minlength="8">
                    <small>Must be at least 8 characters</small>
                </div>
                <div class="form-group">
                    <label for="confirmPassword">Confirm New Password</label>
                    <input type="password" id="confirmPassword" required autocomplete="new-password">
                </div>
                <div id="passwordChangeStatus" class="status-message"></div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeChangePasswordModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">Change Password</button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Handle form submission
    document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const currentPassword = document.getElementById('currentPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const statusEl = document.getElementById('passwordChangeStatus');
        
        // Validate passwords match
        if (newPassword !== confirmPassword) {
            statusEl.textContent = 'New passwords do not match';
            statusEl.className = 'status-message error';
            return;
        }
        
        // Validate password strength
        if (newPassword.length < 8) {
            statusEl.textContent = 'Password must be at least 8 characters';
            statusEl.className = 'status-message error';
            return;
        }
        
        try {
            const response = await fetch('/api/auth/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                statusEl.textContent = '✓ Password changed successfully!';
                statusEl.className = 'status-message success';
                
                // Clear form and close modal after delay
                setTimeout(() => {
                    document.getElementById('changePasswordForm').reset();
                    closeChangePasswordModal();
                }, 1500);
            } else {
                statusEl.textContent = data.detail || 'Failed to change password';
                statusEl.className = 'status-message error';
            }
        } catch (error) {
            console.error('Password change error:', error);
            statusEl.textContent = 'An error occurred. Please try again.';
            statusEl.className = 'status-message error';
        }
    });
}

// Create API Key Modal
function createApiKeyModal() {
    if (document.getElementById('apiKeyModal')) return;
    
    const modal = document.createElement('div');
    modal.id = 'apiKeyModal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeApiKeyModal()"></div>
        <div class="modal-content" style="max-width: 700px;">
            <div class="modal-header">
                <h2>🔑 API Keys</h2>
                <button class="modal-close" onclick="closeApiKeyModal()">×</button>
            </div>
            <div class="modal-body">
                <div style="margin-bottom: 20px;">
                    <p style="color: #666; margin: 0 0 16px 0;">API keys allow you to authenticate API requests. Keep your keys secure and don't share them.</p>
                    <button type="button" class="btn btn-primary" onclick="showCreateKeyForm()">
                        + Generate New API Key
                    </button>
                </div>
                
                <div id="createKeyForm" style="display: none; margin-bottom: 20px; padding: 16px; background: #f5f5f5; border-radius: 8px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px;">Create New API Key</h3>
                    <div class="form-group">
                        <label for="apiKeyName">Key Name (Optional)</label>
                        <input type="text" id="apiKeyName" placeholder="e.g., Production Key">
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button type="button" class="btn btn-primary" onclick="generateApiKey()">Generate</button>
                        <button type="button" class="btn btn-secondary" onclick="hideCreateKeyForm()">Cancel</button>
                    </div>
                </div>
                
                <div id="newKeyDisplay" style="display: none; margin-bottom: 20px; padding: 16px; background: #e8f5e9; border: 2px solid #4caf50; border-radius: 8px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 16px; color: #2e7d32;">✓ API Key Created!</h3>
                    <p style="margin: 0 0 12px 0; color: #666; font-size: 14px;">Save this key now - you won't be able to see it again.</p>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <input type="text" id="newKeyValue" readonly style="flex: 1; font-family: monospace; background: white; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
                        <button type="button" class="btn btn-primary" onclick="copyApiKey()">Copy</button>
                    </div>
                </div>
                
                <div id="apiKeyStatus" class="status-message"></div>
                
                <div id="apiKeysList">
                    <h3 style="margin: 0 0 12px 0; font-size: 16px;">Your API Keys</h3>
                    <div id="keysContainer">
                        <p style="color: #999; text-align: center; padding: 20px;">Loading...</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

// Modal control functions
function openChangePasswordModal() {
    document.getElementById('changePasswordModal').classList.add('active');
    document.getElementById('passwordChangeStatus').textContent = '';
    document.getElementById('passwordChangeStatus').className = 'status-message';
}

function closeChangePasswordModal() {
    document.getElementById('changePasswordModal').classList.remove('active');
    document.getElementById('changePasswordForm').reset();
}

function openApiKeyModal() {
    document.getElementById('apiKeyModal').classList.add('active');
    loadApiKeys();
}

function closeApiKeyModal() {
    document.getElementById('apiKeyModal').classList.remove('active');
    hideCreateKeyForm();
    document.getElementById('newKeyDisplay').style.display = 'none';
}

function showCreateKeyForm() {
    document.getElementById('createKeyForm').style.display = 'block';
    document.getElementById('newKeyDisplay').style.display = 'none';
}

function hideCreateKeyForm() {
    document.getElementById('createKeyForm').style.display = 'none';
    document.getElementById('apiKeyName').value = '';
}

// API Key Management Functions
async function loadApiKeys() {
    const container = document.getElementById('keysContainer');
    const statusEl = document.getElementById('apiKeyStatus');
    
    try {
        const response = await fetch('/api/api-keys');
        
        if (!response.ok) {
            throw new Error('Failed to load API keys');
        }
        
        const data = await response.json();
        const keys = data.items || [];
        
        if (keys.length === 0) {
            container.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">No API keys yet. Generate one to get started!</p>';
            return;
        }
        
        container.innerHTML = keys.map(key => `
            <div class="api-key-item" data-key-id="${key.id}">
                <div style="flex: 1;">
                    <div style="font-weight: 500; margin-bottom: 4px;">
                        ${key.name || 'Unnamed Key'}
                        ${!key.is_active ? '<span style="color: #f44336; font-size: 12px; margin-left: 8px;">REVOKED</span>' : ''}
                    </div>
                    <div style="font-family: monospace; color: #666; font-size: 13px;">
                        ${key.key_prefix}••••••••••••
                    </div>
                    <div style="font-size: 12px; color: #999; margin-top: 4px;">
                        Created: ${new Date(key.created_at).toLocaleDateString()}
                        ${key.last_used_at ? ` • Last used: ${new Date(key.last_used_at).toLocaleDateString()}` : ' • Never used'}
                    </div>
                </div>
                <div style="display: flex; gap: 8px;">
                    ${key.is_active ? `
                        <button type="button" class="btn btn-sm btn-secondary" onclick="revokeApiKey('${key.id}')">Revoke</button>
                    ` : ''}
                    <button type="button" class="btn btn-sm btn-danger" onclick="deleteApiKey('${key.id}')">Delete</button>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading API keys:', error);
        container.innerHTML = '<p style="color: #f44336; text-align: center; padding: 20px;">Failed to load API keys</p>';
    }
}

async function generateApiKey() {
    const name = document.getElementById('apiKeyName').value.trim();
    const statusEl = document.getElementById('apiKeyStatus');
    
    try {
        const response = await fetch('/api/api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name || null })
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to generate API key');
        }
        
        const data = await response.json();
        
        // Show the new key
        document.getElementById('newKeyValue').value = data.key;
        document.getElementById('newKeyDisplay').style.display = 'block';
        hideCreateKeyForm();
        
        // Reload keys list
        await loadApiKeys();
        
        statusEl.textContent = '';
        statusEl.className = 'status-message';
        
    } catch (error) {
        console.error('Error generating API key:', error);
        statusEl.textContent = error.message;
        statusEl.className = 'status-message error';
    }
}

async function copyApiKey() {
    const keyValue = document.getElementById('newKeyValue').value;
    
    try {
        await navigator.clipboard.writeText(keyValue);
        
        const btn = event.target;
        const originalText = btn.textContent;
        btn.textContent = '✓ Copied!';
        btn.style.background = '#4caf50';
        
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '';
        }, 2000);
    } catch (error) {
        console.error('Failed to copy:', error);
        alert('Failed to copy to clipboard. Please copy manually.');
    }
}

async function revokeApiKey(keyId) {
    if (!confirm('Are you sure you want to revoke this API key? It will stop working immediately.')) {
        return;
    }
    
    const statusEl = document.getElementById('apiKeyStatus');
    
    try {
        const response = await fetch(`/api/api-keys/${keyId}/revoke`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to revoke API key');
        }
        
        statusEl.textContent = '✓ API key revoked successfully';
        statusEl.className = 'status-message success';
        
        setTimeout(() => {
            statusEl.textContent = '';
            statusEl.className = 'status-message';
        }, 3000);
        
        await loadApiKeys();
        
    } catch (error) {
        console.error('Error revoking API key:', error);
        statusEl.textContent = error.message;
        statusEl.className = 'status-message error';
    }
}

async function deleteApiKey(keyId) {
    if (!confirm('Are you sure you want to permanently delete this API key? This action cannot be undone.')) {
        return;
    }
    
    const statusEl = document.getElementById('apiKeyStatus');
    
    try {
        const response = await fetch(`/api/api-keys/${keyId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete API key');
        }
        
        statusEl.textContent = '✓ API key deleted successfully';
        statusEl.className = 'status-message success';
        
        setTimeout(() => {
            statusEl.textContent = '';
            statusEl.className = 'status-message';
        }, 3000);
        
        await loadApiKeys();
        
    } catch (error) {
        console.error('Error deleting API key:', error);
        statusEl.textContent = error.message;
        statusEl.className = 'status-message error';
    }
}

// Navigation dropdown toggle
function toggleNavDropdown(event) {
    event.stopPropagation();
    const dropdown = event.target.closest('.nav-dropdown');
    const menu = dropdown.querySelector('.nav-dropdown-menu');
    menu.classList.toggle('show');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.nav-dropdown')) {
        document.querySelectorAll('.nav-dropdown-menu').forEach(menu => {
            menu.classList.remove('show');
        });
    }
});

// Run on page load
document.addEventListener('DOMContentLoaded', updateNavbar);
