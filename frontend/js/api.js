/**
 * Bridge Burner API Client
 * Handles all communication with the FastAPI backend
 */

const API = {
    baseUrl: '/api/projects',

    /**
     * Fetch all projects
     * @returns {Promise<{projects: Array, library_path: string}>}
     */
    async getProjects() {
        const response = await fetch(this.baseUrl);
        if (!response.ok) {
            throw new Error(`Failed to fetch projects: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Fetch a single project's details and files
     * @param {string} name - Project name
     * @returns {Promise<Object>}
     */
    async getProject(name) {
        const response = await fetch(`${this.baseUrl}/${encodeURIComponent(name)}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch project: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Get full-size image URL
     * @param {string} projectName - Project name
     * @param {string} filename - File name
     * @returns {string}
     */
    getFileUrl(projectName, filename) {
        return `${this.baseUrl}/${encodeURIComponent(projectName)}/files/${encodeURIComponent(filename)}`;
    },

    /**
     * Get thumbnail URL
     * @param {string} projectName - Project name
     * @param {string} filename - File name
     * @returns {string}
     */
    getThumbnailUrl(projectName, filename) {
        return `${this.baseUrl}/${encodeURIComponent(projectName)}/thumbnail/${encodeURIComponent(filename)}`;
    },

    /**
     * Mark a file as culled
     * @param {string} projectName - Project name
     * @param {string} filename - File name
     * @returns {Promise<Object>}
     */
    async cullFile(projectName, filename) {
        const response = await fetch(`${this.baseUrl}/${encodeURIComponent(projectName)}/cull`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        if (!response.ok) {
            throw new Error(`Failed to cull file: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Unmark a file (keep it)
     * @param {string} projectName - Project name
     * @param {string} filename - File name
     * @returns {Promise<Object>}
     */
    async keepFile(projectName, filename) {
        const response = await fetch(`${this.baseUrl}/${encodeURIComponent(projectName)}/keep`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        if (!response.ok) {
            throw new Error(`Failed to keep file: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * Delete all culled files from a project
     * @param {string} projectName - Project name
     * @returns {Promise<Object>}
     */
    async deleteCulled(projectName) {
        const response = await fetch(`${this.baseUrl}/${encodeURIComponent(projectName)}/culled`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error(`Failed to delete culled files: ${response.statusText}`);
        }
        return response.json();
    }
};

// Export for use in other modules
window.API = API;
