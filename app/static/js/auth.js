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
    
    // Remove existing login/logout links
    const existingAuthLinks = navMenu.querySelectorAll('[data-auth-link]');
    existingAuthLinks.forEach(link => link.remove());
    
    // Hide/show Models and Analytics links based on admin status
    const modelsLink = navMenu.querySelector('a[href="/models"]');
    if (modelsLink) {
        modelsLink.style.display = authStatus.is_admin ? '' : 'none';
    }
    
    const analyticsLink = navMenu.querySelector('a[href="/analytics"]');
    if (analyticsLink) {
        analyticsLink.style.display = authStatus.is_admin ? '' : 'none';
    }
    
    // Add Login or Logout link
    if (authStatus.is_authenticated && authStatus.is_admin) {
        // Add Logout link
        const logoutLink = document.createElement('a');
        logoutLink.href = '#';
        logoutLink.className = 'nav-link';
        logoutLink.setAttribute('data-auth-link', 'true');
        logoutLink.textContent = 'Logout';
        logoutLink.onclick = (e) => {
            e.preventDefault();
            logout();
        };
        navMenu.appendChild(logoutLink);
    } else {
        // Add Login link
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

// Run on page load
document.addEventListener('DOMContentLoaded', updateNavbar);
