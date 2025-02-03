document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const chatForm = document.getElementById('chatForm');
    const eventsDisplay = document.getElementById('eventsDisplay');
    const chatMessages = document.getElementById('chatMessages');
    const clearButton = document.getElementById('clearButton');
    const downloadButton = document.getElementById('downloadButton');
    const processButton = document.getElementById('processButton');
    const processingIndicator = document.getElementById('processingIndicator');
    const uploadSection = document.getElementById('uploadSection');
    const chatSection = document.getElementById('chatSection');
    const actionButtons = document.getElementById('actionButtons');

    // Handle file and text upload
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const formData = new FormData(uploadForm);

        try {
            // Disable process button and show processing indicator
            processButton.disabled = true;
            processingIndicator.style.display = 'block';

            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                // Show events display
                eventsDisplay.classList.remove('hidden');
                displayEvents(data.events);
                addSystemMessage('Events have been processed. You can make corrections using the chat below.');

                // Hide upload section and show chat section
                uploadSection.classList.add('hidden');
                chatSection.classList.remove('hidden');

                // Show action buttons
                actionButtons.style.display = 'flex';
            } else {
                addSystemMessage('Error: ' + data.error);
                // Re-enable process button on error
                processButton.disabled = false;
            }
        } catch (error) {
            addSystemMessage('Error processing the request: ' + error.message);
            // Re-enable process button on error
            processButton.disabled = false;
        } finally {
            processingIndicator.style.display = 'none';
        }
    });

    // Handle chat corrections
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const message = document.getElementById('chatInput').value;

        if (!message.trim()) return;

        addUserMessage(message);
        document.getElementById('chatInput').value = '';

        try {
            showLoading(true);
            const response = await fetch('/correct', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ correction: message })
            });

            const data = await response.json();
            if (data.success) {
                displayEvents(data.events);
                addSystemMessage('Events have been updated based on your correction.');
            } else {
                addSystemMessage('Error: ' + data.error);
            }
        } catch (error) {
            addSystemMessage('Error processing the correction: ' + error.message);
        } finally {
            showLoading(false);
        }
    });

    // Handle clear session
    clearButton.addEventListener('click', async function() {
        try {
            const response = await fetch('/clear-session', {
                method: 'POST'
            });

            const data = await response.json();
            if (data.success) {
                // Reset UI state
                eventsDisplay.innerHTML = '';
                eventsDisplay.classList.add('hidden');
                chatMessages.innerHTML = '';
                uploadForm.reset();
                processButton.disabled = false;

                // Show upload section and hide chat section
                uploadSection.classList.remove('hidden');
                chatSection.classList.add('hidden');

                // Hide action buttons
                actionButtons.style.display = 'none';
            }
        } catch (error) {
            addSystemMessage('Error clearing session: ' + error.message);
        }
    });

    // Handle ICS download
    downloadButton.addEventListener('click', async function() {
        try {
            showLoading(true);
            const response = await fetch('/download-ics', {
                method: 'POST'
            });

            const data = await response.json();
            if (data.success) {
                downloadICSFile(data.ics_content);
            } else {
                addSystemMessage('Error: ' + data.error);
            }
        } catch (error) {
            addSystemMessage('Error generating ICS file: ' + error.message);
        } finally {
            showLoading(false);
        }
    });

    function displayEvents(events) {
        eventsDisplay.innerHTML = '';
        events.forEach(event => {
            const eventElement = document.createElement('div');
            eventElement.className = 'event-card fade-in';
            eventElement.innerHTML = `
                <h3>${event.title}</h3>
                <p>${event.description}</p>
                <p><strong>Start:</strong> ${formatDateTime(event.start_time)}</p>
                <p><strong>End:</strong> ${formatDateTime(event.end_time)}</p>
                ${event.location ? `<p><strong>Location:</strong> ${event.location}</p>` : ''}
            `;
            eventsDisplay.appendChild(eventElement);
        });
    }

    function addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message user fade-in';
        messageElement.textContent = message;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addSystemMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message system fade-in';
        messageElement.textContent = message;
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showLoading(show) {
        const loadingSpinner = document.getElementById('loadingSpinner');
        if (loadingSpinner) {
            loadingSpinner.style.display = show ? 'block' : 'none';
        }
    }

    function formatDateTime(isoString) {
        return new Date(isoString).toLocaleString();
    }

    function downloadICSFile(icsContent) {
        const blob = new Blob([icsContent], { type: 'text/calendar' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'events.ics';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
});