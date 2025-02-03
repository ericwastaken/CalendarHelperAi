document.addEventListener('DOMContentLoaded', function() {
    // Existing elements
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

    // New elements for modals
    const dataModal = document.getElementById('dataModal');
    const readMoreLink = document.getElementById('readMoreLink');
    const termsLink = document.getElementById('termsLink');
    const closeDataModalBtn = document.getElementById('closeDataModal');

    // Modal functionality
    function toggleModal(modal, show) {
        if (show) {
            // Load terms content if it hasn't been loaded yet
            const termsContent = document.getElementById('termsContent');
            if (!termsContent.innerHTML) {
                fetch('/static/terms.html')
                    .then(response => response.text())
                    .then(html => {
                        termsContent.innerHTML = html;
                        // Reset scroll position when content is loaded
                        const modalContent = modal.querySelector('.modal-content');
                        if (modalContent) {
                            modalContent.scrollTop = 0;
                        }
                    })
                    .catch(error => console.error('Error loading terms:', error));
            } else {
                // Reset scroll position when reopening
                const modalContent = modal.querySelector('.modal-content');
                if (modalContent) {
                    modalContent.scrollTop = 0;
                }
            }
        }
        modal.style.display = show ? 'block' : 'none';
        if (show) {
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        } else {
            document.body.style.overflow = ''; // Restore scrolling
        }
    }

    readMoreLink?.addEventListener('click', function(e) {
        e.preventDefault();
        toggleModal(dataModal, true);
    });

    termsLink.addEventListener('click', function(e) {
        e.preventDefault();
        toggleModal(dataModal, true);
    });

    closeDataModalBtn.addEventListener('click', function() {
        toggleModal(dataModal, false);
    });

    window.addEventListener('click', function(e) {
        if (e.target === dataModal) {
            toggleModal(dataModal, false);
        }
    });

    // Calendar Request section elements
    const calendarRequest = document.getElementById('calendarRequest');
    const originalImageContainer = document.getElementById('originalImageContainer');
    const originalTextContainer = document.getElementById('originalTextContainer');
    const originalImage = document.getElementById('originalImage');
    const originalText = document.getElementById('originalText');
    const imageModal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const closeImageModalBtn = document.querySelector('.close-modal');

    let sessionTimeout;

    // Image modal functionality
    if (originalImage) {
        originalImage.addEventListener('click', function() {
            imageModal.style.display = 'block';
        });
    }

    if (closeImageModalBtn) {
        closeImageModalBtn.addEventListener('click', function() {
            imageModal.style.display = 'none';
        });
    }

    if (imageModal) {
        imageModal.addEventListener('click', function(e) {
            if (e.target === imageModal) {
                imageModal.style.display = 'none';
            }
        });
    }
    // Handle file and text upload
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const formData = new FormData(uploadForm);
        
        // Show processing indicator and disable button
        processButton.disabled = true;
        processingIndicator.style.display = 'block';
        
        try {
            // Disable process button and show processing indicator
            processButton.disabled = true;
            processingIndicator.style.display = 'block';

            // Store original input
            const imageFile = formData.get('image');
            const textInput = formData.get('text');

            // Disable process button and show processing indicator
            processButton.disabled = true;
            processingIndicator.style.display = 'block';

            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'X-Timezone': Intl.DateTimeFormat().resolvedOptions().timeZone
                },
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                // Display original input in Calendar Request section
                if (imageFile) {
                    const imageUrl = URL.createObjectURL(imageFile);
                    originalImage.src = imageUrl;
                    modalImage.src = imageUrl;
                    originalImageContainer.classList.remove('hidden');
                }

                const displayText = textInput || "Extract the events in this image.";
                originalTextContainer.classList.remove('hidden');
                originalText.textContent = displayText;


                // Show calendar request section
                calendarRequest.classList.remove('hidden');

                // Show events display
                eventsDisplay.classList.remove('hidden');
                displayEvents(data.events);
                addSystemMessage('Events have been processed.');

                // Hide upload section and show chat section
                uploadSection.classList.add('hidden');
                chatSection.classList.remove('hidden');

                // Show action buttons
                actionButtons.style.display = 'flex';

                // Set 1-hour timeout
                clearTimeout(sessionTimeout);
                sessionTimeout = setTimeout(clearSession, 3600000); // 1 hour in milliseconds
            } else {
                addSystemMessage('Error: ' + data.error);
                processButton.disabled = false;
            }
        } catch (error) {
            console.error('Processing error:', error);
            addSystemMessage('Error processing the request: ' + error.message);
            processButton.disabled = false;
        } finally {
            processingIndicator.style.display = 'none';
        }
    });


    // Handle clear session
    async function clearSession() {
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

                // Clear original input display
                originalImage.src = '';
                originalText.textContent = '';
                calendarRequest.classList.add('hidden');
                originalImageContainer.classList.add('hidden');
                originalTextContainer.classList.add('hidden');

                // Show upload section and hide chat section
                uploadSection.classList.remove('hidden');
                chatSection.classList.add('hidden');

                // Hide action buttons
                actionButtons.style.display = 'none';

                // Clear timeout
                clearTimeout(sessionTimeout);
            }
        } catch (error) {
            addSystemMessage('Error clearing session: ' + error.message);
        }
    }

    clearButton.addEventListener('click', clearSession);
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