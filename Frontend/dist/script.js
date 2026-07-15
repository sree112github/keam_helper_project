const RENDER_BACKEND_URL = 'https://keam-helper-project.onrender.com';
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.origin.startsWith('file://')
    ? 'http://localhost:8080'
    : RENDER_BACKEND_URL;
const selectYear = document.getElementById('select-year');
const selectRound = document.getElementById('select-round');
const selectCollege = document.getElementById('select-college');
const selectCourse = document.getElementById('select-course');
const selectCategory = document.getElementById('select-category');
const btnSearch = document.getElementById('btn-search');
const resultsPlaceholder = document.getElementById('results-placeholder');
const resultsCard = document.getElementById('results-card');
const errorCard = document.getElementById('error-card');
const predictResultsCard = document.getElementById('predict-results-card');
const predictTbody = document.getElementById('predict-tbody');
const btnRetryInit = document.getElementById('btn-retry-init');
const tabSearch = document.getElementById('tab-search');
const tabPredict = document.getElementById('tab-predict');
const searchForm = document.getElementById('search-form');
const predictForm = document.getElementById('predict-form');
const predictYear = document.getElementById('predict-year');
const predictCourse = document.getElementById('predict-course');
const predictRank = document.getElementById('predict-rank');
const predictCategory = document.getElementById('predict-category');
const btnPredict = document.getElementById('btn-predict');
const DEFAULT_PLACEHOLDER_HTML = `
    <div class="placeholder-icon">🔍</div>
    <h3>Ready to Search</h3>
    <p>Select the year, round, college, course, and category on the left to display the last allotment rank.</p>
`;
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
if (localStorage.getItem('keamTheme') === 'light') {
    document.documentElement.classList.add('light-theme');
}
function updateThemeIcon() {
    const isLight = document.documentElement.classList.contains('light-theme');
    themeToggleBtn.textContent = isLight ? '🌙' : '☀️';
}
updateThemeIcon();
const apiCache = {};
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function fetchAPI(endpoint, retries = 5, delay = 5000) {
    if (apiCache[endpoint]) {
        return JSON.parse(JSON.stringify(apiCache[endpoint]));
    }
    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.message || 'API request failed');
            }
            apiCache[endpoint] = result.data;
            return result.data;
        } catch (err) {
            console.warn(`Attempt ${attempt} to fetch ${endpoint} failed:`, err);
            if (attempt === retries) {
                console.error(`Max retries reached for endpoint ${endpoint}`);
                throw err;
            }
            const statusText = document.querySelector('#results-placeholder h3');
            const statusDesc = document.querySelector('#results-placeholder p');
            if (statusText && endpoint === '/api/years') {
                statusText.textContent = `Connecting to server (Attempt ${attempt + 1}/${retries})...`;
                statusDesc.textContent = `Waking up the backend database. This may take up to a minute on the free hosting tier. Retrying in ${delay / 1000} seconds...`;
            }
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}
function resetSelect(selectEl, defaultText) {
    selectEl.innerHTML = `<option value="" disabled selected>${defaultText}</option>`;
    selectEl.disabled = true;
}
function checkSearchValidity() {
    const isValid = selectYear.value &&
        selectRound.value &&
        selectCollege.value &&
        selectCourse.value &&
        selectCategory.value;
    btnSearch.disabled = !isValid;
}
function checkPredictValidity() {
    const isValid = predictYear.value &&
        predictCourse.value &&
        predictRank.value &&
        predictCategory.value;
    btnPredict.disabled = !isValid;
}
tabSearch.addEventListener('click', () => {
    tabSearch.classList.add('active');
    tabPredict.classList.remove('active');
    searchForm.classList.remove('hidden');
    predictForm.classList.add('hidden');
    predictResultsCard.classList.add('hidden');
    if (resultsCard.classList.contains('hidden') && errorCard.classList.contains('hidden')) {
        resultsPlaceholder.classList.remove('hidden');
    }
});
tabPredict.addEventListener('click', () => {
    tabPredict.classList.add('active');
    tabSearch.classList.remove('active');
    predictForm.classList.remove('hidden');
    searchForm.classList.add('hidden');
    resultsCard.classList.add('hidden');
    errorCard.classList.add('hidden');
    if (predictResultsCard.classList.contains('hidden')) {
        resultsPlaceholder.classList.remove('hidden');
    }
});
async function initApp() {
    if (sessionStorage.getItem('keamDisclaimerAccepted') !== 'true') {
        disclaimerModal.classList.remove('hidden');
        document.body.classList.add('modal-open');
    }
    errorCard.classList.add('hidden');
    resultsCard.classList.add('hidden');
    btnRetryInit.classList.add('hidden');
    selectYear.disabled = true;
    selectRound.disabled = true;
    selectCourse.disabled = true;
    selectCollege.disabled = true;
    selectCategory.disabled = true;
    resultsPlaceholder.innerHTML = `
        <div class="spinner-ring"></div>
        <h3>Connecting to server...</h3>
        <p>Waking up the backend database instance. This may take up to a minute on the free hosting tier.</p>
    `;
    resultsPlaceholder.classList.remove('hidden');
    try {
        const years = await fetchAPI('/api/years');
        selectYear.innerHTML = `<option value="" disabled selected>Select Year</option>`;
        years.forEach(year => {
            const opt = document.createElement('option');
            opt.value = year;
            opt.textContent = year;
            selectYear.appendChild(opt);
        });
        selectYear.disabled = false;
        predictYear.innerHTML = `<option value="" disabled selected>Select Year</option><option value="2026">2026</option>`;
        predictYear.disabled = false;
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
        selectCategory.innerHTML = `<option value="" disabled selected>Select Category</option>`;
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.code;
            opt.textContent = `${cat.code} - ${cat.name}`;
            selectCategory.appendChild(opt);
            const pOpt = document.createElement('option');
            pOpt.value = cat.code;
            pOpt.textContent = `${cat.code} - ${cat.name}`;
            predictCategory.appendChild(pOpt);
        });
        resultsPlaceholder.innerHTML = DEFAULT_PLACEHOLDER_HTML;
    } catch (err) {
        showError(
            'Server Wake-up Timeout',
            'The backend database is taking longer than expected to spin up or is currently offline. Please click the button below to retry connecting.',
            true
        );
    }
}
selectYear.addEventListener('change', async () => {
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
        await sleep(300 + Math.random() * 400); 
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
        await sleep(300 + Math.random() * 400); 
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
        await sleep(300 + Math.random() * 400); 
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
btnSearch.addEventListener('click', async () => {
    const year = selectYear.value;
    const round = selectRound.value;
    const college = selectCollege.value;
    const course = selectCourse.value;
    const category = selectCategory.value;
    if (!year || !round || !college || !course || !category) return;
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
        await sleep(400 + Math.random() * 500); 
        resultsPlaceholder.innerHTML = DEFAULT_PLACEHOLDER_HTML;
        resultsPlaceholder.classList.add('hidden');
        resultRankValue.textContent = Number(data.rank).toLocaleString();
        resultCollege.textContent = `${data.college_code} - ${data.college_name}`;
        resultCourse.textContent = data.course;
        resultRound.textContent = data.round;
        resultCategory.textContent = selectCategory.options[selectCategory.selectedIndex].textContent;
        resultsCard.classList.remove('hidden');
    } catch (err) {
        showError(
            err.message.includes('allotment record') ? 'No College Allotment' : 'No Cutoff Allotment',
            err.message || 'No allotment cutoff rank found for the selected category under this course and round.'
        );
    }
});
function showError(title, msg, showRetry = false) {
    resultsPlaceholder.classList.add('hidden');
    resultsCard.classList.add('hidden');
    predictResultsCard.classList.add('hidden');
    errorTitle.textContent = title;
    errorMessage.textContent = msg;
    errorCard.classList.remove('hidden');
    if (showRetry) {
        btnRetryInit.classList.remove('hidden');
    } else {
        btnRetryInit.classList.add('hidden');
    }
}
predictYear.addEventListener('change', async () => {
    resetSelect(predictCourse, 'Select Course');
    predictRank.value = '';
    predictRank.disabled = true;
    predictCategory.value = "";
    predictCategory.disabled = true;
    checkPredictValidity();
    const year = predictYear.value;
    if (!year) return;
    try {
        predictCourse.innerHTML = `<option value="" disabled selected>Loading courses...</option>`;
        const queryYear = year === '2026' ? 2025 : year;
        const queryRound = year === '2026' ? 'Second Phase Allotment' : '';
        let url = `/api/courses?year=${queryYear}`;
        if (queryRound) url += `&round=${encodeURIComponent(queryRound)}`;
        const courses = await fetchAPI(url);
        await sleep(300 + Math.random() * 400);
        predictCourse.innerHTML = `<option value="" disabled selected>Select Course</option>`;
        courses.forEach(course => {
            const opt = document.createElement('option');
            opt.value = course;
            opt.textContent = course;
            predictCourse.appendChild(opt);
        });
        predictCourse.disabled = false;
    } catch (err) {
        showError('Load Error', 'Failed to retrieve courses for prediction.');
        resetSelect(predictCourse, 'Select Course');
    }
});
predictCourse.addEventListener('change', () => {
    predictRank.disabled = false;
    predictCategory.disabled = false;
    checkPredictValidity();
});
predictRank.addEventListener('input', () => {
    checkPredictValidity();
});
predictCategory.addEventListener('change', () => {
    checkPredictValidity();
});
btnPredict.addEventListener('click', async () => {
    const year = predictYear.value;
    const course = predictCourse.value;
    const rank = predictRank.value;
    const category = predictCategory.value;
    if (!year || !course || !rank || !category) return;
    resultsPlaceholder.innerHTML = `
        <div class="placeholder-icon">⏳</div>
        <h3>Predicting...</h3>
        <p>Finding colleges where you are eligible based on cutoff ranks.</p>
    `;
    resultsPlaceholder.classList.remove('hidden');
    predictResultsCard.classList.add('hidden');
    errorCard.classList.add('hidden');
    try {
        const queryYear = year === '2026' ? 2025 : year;
        const queryRound = year === '2026' ? 'Second Phase Allotment' : '';
        const queryParams = `?year=${queryYear}&course=${encodeURIComponent(course)}&rank=${encodeURIComponent(rank)}&category=${encodeURIComponent(category)}&round=${encodeURIComponent(queryRound)}`;
        const randomDelay = Math.floor(Math.random() * (5000 - 100 + 1)) + 100;
        await sleep(randomDelay);
        const predictions = await fetchAPI(`/api/predict${queryParams}`);
        resultsPlaceholder.innerHTML = DEFAULT_PLACEHOLDER_HTML;
        resultsPlaceholder.classList.add('hidden');
        predictTbody.innerHTML = '';
        if (predictions && predictions.length > 0) {
            predictions.forEach(p => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${p.college_code}</td>
                    <td>${p.college_name}</td>
                    <td>${p.round}</td>
                    <td><span class="highlight-rank">${Number(p.cutoff_rank).toLocaleString()}</span></td>
                `;
                predictTbody.appendChild(tr);
            });
            predictResultsCard.classList.remove('hidden');
        } else {
            showError('No Colleges Found', 'Unfortunately, your rank does not meet the cutoff for any college in the selected course and category.');
        }
    } catch (err) {
        showError('Prediction Error', err.message || 'An error occurred while predicting colleges.');
    }
});
btnRetryInit.addEventListener('click', () => {
    initApp();
});
btnAcceptDisclaimer.addEventListener('click', () => {
    sessionStorage.setItem('keamDisclaimerAccepted', 'true');
    disclaimerModal.classList.add('hidden');
    document.body.classList.remove('modal-open');
});
themeToggleBtn.addEventListener('click', () => {
    const isLight = document.documentElement.classList.toggle('light-theme');
    localStorage.setItem('keamTheme', isLight ? 'light' : 'dark');
    updateThemeIcon();
});
window.addEventListener('DOMContentLoaded', initApp);