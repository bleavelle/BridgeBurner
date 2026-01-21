/**
 * Bridge Burner - Import Module
 * Handles scanning, importing, and converting media files
 */

const Import = {
    // State
    scanResults: null,
    sourceSize: 0,
    targetFreeSpace: 0,
    conversionMultiplier: 17, // DNxHD default
    existingProjects: [],
    conversionJobId: null,

    // Preset size multipliers
    presetMultipliers: {
        'dnxhd_1080p': 17,
        'dnxhd_4k': 20,
        'prores_proxy': 3,
        'prores_lt': 6,
        'prores_422': 10,
        'prores_hq': 15,
        'h264_high': 0.8,
        'h264_medium': 0.5,
        'h265_high': 0.5,
        'h265_medium': 0.3,
        'copy': 1,
    },

    /**
     * Initialize import module
     */
    init() {
        this.bindEvents();
        this.checkFfmpeg();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Browse button - native folder picker
        document.getElementById('btn-browse')?.addEventListener('click', () => this.browseFolder());

        // Scan button
        document.getElementById('btn-scan')?.addEventListener('click', () => this.scanFolder());

        // Enter key in source input
        document.getElementById('import-source')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.scanFolder();
        });

        // Start import button
        document.getElementById('btn-start-import')?.addEventListener('click', () => this.startImport());

        // Convert checkbox toggle
        document.getElementById('import-convert')?.addEventListener('change', (e) => {
            const options = document.getElementById('conversion-options');
            if (options) {
                options.classList.toggle('hidden', !e.target.checked);
                this.updateSizeEstimate();
            }
        });

        // Preset change
        document.getElementById('conversion-preset')?.addEventListener('change', () => {
            this.updateSizeEstimate();
        });

        // Project mode radio buttons
        document.querySelectorAll('input[name="project-mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                const isExisting = e.target.value === 'existing';
                document.getElementById('existing-project-group')?.classList.toggle('hidden', !isExisting);
                document.getElementById('new-project-group')?.classList.toggle('hidden', isExisting);

                if (isExisting) {
                    this.loadExistingProjects();
                }
            });
        });

        // Existing project selection
        document.getElementById('existing-project')?.addEventListener('change', (e) => {
            if (e.target.value) {
                this.loadProjectInfo(e.target.value);
            }
        });
    },

    /**
     * Open native folder picker dialog
     */
    async browseFolder() {
        try {
            const response = await fetch('/api/import/browse-folder', {
                method: 'POST',
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Browse failed');
            }

            const data = await response.json();

            if (data.path) {
                document.getElementById('import-source').value = data.path;
                // Auto-scan after selecting folder
                this.scanFolder();
            } else if (data.cancelled) {
                // User cancelled, do nothing
            }
        } catch (error) {
            App.showToast(error.message, 'error');
            console.error('Browse error:', error);
        }
    },

    /**
     * Check ffmpeg availability
     */
    async checkFfmpeg() {
        try {
            const response = await fetch('/api/import/ffmpeg-status');
            const data = await response.json();

            const statusEl = document.getElementById('ffmpeg-status');
            const versionEl = document.getElementById('ffmpeg-version');

            if (data.available) {
                if (statusEl) statusEl.innerHTML = '<span class="status-ok">FFmpeg OK</span>';
                if (versionEl) versionEl.textContent = data.version || 'FFmpeg available';
            } else {
                if (statusEl) statusEl.innerHTML = '<span class="status-error">FFmpeg Not Found</span>';
                if (versionEl) versionEl.textContent = 'FFmpeg not found - video conversion will not work';
            }
        } catch (error) {
            console.error('Failed to check ffmpeg:', error);
        }
    },

    /**
     * Scan source folder
     */
    async scanFolder() {
        const sourcePath = document.getElementById('import-source')?.value?.trim();
        if (!sourcePath) {
            App.showToast('Please enter a source folder path', 'error');
            return;
        }

        App.showToast('Scanning folder...', 'info');

        try {
            const response = await fetch('/api/import/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: sourcePath })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Scan failed');
            }

            const data = await response.json();
            this.scanResults = data;
            this.sourceSize = data.total_size;

            // Update UI with results
            document.getElementById('scan-raw-count').textContent = data.counts.raw;
            document.getElementById('scan-jpeg-count').textContent = data.counts.jpeg;
            document.getElementById('scan-video-count').textContent = data.counts.video;
            document.getElementById('scan-gopro-count').textContent = data.counts.gopro;
            document.getElementById('scan-other-count').textContent = data.counts.other;
            document.getElementById('scan-total-size').textContent = this.formatSize(data.total_size);

            // Show GoPro warning
            const goproWarning = document.getElementById('gopro-warning');
            if (goproWarning && data.counts.gopro > 0) {
                goproWarning.classList.remove('hidden');
                goproWarning.textContent = `(${data.counts.gopro} GoPro files detected!)`;
            }

            // Get disk space
            await this.checkDiskSpace();

            // Show steps 2 and 3
            document.getElementById('import-step-2')?.classList.remove('hidden');
            document.getElementById('import-step-3')?.classList.remove('hidden');

            App.showToast(`Found ${data.counts.total} files`, 'success');

        } catch (error) {
            App.showToast(error.message, 'error');
            console.error('Scan error:', error);
        }
    },

    /**
     * Check disk space on target drive
     */
    async checkDiskSpace() {
        try {
            const response = await fetch('/api/import/disk-space');
            const data = await response.json();

            if (data.free) {
                this.targetFreeSpace = data.free;
                document.getElementById('target-free-space').textContent =
                    `${this.formatSize(data.free)} (${data.drive})`;

                this.updateSizeEstimate();
            }
        } catch (error) {
            console.error('Failed to check disk space:', error);
        }
    },

    /**
     * Update size estimate based on selected preset
     */
    updateSizeEstimate() {
        const preset = document.getElementById('conversion-preset')?.value || 'dnxhd_1080p';
        const convertEnabled = document.getElementById('import-convert')?.checked;

        this.conversionMultiplier = this.presetMultipliers[preset] || 1;

        // Calculate estimated size
        let estimatedSize = this.sourceSize;
        if (convertEnabled && this.scanResults?.counts?.gopro > 0) {
            // GoPro video size * multiplier + other files
            const goproSize = this.scanResults.files.gopro.reduce((sum, f) => sum + f.size, 0);
            const otherSize = this.sourceSize - goproSize;
            estimatedSize = (goproSize * this.conversionMultiplier) + otherSize;
        }

        document.getElementById('estimated-required').textContent = this.formatSize(estimatedSize);

        // Show warning if not enough space
        const warning = document.getElementById('disk-warning');
        if (warning) {
            const hasSpace = this.targetFreeSpace >= estimatedSize;
            warning.classList.toggle('hidden', hasSpace);
        }
    },

    /**
     * Load list of existing projects
     */
    async loadExistingProjects() {
        try {
            const response = await fetch('/api/projects');
            const data = await response.json();

            this.existingProjects = data.projects;

            const select = document.getElementById('existing-project');
            if (select) {
                select.innerHTML = '<option value="">-- Select Project --</option>';
                data.projects.forEach(project => {
                    const option = document.createElement('option');
                    option.value = project.name;
                    option.textContent = `${project.name} (${project.total_files} files)`;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    },

    /**
     * Load info about a specific project
     */
    async loadProjectInfo(name) {
        try {
            const response = await fetch(`/api/import/project-info/${encodeURIComponent(name)}`);
            const data = await response.json();

            // Auto-fill prefix
            if (data.detected_prefix) {
                document.getElementById('import-file-prefix').value = data.detected_prefix;
            }

            // Show project info
            const infoEl = document.getElementById('existing-project-info');
            if (infoEl) {
                const created = data.metadata.created ? new Date(data.metadata.created).toLocaleDateString() : 'Unknown';
                infoEl.textContent = `Created: ${created}${data.detected_prefix ? ` | Prefix: ${data.detected_prefix}` : ''}`;
            }

            // Fill notes
            if (data.metadata.notes) {
                document.getElementById('import-notes').value = data.metadata.notes;
            }

        } catch (error) {
            console.error('Failed to load project info:', error);
        }
    },

    /**
     * Start the import process
     */
    async startImport() {
        const isExisting = document.querySelector('input[name="project-mode"]:checked')?.value === 'existing';
        let projectName;

        if (isExisting) {
            projectName = document.getElementById('existing-project')?.value;
            if (!projectName) {
                App.showToast('Please select an existing project', 'error');
                return;
            }
        } else {
            projectName = document.getElementById('import-project-name')?.value?.trim();
            if (!projectName) {
                App.showToast('Please enter a project name', 'error');
                return;
            }
        }

        const filePrefix = document.getElementById('import-file-prefix')?.value?.trim();
        if (!filePrefix) {
            App.showToast('Please enter a file name prefix', 'error');
            return;
        }

        const sourcePath = document.getElementById('import-source')?.value?.trim();
        if (!sourcePath) {
            App.showToast('Please scan a source folder first', 'error');
            return;
        }

        // Gather options
        const options = {
            source_path: sourcePath,
            project_name: projectName,
            file_prefix: filePrefix,
            notes: document.getElementById('import-notes')?.value || '',
            organize: true,
            convert_gopro: document.getElementById('import-convert')?.checked || false,
            conversion_preset: document.getElementById('conversion-preset')?.value || 'dnxhd_1080p',
            delete_originals: document.getElementById('import-delete-originals')?.checked || false,
            add_to_existing: isExisting,
        };

        // Show progress view
        document.getElementById('import-step-1')?.classList.add('hidden');
        document.getElementById('import-step-2')?.classList.add('hidden');
        document.getElementById('import-step-3')?.classList.add('hidden');
        document.getElementById('import-step-4')?.classList.remove('hidden');

        document.getElementById('import-progress-text').textContent = 'Copying files... (check terminal for progress)';
        document.getElementById('import-progress-fill').style.width = '10%';

        try {
            const response = await fetch('/api/import/import-v2', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(options)
            });

            // Check if response is ok before parsing
            if (!response.ok) {
                const errorText = await response.text();
                let errorMsg = 'Import failed';
                try {
                    const errorJson = JSON.parse(errorText);
                    errorMsg = errorJson.detail || errorMsg;
                } catch {
                    errorMsg = errorText || errorMsg;
                }
                throw new Error(errorMsg);
            }

            const data = await response.json();
            console.log('[Import] Response:', data);

            if (data.success) {
                const total = Object.values(data.imported).reduce((a, b) => a + b, 0);
                document.getElementById('import-progress-fill').style.width = '100%';

                let statusMsg = `Imported ${total} files (RAW: ${data.imported.RAW}, JPEG: ${data.imported.JPEG}, Video: ${data.imported.Video})`;
                if (data.gopro_queued > 0) {
                    statusMsg += ` | ${data.gopro_queued} GoPro queued for conversion`;
                }
                document.getElementById('import-progress-text').textContent = statusMsg;

                if (data.conversion_job_id) {
                    console.log('[Import] Starting conversion polling for job:', data.conversion_job_id);
                    this.conversionJobId = data.conversion_job_id;
                    document.getElementById('conversion-progress')?.classList.remove('hidden');
                    this.pollConversionProgress();
                } else {
                    App.showToast('Import complete!', 'success');
                    setTimeout(() => this.resetImport(), 3000);
                }
            } else {
                throw new Error(data.error || 'Import failed');
            }

        } catch (error) {
            App.showToast(error.message, 'error');
            document.getElementById('import-progress-text').textContent = `Error: ${error.message}`;
        }
    },

    /**
     * Poll conversion job progress
     */
    async pollConversionProgress() {
        if (!this.conversionJobId) {
            console.log('[Import] No conversion job ID, stopping poll');
            return;
        }

        try {
            console.log('[Import] Polling job:', this.conversionJobId);
            const response = await fetch(`/api/import/jobs/${this.conversionJobId}`);
            const job = await response.json();
            console.log('[Import] Job status:', job);

            document.getElementById('conversion-progress-fill').style.width = `${job.progress}%`;
            document.getElementById('conversion-progress-text').textContent =
                `${job.completed}/${job.total} files converted (${Math.round(job.progress)}%)`;

            if (job.current_file) {
                document.getElementById('conversion-current-file').textContent =
                    `Converting: ${job.current_file}`;
            }

            if (job.status === 'completed') {
                App.showToast('Import and conversion complete!', 'success');
                setTimeout(() => this.resetImport(), 3000);
            } else if (job.status === 'failed') {
                App.showToast('Conversion failed', 'error');
            } else {
                // Continue polling
                setTimeout(() => this.pollConversionProgress(), 2000);
            }

        } catch (error) {
            console.error('Failed to poll conversion progress:', error);
            setTimeout(() => this.pollConversionProgress(), 5000);
        }
    },

    /**
     * Reset import form
     */
    resetImport() {
        // Reset form
        document.getElementById('import-source').value = '';
        document.getElementById('import-project-name').value = '';
        document.getElementById('import-file-prefix').value = '';
        document.getElementById('import-notes').value = '';
        document.getElementById('import-convert').checked = true;
        document.getElementById('import-delete-originals').checked = false;

        // Reset state
        this.scanResults = null;
        this.sourceSize = 0;
        this.conversionJobId = null;

        // Reset visibility
        document.getElementById('import-step-1')?.classList.remove('hidden');
        document.getElementById('import-step-2')?.classList.add('hidden');
        document.getElementById('import-step-3')?.classList.add('hidden');
        document.getElementById('import-step-4')?.classList.add('hidden');
        document.getElementById('conversion-progress')?.classList.add('hidden');
        document.getElementById('gopro-warning')?.classList.add('hidden');

        // Reset progress
        document.getElementById('import-progress-fill').style.width = '0%';
        document.getElementById('conversion-progress-fill').style.width = '0%';
    },

    /**
     * Format bytes to human readable
     */
    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => Import.init());

// Export
window.Import = Import;
