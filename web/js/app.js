/**
 * EduVision CRM - Shared JavaScript Utilities
 */

// API Helper Functions
const API = {
  baseURL: '/api',
  
  async fetch(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    };
    
    try {
      const response = await fetch(url, config);
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || data.error || 'API error');
      }
      
      return data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  },
  
  get(endpoint) {
    return this.fetch(endpoint);
  },
  
  post(endpoint, body) {
    return this.fetch(endpoint, {
      method: 'POST',
      body: JSON.stringify(body)
    });
  },
  
  put(endpoint, body) {
    return this.fetch(endpoint, {
      method: 'PUT',
      body: JSON.stringify(body)
    });
  },
  
  patch(endpoint, body) {
    return this.fetch(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(body)
    });
  },
  
  delete(endpoint) {
    return this.fetch(endpoint, {
      method: 'DELETE'
    });
  }
};

// User Session
const User = {
  data: null,
  
  async load() {
    try {
      const response = await API.get('/login/me');
      this.data = response.user || response;
      return this.data;
    } catch (error) {
      console.error('Failed to load user:', error);
      return null;
    }
  },
  
  async logout() {
    try {
      await API.post('/login/logout', {});
      this.data = null;
      window.location.href = '/';
    } catch (error) {
      console.error('Logout failed:', error);
      window.location.href = '/';
    }
  },
  
  hasRole(role) {
    if (!this.data) return false;
    const userAccess = this.data.user_access || '';
    const extraAccess = this.data.extra_access || '';
    return userAccess.includes(role) || extraAccess.includes(role);
  },
  
  isAdmin() {
    return this.hasRole('def') || this.hasRole('admin');
  },
  
  isTeacher() {
    return this.hasRole('teacher') || this.isAdmin();
  },
  
  isParent() {
    return this.hasRole('parent');
  },
  
  isStudent() {
    return this.hasRole('student');
  }
};

// UI Helpers
const UI = {
  showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('show');
    }
  },
  
  hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('show');
    }
  },
  
  showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    
    const container = document.querySelector('.main-content') || document.body;
    container.insertBefore(alert, container.firstChild);
    
    setTimeout(() => alert.remove(), 5000);
  },
  
  showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    }
  },
  
  showError(elementId, message) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = `<div class="alert alert-danger">${message}</div>`;
    }
  },
  
  formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString('uk-UA', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  },
  
  formatDateTime(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('uk-UA', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  },
  
  formatCurrency(amount) {
    if (amount === null || amount === undefined) return '-';
    return new Intl.NumberFormat('uk-UA', {
      style: 'currency',
      currency: 'UAH'
    }).format(amount);
  }
};

// Table Helper
const Table = {
  create(data, columns, actions = []) {
    const table = document.createElement('table');
    
    // Header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
      const th = document.createElement('th');
      th.textContent = col.label;
      headerRow.appendChild(th);
    });
    if (actions.length > 0) {
      const th = document.createElement('th');
      th.textContent = 'Дії';
      headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Body
    const tbody = document.createElement('tbody');
    data.forEach(row => {
      const tr = document.createElement('tr');
      
      columns.forEach(col => {
        const td = document.createElement('td');
        const value = col.field ? row[col.field] : col.render(row);
        td.innerHTML = value;
        tr.appendChild(td);
      });
      
      if (actions.length > 0) {
        const td = document.createElement('td');
        actions.forEach(action => {
          const btn = document.createElement('button');
          btn.className = `btn btn-sm ${action.class || 'btn-secondary'}`;
          btn.textContent = action.label;
          btn.onclick = () => action.onClick(row);
          td.appendChild(btn);
          td.appendChild(document.createTextNode(' '));
        });
        tr.appendChild(td);
      }
      
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    
    return table;
  }
};

// Form Helper
const Form = {
  getData(formId) {
    const form = document.getElementById(formId);
    if (!form) return null;
    
    const data = {};
    const inputs = form.querySelectorAll('input, select, textarea');
    
    inputs.forEach(input => {
      if (input.name) {
        if (input.type === 'checkbox') {
          data[input.name] = input.checked;
        } else if (input.type === 'number') {
          data[input.name] = input.value ? parseFloat(input.value) : null;
        } else {
          data[input.name] = input.value;
        }
      }
    });
    
    return data;
  },
  
  setData(formId, data) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    Object.keys(data).forEach(key => {
      const input = form.querySelector(`[name="${key}"]`);
      if (input) {
        if (input.type === 'checkbox') {
          input.checked = data[key];
        } else {
          input.value = data[key] || '';
        }
      }
    });
  },
  
  reset(formId) {
    const form = document.getElementById(formId);
    if (form) {
      form.reset();
    }
  },
  
  validate(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    return form.checkValidity();
  }
};

// Navigation Helper
const Nav = {
  setActive(path) {
    // Remove active class from all nav items
    document.querySelectorAll('.sidebar-nav a, .bottom-nav-item').forEach(item => {
      item.classList.remove('active');
    });
    
    // Add active class to current path
    const currentLinks = document.querySelectorAll(`a[href="${path}"]`);
    currentLinks.forEach(link => {
      link.classList.add('active');
    });
  },
  
  init() {
    // Set active based on current path
    this.setActive(window.location.pathname);
  }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', async () => {
  // Load user session
  await User.load();
  
  // Initialize navigation
  Nav.init();
  
  // Setup modal close handlers
  document.querySelectorAll('.modal-close').forEach(closeBtn => {
    closeBtn.addEventListener('click', (e) => {
      const modal = e.target.closest('.modal');
      if (modal) {
        modal.classList.remove('show');
      }
    });
  });
  
  // Close modal on overlay click
  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('show');
      }
    });
  });
  
  // Setup logout button if exists
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (confirm('Ви впевнені, що хочете вийти?')) {
        User.logout();
      }
    });
  }
});

// Export for use in other scripts
window.API = API;
window.User = User;
window.UI = UI;
window.Table = Table;
window.Form = Form;
window.Nav = Nav;
