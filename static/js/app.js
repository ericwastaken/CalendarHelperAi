document.addEventListener('DOMContentLoaded', async function() {
    // Fetch config on page load
    let appConfig;
    try {
        const configResponse = await fetch('/api/config');
        if (!configResponse.ok) {
            throw new Error(`Failed to fetch config: ${configResponse.status}`);
        }
        appConfig = await configResponse.json();
    } catch (error) {
        console.error("Error fetching config:", error);
        appConfig = { maxImageSize: 4 * 1024 * 1024, allowedImageTypes: ['image/jpeg', 'image/jpg', 'image/png', 'image/tiff'] };
    }

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
    const exampleLink = document.getElementById('exampleLink');
    const exampleModal = document.getElementById('exampleModal');
    const closeExampleModalBtn = document.getElementById('closeExampleModal');

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
        if (e.target === exampleModal) {
            toggleModal(exampleModal, false);
        }
    });

    exampleLink.addEventListener('click', function(e) {
        e.preventDefault();
        const exampleContent = document.getElementById('exampleContent');
        if (!exampleContent.innerHTML) {
            fetch('/static/example-images-and-prompts.html')
                .then(response => response.text())
                .then(html => {
                    exampleContent.innerHTML = html;
                });
        }
        toggleModal(exampleModal, true);
    });

    closeExampleModalBtn.addEventListener('click', function() {
        toggleModal(exampleModal, false);
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
    originalImage.addEventListener('click', function() {
        imageModal.style.display = 'block';
        document.body.style.overflow = 'hidden';
    });

    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', function() {
            imageModal.style.display = 'none';
            document.body.style.overflow = '';
        });
    });

    imageModal.addEventListener('click', function(e) {
        if (e.target === imageModal) {
            imageModal.style.display = 'none';
            document.body.style.overflow = '';
        }
    });
    // Handle file and text upload
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const formData = new FormData(uploadForm);

        try {
            // Store original input
            const imageFile = formData.get('image');
            const textInput = formData.get('text');

            const maxImageSize = appConfig.maxImageSize;
            const allowedImageTypes = appConfig.allowedImageTypes;


            // Check file size using server config
            if (imageFile && imageFile.size > maxImageSize) {
                const errorContainer = document.getElementById('promptErrorContainer');
                const errorMessage = document.getElementById('promptErrorMessage');
                errorMessage.textContent = `Please limit your image to ${maxImageSize/(1024*1024)}mb`;
                errorContainer.style.display = 'block';
                processButton.disabled = false;
                return;
            }

            // Check file type using server config
            if (imageFile && !allowedImageTypes.includes(imageFile.type)) {
                const errorContainer = document.getElementById('promptErrorContainer');
                const errorMessage = document.getElementById('promptErrorMessage');
                errorMessage.textContent = `Please use ${allowedImageTypes.join(', ')} images only`;
                errorContainer.style.display = 'block';
                processButton.disabled = false;
                return;
            }

            // Disable process button and show processing indicator
            processButton.disabled = true;
            processButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Analyzing events...';
            processingIndicator.style.display = 'block';

            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'X-Timezone': Intl.DateTimeFormat().resolvedOptions().timeZone
                },
                body: formData
            });

            try {
                const errorData = await response.json();
                console.log('Response received:', errorData);
                
                const errorContainer = document.getElementById('promptErrorContainer');
                const errorMessage = document.getElementById('promptErrorMessage');

                if (!response.ok || !errorData.success) {
                    console.log('Error response:', {
                        status: response.status,
                        data: errorData
                    });
                    
                    errorContainer.style.display = 'block';
                    // SafetyValidationError sends 'reason' field
                    // Get error message directly from error field
                    const displayMessage = errorData.user_message || 'An error occurred while processing your request.';
                    
                    console.log('Display message selected:', displayMessage);
                    errorMessage.textContent = displayMessage;
                    processButton.disabled = false;
                    processButton.innerHTML = 'Process';
                    return;
                }

                const data = errorData; // Use the errorData since it contains success/error info

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
            } catch (jsonError) {
                // Handle JSON parsing errors
                console.error("Error parsing JSON response:", jsonError);
                const errorContainer = document.getElementById('promptErrorContainer');
                const errorMessage = document.getElementById('promptErrorMessage');
                errorMessage.textContent = 'An error occurred while processing your request. Please try again.';
                errorContainer.style.display = 'block';
                processButton.disabled = false;
                processButton.innerHTML = 'Process';
            }

        } catch (error) {
            const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
            errorModal.show();
            processButton.disabled = false;
        } finally {
            processingIndicator.style.display = 'none';
            processButton.innerHTML = 'Process';
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
                eventsData = []; // Explicitly clear stored events
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

        const sendButton = chatForm.querySelector('button[type="submit"]');
        const chatInput = document.getElementById('chatInput');

        addUserMessage(message);
        chatInput.value = '';

        // Disable input and button while processing
        chatInput.disabled = true;
        sendButton.disabled = true;
        sendButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Correcting...';

        try {
            showLoading(true);
            const response = await fetch('/correct', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Timezone': Intl.DateTimeFormat().resolvedOptions().timeZone
                },
                body: JSON.stringify({ 
                    correction: message,
                    current_events: eventsData
                })
            });

            const errorData = await response.json();
            if (!response.ok || !errorData.success) {
                const errorMessage = errorData.user_message || 'There was an error. Please try again in a few seconds.';
                addSystemMessage(errorMessage);
                return;
            }

            const data = errorData;
            if (data.success) {
                displayEvents(data.events);
                addSystemMessage('Events have been updated based on your correction.');
            } else {
                addSystemMessage('There was an error. Please try again in a few seconds.');
            }
        } catch (error) {
            console.error('Correction error:', error);
            addSystemMessage('There was an error. Please try again in a few seconds.');
        } finally {
            showLoading(false);
            // Re-enable input and button
            const sendButton = chatForm.querySelector('button[type="submit"]');
            const chatInput = document.getElementById('chatInput');
            chatInput.disabled = false;
            sendButton.disabled = false;
            sendButton.innerHTML = 'Send';
        }
    });


    // Handle ICS download
    downloadButton.addEventListener('click', async function() {
        try {
            showLoading(true);
            const response = await fetch('/download-ics', {
                method: 'POST',
                headers: {
                    'X-Timezone': Intl.DateTimeFormat().resolvedOptions().timeZone
                }
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

    let eventsData = [];

    function displayEvents(events) {
        if (!events) {
            addSystemMessage('Error: No event data received');
            return;
        }
        eventsData = events;
        if (!Array.isArray(events)) {
            // Don't log error objects to console
            addSystemMessage('Error: ' + (events.error || 'Invalid event data received'));
            return;
        }

        eventsDisplay.innerHTML = '<div class="alert alert-warning mb-4">Verify all the information extracted from your image and prompt, especially addresses.</div>';
        events.forEach(event => {
            if (!event || typeof event !== 'object') {
                console.error('Invalid event:', event);
                return;
            }

            const eventElement = document.createElement('div');
            eventElement.className = 'event-card fade-in';
            eventElement.innerHTML = `
                <h3>${event.title || 'Untitled Event'}</h3>
                ${event.description ? `<p>${event.description}</p>` : ''}
                <p><strong>Start:</strong> ${formatDateTime(event.start_time)}</p>
                <p><strong>End:</strong> ${formatDateTime(event.end_time)}</p>
                ${event.location ? `<p><strong>Location:</strong> <a href="${getMapsLink(event.location)}" target="_blank">${event.location}</a></p>` : ''}
            `;
            eventsDisplay.appendChild(eventElement);
        });

        function getMapsLink(location) {
            const isAppleDevice = /iPhone|iPad|iPod|Mac/.test(navigator.userAgent);
            const encodedLocation = encodeURIComponent(location);
            return isAppleDevice ? 
                `maps://?q=${encodedLocation}` : 
                `https://www.google.com/maps/search/?api=1&query=${encodedLocation}`;
        }

        // Ensure the events display is visible
        eventsDisplay.classList.remove('hidden');
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