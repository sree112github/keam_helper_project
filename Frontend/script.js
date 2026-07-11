// KEAM Last Rank Finder - Frontend Interactivity Script

// Automatic backend base detection (works locally or served directly from the Go app)
const API_BASE = window.location.origin.startsWith('file://') ? 'http://localhost:8080' : window.location.origin;

// DOM Elements
const selectYear = document.getElementById('select-year');
const selectRound = document.getElementById('select-round');
const selectCollege = document.getElementById('select-college');
const selectCourse = document.getElementById('select-course');
const selectCategory = document.getElementById('select-category');
const btnSearch = document.getElementById('btn-search');

const resultsPlaceholder = document.getElementById('results-placeholder');
const resultsCard = document.getElementById('results-card');
const errorCard = document.getElementById('error-card');

const resultRankValue = document.getElementById('result-rank-value');
const resultCollege = document.getElementById('result-college');
const resultCourse = document.getElementById('result-course');
const resultRound = document.getElementById('result-round');
const resultCategory = document.getElementById('result-category');

const errorTitle = document.getElementById('error-title');
const errorMessage = document.getElementById('error-message');

const disclaimerModal = document.getElementById('disclaimer-modal');
const btnAcceptDisclaimer = document.getElementById('btn-accept-disclaimer');
const themeToggleBtn = document.getElementById('theme-toggle');

// Check saved theme preference immediately to prevent flash of dark theme in light mode
if (localStorage.getItem('keamTheme') === 'light') {
    document.documentElement.classList.add('light-theme');
}

// Function to update the toggle button's icon based on current theme state
function updateThemeIcon() {
    const isLight = document.documentElement.classList.contains('light-theme');
    themeToggleBtn.textContent = isLight ? '🌙' : '☀️';
}

// Set initial icon state
updateThemeIcon();

const apiCache = {};

// Helper to pause execution with random delay (tricks user and spaces requests)
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

// API call wrapper with caching to reduce database load and save bandwidth
async function fetchAPI(endpoint) {
    if (apiCache[endpoint]) {
        return JSON.parse(JSON.stringify(apiCache[endpoint]));
    }
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || 'API request failed');
        }
        apiCache[endpoint] = result.data;
        return result.data;
    } catch (err) {
        console.error(`Error fetching endpoint ${endpoint}:`, err);
        throw err;
    }
}

// Reset helper to clear option list and restore default option
function resetSelect(selectEl, defaultText) {
    selectEl.innerHTML = `<option value="" disabled selected>${defaultText}</option>`;
    selectEl.disabled = true;
}

// Check if all fields are selected to enable Search button
function checkSearchValidity() {
    const isValid = selectYear.value && 
                    selectRound.value && 
                    selectCollege.value && 
                    selectCourse.value && 
                    selectCategory.value;
    
    btnSearch.disabled = !isValid;
}

// Initialize Application Data
async function initApp() {
    // Check disclaimer acceptance status
    if (sessionStorage.getItem('keamDisclaimerAccepted') !== 'true') {
        disclaimerModal.classList.remove('hidden');
        document.body.classList.add('modal-open');
    }

    try {
        // Preload years
        const years = await fetchAPI('/api/years');
        years.forEach(year => {
            const opt = document.createElement('option');
            opt.value = year;
            opt.textContent = year;
            selectYear.appendChild(opt);
        });

        // Preload categories sorted by preferred order
        const categories = await fetchAPI('/api/categories');
        const preferredOrder = ["SM", "EZ", "MU", "LA", "DV", "VK", "BH", "BX", "KN", "KU", "SC", "ST", "EW"];
        categories.sort((a, b) => {
            const indexA = preferredOrder.indexOf(a.code);
            const indexB = preferredOrder.indexOf(b.code);
            if (indexA !== -1 && indexB !== -1) return indexA - indexB;
            if (indexA !== -1) return -1;
            if (indexB !== -1) return 1;
            return a.code.localeCompare(b.code);
        });

        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.code;
            opt.textContent = `${cat.code} - ${cat.name}`;
            selectCategory.appendChild(opt);
        });
    } catch (err) {
        showError('Initialization Error', 'Failed to load initial data. Ensure the backend server is running.');
    }
}

// Dropdown Event Listeners
selectYear.addEventListener('change', async () => {
    // Reset subsequent inputs
    resetSelect(selectRound, 'Select Allotment Round');
    resetSelect(selectCourse, 'Select Course');
    resetSelect(selectCollege, 'Select College');
    selectCategory.value = "";
    selectCategory.disabled = true;
    checkSearchValidity();

    const year = selectYear.value;
    if (!year) return;

    try {
        selectRound.innerHTML = `<option value="" disabled selected>Loading rounds...</option>`;
        const rounds = await fetchAPI(`/api/rounds?year=${year}`);
        await sleep(300 + Math.random() * 400); // random loading delay
        
        selectRound.innerHTML = `<option value="" disabled selected>Select Allotment Round</option>`;
        rounds.forEach(round => {
            const opt = document.createElement('option');
            opt.value = round;
            opt.textContent = round;
            selectRound.appendChild(opt);
        });
        selectRound.disabled = false;
    } catch (err) {
        showError('Load Error', 'Failed to retrieve allotment rounds.');
        resetSelect(selectRound, 'Select Allotment Round');
    }
});

selectRound.addEventListener('change', async () => {
    // Reset subsequent inputs
    resetSelect(selectCourse, 'Select Course');
    resetSelect(selectCollege, 'Select College');
    selectCategory.value = "";
    selectCategory.disabled = true;
    checkSearchValidity();

    const year = selectYear.value;
    const round = selectRound.value;
    if (!year || !round) return;

    try {
        selectCourse.innerHTML = `<option value="" disabled selected>Loading courses...</option>`;
        const courses = await fetchAPI(`/api/courses?year=${year}&round=${encodeURIComponent(round)}`);
        await sleep(300 + Math.random() * 400); // random loading delay
        
        selectCourse.innerHTML = `<option value="" disabled selected>Select Course</option>`;
        courses.forEach(course => {
            const opt = document.createElement('option');
            opt.value = course;
            opt.textContent = course;
            selectCourse.appendChild(opt);
        });
        selectCourse.disabled = false;
    } catch (err) {
        showError('Load Error', 'Failed to retrieve courses.');
        resetSelect(selectCourse, 'Select Course');
    }
});

selectCourse.addEventListener('change', async () => {
    // Reset subsequent inputs
    resetSelect(selectCollege, 'Select College');
    selectCategory.value = "";
    selectCategory.disabled = true;
    checkSearchValidity();

    const year = selectYear.value;
    const round = selectRound.value;
    const course = selectCourse.value;
    if (!year || !round || !course) return;

    try {
        selectCollege.innerHTML = `<option value="" disabled selected>Loading colleges...</option>`;
        const colleges = await fetchAPI(`/api/colleges?year=${year}&round=${encodeURIComponent(round)}&course=${encodeURIComponent(course)}`);
        await sleep(300 + Math.random() * 400); // random loading delay
        
        selectCollege.innerHTML = `<option value="" disabled selected>Select College</option>`;
        colleges.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col.college_code;
            opt.textContent = `${col.college_code} - ${col.college_name}`;
            selectCollege.appendChild(opt);
        });
        selectCollege.disabled = false;
    } catch (err) {
        showError('Load Error', 'Failed to retrieve colleges list.');
        resetSelect(selectCollege, 'Select College');
    }
});

selectCollege.addEventListener('change', () => {
    selectCategory.disabled = false;
    checkSearchValidity();
});

selectCategory.addEventListener('change', () => {
    checkSearchValidity();
});

// Search execution
btnSearch.addEventListener('click', async () => {
    const year = selectYear.value;
    const round = selectRound.value;
    const college = selectCollege.value;
    const course = selectCourse.value;
    const category = selectCategory.value;

    if (!year || !round || !college || !course || !category) return;

    const defaultPlaceholderHTML = `
        <div class="placeholder-icon">🔍</div>
        <h3>Ready to Search</h3>
        <p>Select the year, round, college, course, and category on the left to display the last allotment rank.</p>
    `;

    // Show temporary searching state in placeholder to trick user
    resultsPlaceholder.innerHTML = `
        <div class="placeholder-icon">⏳</div>
        <h3>Searching...</h3>
        <p>Retrieving the allotment cutoff records from database.</p>
    `;
    resultsPlaceholder.classList.remove('hidden');
    resultsCard.classList.add('hidden');
    errorCard.classList.add('hidden');

    try {
        const queryParams = `?year=${year}&round=${encodeURIComponent(round)}&college=${encodeURIComponent(college)}&course=${encodeURIComponent(course)}&category=${encodeURIComponent(category)}`;
        const data = await fetchAPI(`/api/rank${queryParams}`);
        await sleep(400 + Math.random() * 500); // random loading delay

        // Restore placeholder content for future resets
        resultsPlaceholder.innerHTML = defaultPlaceholderHTML;
        resultsPlaceholder.classList.add('hidden');

        // Update result display
        resultRankValue.textContent = Number(data.rank).toLocaleString();
        resultCollege.textContent = `${data.college_code} - ${data.college_name}`;
        resultCourse.textContent = data.course;
        resultRound.textContent = data.round;
        resultCategory.textContent = selectCategory.options[selectCategory.selectedIndex].textContent;

        resultsCard.classList.remove('hidden');
    } catch (err) {
        // Handle no rank / error response
        showError(
            err.message.includes('allotment record') ? 'No College Allotment' : 'No Cutoff Allotment',
            err.message || 'No allotment cutoff rank found for the selected category under this course and round.'
        );
    }
});

function showError(title, msg) {
    resultsPlaceholder.classList.add('hidden');
    resultsCard.classList.add('hidden');
    
    errorTitle.textContent = title;
    errorMessage.textContent = msg;
    errorCard.classList.remove('hidden');
}

// Disclaimer Acceptance click event handler
btnAcceptDisclaimer.addEventListener('click', () => {
    sessionStorage.setItem('keamDisclaimerAccepted', 'true');
    disclaimerModal.classList.add('hidden');
    document.body.classList.remove('modal-open');
});

// Theme toggle click event handler
themeToggleBtn.addEventListener('click', () => {
    const isLight = document.documentElement.classList.toggle('light-theme');
    localStorage.setItem('keamTheme', isLight ? 'light' : 'dark');
    updateThemeIcon();
});

// Start app
window.addEventListener('DOMContentLoaded', initApp);
