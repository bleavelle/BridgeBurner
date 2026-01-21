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
        // Close button and overlay click (debounced)
        this.elements.btnClose.addEventListener('click', debounce(() => this.close()));
        this.elements.overlay.addEventListener('click', debounce(() => this.close()));

        // Navigation (debounced to prevent rapid clicking)
        this.elements.btnPrev.addEventListener('click', debounce(() => this.prev(), 200));
        this.elements.btnNext.addEventListener('click', debounce(() => this.next(), 200));

        // Actions (async debounced - these make API calls)
        this.elements.btnCull.addEventListener('click', debounceAsync(() => this.cull()));
        this.elements.btnKeep.addEventListener('click', debounceAsync(() => this.keep()));
        this.elements.btnGimp.addEventListener('click', debounceAsync(() => this.openInGimp()));

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
                if (data.needs_choice) {
                    // Show choice dialog
                    // Auto-start if it's a new conversion (no existing edits)
                    const autoStart = data.needs_conversion === true;
                    this.showGimpChoiceDialog(data.choices, autoStart);
                } else {
                    App.showToast(data.message, 'success');
                }
            } else {
                App.showToast(data.detail || 'Failed to open in GIMP', 'error');
            }
        } catch (error) {
            console.error('Failed to open in GIMP:', error);
            App.showToast('Failed to open in GIMP', 'error');
        }
    },

    /**
     * Show dialog to choose between multiple GIMP edits
     */
    showGimpChoiceDialog(choices, autoStart = false) {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'gimp-choice-overlay';

        // Check if this is a new conversion (single "convert" choice)
        const isNewConversion = choices.length === 1 && choices[0].type === 'convert';

        overlay.innerHTML = `
            <div class="gimp-choice-dialog">
                <h3>Open in GIMP</h3>
                <p>${isNewConversion ? 'RAW file will be converted to TIFF:' : 'Choose which version to open:'}</p>
                <div class="gimp-choice-buttons">
                    ${choices.map((c, i) => `
                        <button class="btn ${(c.type === 'rebuild' || c.type === 'convert') ? 'btn-primary' : 'btn-secondary'} gimp-choice-btn" data-index="${i}">
                            ${c.label}
                        </button>
                    `).join('')}
                </div>
                <button class="btn btn-link gimp-choice-cancel">Cancel</button>
            </div>
        `;

        // Append to body
        document.body.appendChild(overlay);

        // Handle button clicks (with debounce to prevent double-clicks)
        let processing = false;

        const processChoice = async (btn, choice) => {
            if (processing) return;
            processing = true;

            btn.disabled = true;
            btn.textContent = (choice.type === 'rebuild' || choice.type === 'convert') ? 'Converting...' : 'Opening...';

            if (choice.type === 'rebuild' || choice.type === 'convert') {
                // Convert/rebuild TIFF from RAW
                await this.rebuildTiff(choice.path);
            } else {
                // Open existing file directly
                await this.openGimpDirect(choice.path);
            }
            overlay.remove();
        };

        overlay.querySelectorAll('.gimp-choice-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const choice = choices[parseInt(btn.dataset.index)];
                await processChoice(btn, choice);
            });
        });

        overlay.querySelector('.gimp-choice-cancel').addEventListener('click', () => {
            overlay.remove();
        });

        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });

        // Auto-start conversion for new RAW files
        if (isNewConversion && autoStart) {
            const btn = overlay.querySelector('.gimp-choice-btn');
            processChoice(btn, choices[0]);
        }
    },

    /**
     * Open a specific file directly in GIMP
     */
    async openGimpDirect(filepath) {
        try {
            const response = await fetch(`/api/projects/${this.projectName}/open-in-gimp-direct`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath })
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
     * Rebuild TIFF from RAW and open in GIMP
     */
    async rebuildTiff(rawFilepath) {
        App.showToast('Rebuilding TIFF from RAW... please wait', 'info');

        try {
            const response = await fetch(`/api/projects/${this.projectName}/rebuild-tiff`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filepath: rawFilepath })
            });

            const data = await response.json();

            if (response.ok) {
                App.showToast(data.message, 'success');
            } else {
                App.showToast(data.detail || 'Failed to rebuild TIFF', 'error');
            }
        } catch (error) {
            console.error('Failed to rebuild TIFF:', error);
            App.showToast('Failed to rebuild TIFF', 'error');
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
