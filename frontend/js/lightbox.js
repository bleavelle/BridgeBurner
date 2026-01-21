/**
 * Bridge Burner - Lightbox Component
 * Full-screen image viewer with keyboard navigation
 */

const Lightbox = {
    isOpen: false,
    files: [],
    currentIndex: 0,
    projectName: '',

    // DOM elements
    elements: {},

    /**
     * Initialize lightbox (call once on page load)
     */
    init() {
        this.cacheElements();
        this.bindEvents();
    },

    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.elements = {
            lightbox: document.getElementById('lightbox'),
            overlay: document.querySelector('.lightbox-overlay'),
            image: document.getElementById('lightbox-image'),
            video: document.getElementById('lightbox-video'),
            filename: document.getElementById('lightbox-filename'),
            counter: document.getElementById('lightbox-counter'),
            btnClose: document.getElementById('lightbox-close'),
            btnPrev: document.getElementById('lightbox-prev'),
            btnNext: document.getElementById('lightbox-next'),
            btnCull: document.getElementById('lightbox-cull'),
            btnKeep: document.getElementById('lightbox-keep'),
            btnGimp: document.getElementById('lightbox-gimp'),
        };
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Close button and overlay click
        this.elements.btnClose.addEventListener('click', () => this.close());
        this.elements.overlay.addEventListener('click', () => this.close());

        // Navigation
        this.elements.btnPrev.addEventListener('click', () => this.prev());
        this.elements.btnNext.addEventListener('click', () => this.next());

        // Actions
        this.elements.btnCull.addEventListener('click', () => this.cull());
        this.elements.btnKeep.addEventListener('click', () => this.keep());
        this.elements.btnGimp.addEventListener('click', () => this.openInGimp());

        // Keyboard navigation
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    },

    /**
     * Open lightbox with files
     */
    open(files, startIndex, projectName) {
        this.files = files;
        this.currentIndex = startIndex;
        this.projectName = projectName;
        this.isOpen = true;

        this.elements.lightbox.classList.add('active');
        document.body.style.overflow = 'hidden';

        this.showCurrent();
    },

    /**
     * Close lightbox
     */
    close() {
        this.isOpen = false;
        this.elements.lightbox.classList.remove('active');
        document.body.style.overflow = '';

        // Stop video if playing
        this.elements.video.pause();
        this.elements.video.src = '';
    },

    /**
     * Show current file
     */
    showCurrent() {
        const file = this.files[this.currentIndex];
        if (!file) return;

        const isVideo = file.type === 'video';
        const fileUrl = API.getFileUrl(this.projectName, file.filename);

        // Show image or video
        if (isVideo) {
            this.elements.image.style.display = 'none';
            this.elements.video.style.display = 'block';
            this.elements.video.src = fileUrl;
            this.elements.btnGimp.style.display = 'none';
        } else {
            this.elements.video.style.display = 'none';
            this.elements.video.src = '';
            this.elements.image.style.display = 'block';
            this.elements.image.src = fileUrl;
            this.elements.btnGimp.style.display = '';
        }

        // Update info
        this.elements.filename.textContent = file.filename;
        this.elements.counter.textContent = `${this.currentIndex + 1} / ${this.files.length}`;

        // Update cull/keep button states
        this.updateActionButtons(file.culled);

        // Update navigation button visibility
        this.elements.btnPrev.style.visibility = this.currentIndex > 0 ? 'visible' : 'hidden';
        this.elements.btnNext.style.visibility = this.currentIndex < this.files.length - 1 ? 'visible' : 'hidden';
    },

    /**
     * Update action button states
     */
    updateActionButtons(isCulled) {
        if (isCulled) {
            this.elements.btnCull.classList.add('active');
            this.elements.btnKeep.classList.remove('active');
        } else {
            this.elements.btnCull.classList.remove('active');
            this.elements.btnKeep.classList.add('active');
        }
    },

    /**
     * Go to previous image
     */
    prev() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.showCurrent();
        }
    },

    /**
     * Go to next image
     */
    next() {
        if (this.currentIndex < this.files.length - 1) {
            this.currentIndex++;
            this.showCurrent();
        }
    },

    /**
     * Mark current file as culled
     */
    async cull() {
        const file = this.files[this.currentIndex];
        if (!file) return;

        try {
            await API.cullFile(this.projectName, file.filename);
            file.culled = true;
            this.updateActionButtons(true);

            // Update main app state
            const mainFile = App.files.find(f => f.filename === file.filename);
            if (mainFile) mainFile.culled = true;
            App.updateStats();

            App.showToast('Marked as culled', 'success');

            // Auto-advance to next image
            if (this.currentIndex < this.files.length - 1) {
                this.next();
            }

        } catch (error) {
            App.showToast('Failed to cull file', 'error');
            console.error(error);
        }
    },

    /**
     * Mark current file as kept
     */
    async keep() {
        const file = this.files[this.currentIndex];
        if (!file) return;

        try {
            await API.keepFile(this.projectName, file.filename);
            file.culled = false;
            this.updateActionButtons(false);

            // Update main app state
            const mainFile = App.files.find(f => f.filename === file.filename);
            if (mainFile) mainFile.culled = false;
            App.updateStats();

            App.showToast('Marked as kept', 'success');

            // Auto-advance to next image
            if (this.currentIndex < this.files.length - 1) {
                this.next();
            }

        } catch (error) {
            App.showToast('Failed to keep file', 'error');
            console.error(error);
        }
    },

    /**
     * Open current file in GIMP
     */
    async openInGimp() {
        const file = this.files[this.currentIndex];
        if (!file || file.type === 'video') return;

        try {
            const response = await fetch(`/api/projects/${this.projectName}/open-in-gimp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath: file.filepath })
            });

            const data = await response.json();

            if (response.ok) {
                App.showToast(data.message, 'success');
            } else {
                App.showToast(data.detail || 'Failed to open in GIMP', 'error');
            }
        } catch (error) {
            console.error('Failed to open in GIMP:', error);
            App.showToast('Failed to open in GIMP', 'error');
        }
    },

    /**
     * Handle keyboard shortcuts
     */
    handleKeyboard(e) {
        if (!this.isOpen) return;

        switch (e.key) {
            case 'Escape':
                this.close();
                break;
            case 'ArrowLeft':
                this.prev();
                break;
            case 'ArrowRight':
                this.next();
                break;
            case 'x':
            case 'X':
                this.cull();
                break;
            case 'k':
            case 'K':
                this.keep();
                break;
            case ' ':
                e.preventDefault();
                // Toggle cull state
                const file = this.files[this.currentIndex];
                if (file) {
                    file.culled ? this.keep() : this.cull();
                }
                break;
            case 'g':
            case 'G':
                this.openInGimp();
                break;
        }
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => Lightbox.init());

// Export for use by App
window.Lightbox = Lightbox;
