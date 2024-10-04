const ovenCount = 4;
const defaultSkewersCount = 7;
const chickensPerSkewer = 4;

function createOvenElement(ovenNumber) {
    return `
        <div class="oven" id="oven${ovenNumber}">
            <h2>Oven ${ovenNumber}</h2>
            <p>Status: <span id="oven${ovenNumber}-status">Empty</span></p>
            <p>Start Time: <span id="oven${ovenNumber}-start">-</span></p>
            <p>Expected End Time: <span id="oven${ovenNumber}-end">-</span></p>
            <p>Actual End Time: <span id="oven${ovenNumber}-actual-end">-</span></p>
            <p>Chickens: <span id="oven${ovenNumber}-chickens">0</span></p>
            <input type="number" id="oven${ovenNumber}-capacity" value="${defaultSkewersCount}" min="1" max="25">
            <button onclick="startCooking(${ovenNumber})">Start Cooking</button>
            <button onclick="finishCooking(${ovenNumber})" id="finish-${ovenNumber}" disabled>Finish Cooking</button>
            <div id="oven${ovenNumber}-time-adjust" style="display:none;">
                <input type="number" id="oven${ovenNumber}-time-left" min="1" value="90">
                <button onclick="adjustCookingTime(${ovenNumber})">Adjust Time</button>
            </div>
            <div id="oven${ovenNumber}-post-rush" style="display:none;">
                <p>Chickens Left After Rush: <input type="number" id="oven${ovenNumber}-left" min="0" max="${defaultSkewersCount * chickensPerSkewer}"></p>
                <button onclick="logPostRush(${ovenNumber})">Log Post-Rush</button>
            </div>
        </div>
    `;
}

function initializeOvens() {
    const ovensContainer = document.getElementById('ovens');
    for (let i = 1; i <= ovenCount; i++) {
        ovensContainer.innerHTML += createOvenElement(i);
    }
    loadOvenStates();
}

function loadOvenStates() {
    fetch('/oven_states')
        .then(response => response.json())
        .then(states => {
            for (let i = 1; i <= ovenCount; i++) {
                const ovenState = states[i] || {};
                updateOvenDisplay(i, ovenState);
            }
        })
        .catch(error => console.error('Error loading oven states:', error));
}

function updateOvenDisplay(ovenNumber, state) {
    const finishButton = document.getElementById(`finish-${ovenNumber}`);
    
    if (state.status === 'Cooking' || state.status === 'Ready') {
        document.getElementById(`oven${ovenNumber}-status`).textContent = state.status;
        document.getElementById(`oven${ovenNumber}-start`).textContent = new Date(state.startTime).toLocaleTimeString();
        document.getElementById(`oven${ovenNumber}-end`).textContent = new Date(state.expectedEndTime).toLocaleTimeString();
        document.getElementById(`oven${ovenNumber}-chickens`).textContent = state.chickens;
        document.getElementById(`oven${ovenNumber}-time-adjust`).style.display = state.status === 'Cooking' ? 'block' : 'none';
        document.getElementById(`oven${ovenNumber}-post-rush`).style.display = state.status === 'Ready' ? 'block' : 'none';
        
        finishButton.disabled = false;
        
        if (state.status === 'Ready') {
            document.getElementById(`oven${ovenNumber}-actual-end`).textContent = new Date(state.actualEndTime).toLocaleTimeString();
            finishButton.disabled = true;
        }
    } else {
        // Reset display for empty oven
        document.getElementById(`oven${ovenNumber}-status`).textContent = 'Empty';
        document.getElementById(`oven${ovenNumber}-start`).textContent = '-';
        document.getElementById(`oven${ovenNumber}-end`).textContent = '-';
        document.getElementById(`oven${ovenNumber}-actual-end`).textContent = '-';
        document.getElementById(`oven${ovenNumber}-chickens`).textContent = '0';
        document.getElementById(`oven${ovenNumber}-time-adjust`).style.display = 'none';
        document.getElementById(`oven${ovenNumber}-post-rush`).style.display = 'none';
        
        finishButton.disabled = true;
    }
}

function updateOvenState(ovenNumber, state) {
    fetch('/update_oven_state', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ oven: ovenNumber, state: state }),
    })
    .then(response => response.json())
    .then(data => console.log('Oven state updated successfully:', data))
    .catch((error) => console.error('Error updating oven state:', error));
}

function startCooking(ovenNumber) {
    const now = new Date();
    const skewersCount = parseInt(document.getElementById(`oven${ovenNumber}-capacity`).value);
    const chickenCount = skewersCount * chickensPerSkewer;
    const expectedEndTime = new Date(now.getTime() + 90 * 60000); // 90 minutes from now

    const state = {
        status: 'Cooking',
        startTime: now.toISOString(),
        expectedEndTime: expectedEndTime.toISOString(),
        chickens: chickenCount
    };

    updateOvenDisplay(ovenNumber, state);
    updateOvenState(ovenNumber, state);

    logActivity(`Started cooking ${skewersCount} skewers (${chickenCount} chickens) in Oven ${ovenNumber}`);
    sendLog('start_cooking', { 
        oven: ovenNumber, 
        chickens: chickenCount, 
        start_time: now.toISOString(),
        expected_end_time: expectedEndTime.toISOString()
    });
}

function adjustCookingTime(ovenNumber) {
    const timeLeft = parseInt(document.getElementById(`oven${ovenNumber}-time-left`).value);
    if (timeLeft <= 0) {
        alert("Please enter a positive number for the cooking time.");
        return;
    }
    const now = new Date();
    const newEndTime = new Date(now.getTime() + timeLeft * 60000);

    document.getElementById(`oven${ovenNumber}-end`).textContent = newEndTime.toLocaleTimeString();

    // Update oven state
    const state = {
        status: 'Cooking',
        startTime: document.getElementById(`oven${ovenNumber}-start`).textContent,
        expectedEndTime: newEndTime.toISOString(),
        chickens: parseInt(document.getElementById(`oven${ovenNumber}-chickens`).textContent)
    };
    updateOvenState(ovenNumber, state);

    logActivity(`Adjusted cooking time for Oven ${ovenNumber}. New expected end time: ${newEndTime.toLocaleTimeString()}`);
    sendLog('adjust_cooking_time', { 
        oven: ovenNumber, 
        new_time_left: timeLeft,
        new_expected_end_time: newEndTime.toISOString()
    });
}

function finishCooking(ovenNumber) {
    const now = new Date();
    const startTime = document.getElementById(`oven${ovenNumber}-start`).textContent;
    const expectedEndTime = document.getElementById(`oven${ovenNumber}-end`).textContent;
    const chickenCount = parseInt(document.getElementById(`oven${ovenNumber}-chickens`).textContent);

    const state = {
        status: 'Ready',
        startTime: startTime,
        expectedEndTime: expectedEndTime,
        actualEndTime: now.toISOString(),
        chickens: chickenCount
    };

    updateOvenDisplay(ovenNumber, state);
    updateOvenState(ovenNumber, state);

    logActivity(`Finished cooking in Oven ${ovenNumber}`);
    sendLog('finish_cooking', { 
        oven: ovenNumber, 
        chickens: chickenCount,
        start_time: startTime,
        expected_end_time: expectedEndTime,
        actual_end_time: now.toISOString()
    });
}

function logPostRush(ovenNumber) {
    const chickensLeft = parseInt(document.getElementById(`oven${ovenNumber}-left`).value);
    const totalChickens = parseInt(document.getElementById(`oven${ovenNumber}-chickens`).textContent);
    const chickensTaken = totalChickens - chickensLeft;

    updateOvenDisplay(ovenNumber, {}); // Reset oven display
    updateOvenState(ovenNumber, {}); // Clear oven state

    logActivity(`Post-rush: ${chickensTaken} chickens taken, ${chickensLeft} chickens left from Oven ${ovenNumber}`);
    sendLog('post_rush', { 
        oven: ovenNumber, 
        chickens_taken: chickensTaken,
        chickens_left: chickensLeft,
        time: new Date().toISOString()
    });
}

function logActivity(message) {
    const logElement = document.getElementById('activity-log');
    const li = document.createElement('li');
    li.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
    logElement.prepend(li);
}

function sendLog(action, data) {
    fetch('/log', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action: action, data: data }),
    })
    .then(response => response.json())
    .then(data => console.log('Log sent successfully:', data))
    .catch((error) => console.error('Error sending log:', error));
}

// Initialize ovens when the page loads
document.addEventListener('DOMContentLoaded', initializeOvens);

// Periodically refresh oven states
setInterval(loadOvenStates, 30000); // Refresh every 30 seconds
