/**
 * Bridge Burner - Main Application
 */

/**
 * Debounce helper - prevents rapid repeated calls
 * Returns a function that ignores calls while a previous async call is in progress
 */
function debounceAsync(fn) {
    let inProgress = false;
    return async function(...args) {
        if (inProgress) return;
        inProgress = true;
        try {
            await fn.apply(this, args);
        } finally {
            inProgress = false;
        }
    };
}

/**
 * Debounce with cooldown - prevents calls within cooldown period
 */
function debounce(fn, cooldownMs = 500) {
    let lastCall = 0;
    return function(...args) {
        const now = Date.now();
        if (now - lastCall < cooldownMs) return;
        lastCall = now;
        return fn.apply(this, args);
    };
}

const App = {
    // Current state
    currentProject: null,
    files: [],
    filteredFiles: [],
    currentFilter: 'all',

    // DOM elements (cached on init)
    elements: {},

    /**
     * Initialize the application
     */
    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadProjects();
        this.registerServiceWorker();
    },

    /**
     * Cache DOM elements for performance
     */
    cacheElements() {
        this.elements = {
            // Views
            viewProjects: document.getElementById('view-projects'),
            viewDetail: document.getElementById('view-detail'),
            viewImport: document.getElementById('view-import'),
            viewSettings: document.getElementById('view-settings'),

            // Navigation
            btnProjects: document.getElementById('btn-projects'),
            btnImport: document.getElementById('btn-import'),
            btnSettings: document.getElementById('btn-settings'),
            btnBack: document.getElementById('btn-back'),

            // Project list
            projectList: document.getElementById('project-list'),
            libraryPath: document.getElementById('library-path'),

            // Project detail
            projectName: document.getElementById('project-name'),
            imageGrid: document.getElementById('image-grid'),
            statTotal: document.getElementById('stat-total'),
            statCulled: document.getElementById('stat-culled'),
            statKept: document.getElementById('stat-kept'),
            btnDeleteCulled: document.getElementById('btn-delete-culled'),
            filterTabs: document.querySelectorAll('.filter-tab'),
            btnToggleNotes: document.getElementById('btn-toggle-notes'),
            projectNotesPanel: document.getElementById('project-notes-panel'),
            projectNotes: document.getElementById('project-notes'),
            btnCloseNotes: document.getElementById('btn-close-notes'),
            btnSaveNotes: document.getElementById('btn-save-notes'),

            // Settings
            libraryLocation: document.getElementById('library-location'),

            // Toast
            toastContainer: document.getElementById('toast-container'),
        };
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Navigation (debounced to prevent double-clicks)
        this.elements.btnProjects.addEventListener('click', debounce(() => this.showView('projects')));
        this.elements.btnImport?.addEventListener('click', debounce(() => this.showView('import')));
        this.elements.btnSettings.addEventListener('click', debounce(() => this.showView('settings')));
        this.elements.btnBack.addEventListener('click', debounce(() => this.showView('projects')));

        // Help modal
        document.getElementById('btn-help')?.addEventListener('click', debounce(() => this.showHelpModal()));
        document.getElementById('help-close')?.addEventListener('click', debounce(() => this.hideHelpModal()));
        document.querySelector('#help-modal .modal-overlay')?.addEventListener('click', () => this.hideHelpModal());

        // Delete culled button (async debounce - waits for operation to complete)
        this.elements.btnDeleteCulled.addEventListener('click', debounceAsync(() => this.deleteCulled()));

        // Filter tabs
        this.elements.filterTabs.forEach(tab => {
            tab.addEventListener('click', debounce((e) => this.setFilter(e.target.dataset.filter)));
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));

        // Settings - library path (async operations need async debounce)
        document.getElementById('btn-browse-library')?.addEventListener('click', debounceAsync(() => this.browseLibraryPath()));
        document.getElementById('btn-save-library')?.addEventListener('click', debounceAsync(() => this.saveLibraryPath()));

        // Project notes
        this.elements.btnToggleNotes?.addEventListener('click', debounce(() => this.toggleNotesPanel()));
        this.elements.btnCloseNotes?.addEventListener('click', debounce(() => this.toggleNotesPanel(false)));
        this.elements.btnSaveNotes?.addEventListener('click', debounceAsync(() => this.saveProjectNotes()));
    },

    /**
     * Show a specific view
     */
    showView(viewName) {
        // Hide all views
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

        // Update nav buttons
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

        // Show selected view
        if (viewName === 'projects') {
            this.elements.viewProjects.classList.add('active');
            this.elements.btnProjects.classList.add('active');
            this.loadProjects();
        } else if (viewName === 'detail') {
            this.elements.viewDetail.classList.add('active');
            this.elements.btnProjects.classList.add('active');
        } else if (viewName === 'import') {
            this.elements.viewImport?.classList.add('active');
            this.elements.btnImport?.classList.add('active');
        } else if (viewName === 'settings') {
            this.elements.viewSettings.classList.add('active');
            this.elements.btnSettings.classList.add('active');
        }
    },

    /**
     * Load and display projects
     */
    async loadProjects() {
        try {
            const data = await API.getProjects();
            this.renderProjects(data.projects);
            this.elements.libraryPath.textContent = data.library_path;
            this.elements.libraryLocation.value = data.library_path;
        } catch (error) {
            this.showToast('Failed to load projects', 'error');
            console.error(error);
        }
    },

    /**
     * Render project list
     */
    renderProjects(projects) {
        if (projects.length === 0) {
            this.elements.projectList.innerHTML = `
                <div class="empty-state">
                    <p>No projects found</p>
                    <p class="help-text">Add project folders to your library directory</p>
                </div>
            `;
            return;
        }

        this.elements.projectList.innerHTML = projects.map(project => `
            <div class="project-card" data-project="${this.escapeHtml(project.name)}">
                <button class="btn-delete-project" title="Delete project">&times;</button>
                <h3 class="project-title">${this.escapeHtml(project.name)}</h3>
                <div class="project-stats">
                    <span>${project.total_files} files</span>
                    <span class="stat-culled">${project.culled_count} culled</span>
                </div>
                ${project.notes ? `<p class="project-notes">${this.escapeHtml(project.notes)}</p>` : ''}
            </div>
        `).join('');

        // Bind click events
        this.elements.projectList.querySelectorAll('.project-card').forEach(card => {
            // Open project on card click
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.btn-delete-project')) {
                    this.openProject(card.dataset.project);
                }
            });

            // Delete button
            card.querySelector('.btn-delete-project').addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteProject(card.dataset.project);
            });
        });
    },

    /**
     * Open a project
     */
    async openProject(name) {
        try {
            const project = await API.getProject(name);
            this.currentProject = project;
            this.files = project.files;
            this.elements.projectName.textContent = project.name;

            // Load project notes
            const notes = project.metadata?.notes || '';
            this.elements.projectNotes.value = notes;
            // Hide notes panel when opening a new project
            this.elements.projectNotesPanel?.classList.add('hidden');

            this.setFilter('all');
            this.updateStats();
            this.showView('detail');
        } catch (error) {
            this.showToast('Failed to load project', 'error');
            console.error(error);
        }
    },

    /**
     * Update stats display
     */
    updateStats() {
        const total = this.files.length;
        const culled = this.files.filter(f => f.culled).length;
        const kept = total - culled;

        this.elements.statTotal.textContent = `${total} files`;
        this.elements.statCulled.textContent = `${culled} culled`;
        this.elements.statKept.textContent = `${kept} kept`;
    },

    /**
     * Set filter and re-render grid
     */
    setFilter(filter) {
        this.currentFilter = filter;

        // Update active tab
        this.elements.filterTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.filter === filter);
        });

        // Filter files
        this.filteredFiles = this.files.filter(file => {
            if (filter === 'all') return true;
            if (filter === 'kept') return !file.culled;
            if (filter === 'culled') return file.culled;
            return file.type === filter;
        });

        this.renderGrid();
    },

    /**
     * Render image grid
     */
    renderGrid() {
        if (this.filteredFiles.length === 0) {
            this.elements.imageGrid.innerHTML = `
                <div class="empty-state">
                    <p>No files match the current filter</p>
                </div>
            `;
            return;
        }

        this.elements.imageGrid.innerHTML = this.filteredFiles.map((file, index) => {
            const thumbnailUrl = file.can_thumbnail
                ? API.getThumbnailUrl(this.currentProject.name, file.filename)
                : '';
            const isVideo = file.type === 'video';
            const hasEdits = file.has_xcf || file.has_tif;

            return `
                <div class="grid-item ${file.culled ? 'culled' : ''}"
                     data-index="${index}"
                     data-filename="${this.escapeHtml(file.filename)}">
                    ${hasEdits ? `
                        <div class="edit-indicators">
                            ${file.has_xcf ? '<span class="edit-badge badge-xcf" title="Has GIMP project">XCF</span>' : ''}
                            ${file.has_tif ? '<span class="edit-badge badge-tif" title="Has TIFF export">TIF</span>' : ''}
                        </div>
                    ` : ''}
                    ${file.can_thumbnail
                        ? `<img src="${thumbnailUrl}" alt="${this.escapeHtml(file.filename)}" loading="lazy">`
                        : `<div class="file-icon">${isVideo ? '🎬' : '📄'}</div>`
                    }
                    <div class="grid-item-info">
                        <span class="filename">${this.escapeHtml(file.filename)}</span>
                        ${file.culled ? '<span class="badge badge-culled">CULLED</span>' : ''}
                    </div>
                    <div class="grid-item-actions">
                        <button class="btn-icon btn-cull" title="Cull (X)">✕</button>
                        <button class="btn-icon btn-keep" title="Keep (K)">✓</button>
                    </div>
                </div>
            `;
        }).join('');

        // Bind click events
        this.elements.imageGrid.querySelectorAll('.grid-item').forEach(item => {
            // Open lightbox on image click
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.grid-item-actions')) {
                    const index = parseInt(item.dataset.index);
                    Lightbox.open(this.filteredFiles, index, this.currentProject.name);
                }
            });

            // Cull button
            item.querySelector('.btn-cull').addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleCull(item.dataset.filename, true);
            });

            // Keep button
            item.querySelector('.btn-keep').addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleCull(item.dataset.filename, false);
            });
        });
    },

    /**
     * Toggle cull status for a file
     */
    async toggleCull(filename, cull) {
        try {
            if (cull) {
                await API.cullFile(this.currentProject.name, filename);
            } else {
                await API.keepFile(this.currentProject.name, filename);
            }

            // Update local state
            const file = this.files.find(f => f.filename === filename);
            if (file) {
                file.culled = cull;
            }

            // Update UI
            this.updateStats();
            this.renderGrid();
            this.showToast(cull ? 'Marked as culled' : 'Marked as kept', cull ? 'error' : 'success');

        } catch (error) {
            this.showToast('Failed to update file', 'error');
            console.error(error);
        }
    },

    /**
     * Delete all culled files
     */
    async deleteCulled() {
        const culledCount = this.files.filter(f => f.culled).length;
        if (culledCount === 0) {
            this.showToast('No culled files to delete', 'info');
            return;
        }

        if (!confirm(`Are you sure you want to permanently delete ${culledCount} culled files? This cannot be undone!`)) {
            return;
        }

        try {
            const result = await API.deleteCulled(this.currentProject.name);
            this.showToast(`Deleted ${result.total_deleted} files`, 'success');

            // Refresh project
            await this.openProject(this.currentProject.name);

        } catch (error) {
            this.showToast('Failed to delete files', 'error');
            console.error(error);
        }
    },

    /**
     * Delete entire project
     */
    async deleteProject(projectName) {
        if (!confirm(`Are you sure you want to delete the entire project "${projectName}"?\n\nThis will permanently delete all files and cannot be undone!`)) {
            return;
        }

        // Double confirm for safety
        if (!confirm(`FINAL WARNING: Click OK to confirm deletion of "${projectName}" and all its contents.`)) {
            return;
        }

        try {
            await API.deleteProject(projectName);
            this.showToast(`Project "${projectName}" deleted`, 'success');

            // Refresh project list
            this.loadProjects();

        } catch (error) {
            this.showToast('Failed to delete project', 'error');
            console.error(error);
        }
    },

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboard(e) {
        // Ignore if typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        // Close help modal on Escape
        if (e.key === 'Escape') {
            const helpModal = document.getElementById('help-modal');
            if (helpModal && !helpModal.classList.contains('hidden')) {
                this.hideHelpModal();
                return;
            }
        }

        // Lightbox is open - let it handle keys
        if (Lightbox.isOpen) {
            return;
        }

        // Global shortcuts could go here
    },

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        this.elements.toastContainer.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => toast.classList.add('show'));

        // Remove after delay
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Register service worker for PWA
     */
    async registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            try {
                await navigator.serviceWorker.register('/static/sw.js');
                console.log('Service Worker registered');
            } catch (error) {
                console.log('Service Worker registration failed:', error);
            }
        }
    },

    /**
     * Show help modal
     */
    showHelpModal() {
        document.getElementById('help-modal')?.classList.remove('hidden');
    },

    /**
     * Hide help modal
     */
    hideHelpModal() {
        document.getElementById('help-modal')?.classList.add('hidden');
    },

    /**
     * Browse for library path
     */
    async browseLibraryPath() {
        try {
            const response = await fetch('/api/import/browse-folder', { method: 'POST' });
            const data = await response.json();

            if (data.path) {
                this.elements.libraryLocation.value = data.path;
            }
        } catch (error) {
            this.showToast('Failed to open folder picker', 'error');
        }
    },

    /**
     * Save library path setting
     */
    async saveLibraryPath() {
        const path = this.elements.libraryLocation.value.trim();
        if (!path) {
            this.showToast('Please enter a path', 'error');
            return;
        }

        try {
            const response = await fetch('/api/projects/settings/library', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });

            if (response.ok) {
                this.showToast('Library path saved!', 'success');
                this.loadProjects(); // Refresh project list
            } else {
                const data = await response.json();
                this.showToast(data.detail || 'Failed to save', 'error');
            }
        } catch (error) {
            this.showToast('Failed to save library path', 'error');
        }
    },

    /**
     * Toggle the notes panel visibility
     */
    toggleNotesPanel(show) {
        const panel = this.elements.projectNotesPanel;
        if (!panel) return;

        if (show === undefined) {
            // Toggle
            panel.classList.toggle('hidden');
        } else if (show) {
            panel.classList.remove('hidden');
        } else {
            panel.classList.add('hidden');
        }
    },

    /**
     * Save project notes
     */
    async saveProjectNotes() {
        if (!this.currentProject) return;

        const notes = this.elements.projectNotes.value;

        try {
            const response = await fetch(`/api/projects/${encodeURIComponent(this.currentProject.name)}/notes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes })
            });

            if (response.ok) {
                this.showToast('Notes saved!', 'success');
                // Update local state
                if (this.currentProject.metadata) {
                    this.currentProject.metadata.notes = notes;
                }
            } else {
                const data = await response.json();
                this.showToast(data.detail || 'Failed to save notes', 'error');
            }
        } catch (error) {
            this.showToast('Failed to save notes', 'error');
        }
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => App.init());

// Export for use by other modules
window.App = App;
