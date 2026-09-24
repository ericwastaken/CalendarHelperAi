'use strict';

(() => {
    const screen = document.querySelector('#screen');
    const modal = document.querySelector('#modal');
    const modalContent = document.querySelector('#modal-content');
    const status = document.querySelector('#status');
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    const MAX_FILES = 5;
    const SESSION_MS = 60 * 60 * 1000;
    const config = { maxImageSize: 4 * 1024 * 1024, allowedImageTypes: ['image/jpeg', 'image/jpg', 'image/png', 'image/tiff'] };
    let view = 'upload';
    let busy = false;
    let files = [];
    let details = '';
    let correction = '';
    let events = [];
    let previousEvents = [];
    let messages = [];
    let feedback = null;
    let correctionError = '';
    let exportError = '';
    let expiresAt = null;
    let expiryWarning = false;
    let dialogOpener = null;
    let imageIndex = 0;
    let dialogGeneration = 0;

    const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
    const imageIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="4"/><path d="m4 17 5-5 4 4 3-3 5 5"/><circle cx="15.5" cy="8" r="1.5"/></svg>';
    const intro = (eyebrow, title, body, compact = false) => `<div class="intro ${compact ? 'compact' : ''}"><div class="eyebrow">${eyebrow}</div><h1 tabindex="-1" id="screen-heading">${title}</h1><p>${body}</p></div>`;
    const notice = (title, body, type = 'error', id = '') => `<div class="notice ${type}" ${id ? `id="${id}"` : ''} role="${type === 'error' ? 'alert' : 'status'}"><strong>${escape(title)}</strong>${escape(body)}</div>`;
    const eventCount = () => `${events.length} ${events.length === 1 ? 'event' : 'events'}`;
    const announce = text => { status.textContent = text; };

    function thumbnails(removable = true) {
        return `<div class="files">${files.map(({ file, url }, index) => `<div class="file"><button type="button" class="file-image" data-image="${index}" aria-label="Preview ${escape(file.name)}"><img src="${url}" alt="${escape(file.name)}"></button><div class="file-name"><span title="${escape(file.name)}">${escape(file.name)}</span>${removable ? `<button type="button" class="remove" data-remove="${index}" aria-label="Remove ${escape(file.name)}">Remove</button>` : ''}</div></div>`).join('')}</div>`;
    }

    function uploadView() {
        return intro('Make room for your day', 'From a photo to<br>your calendar.', 'Turn schedules, flyers, and everyday notes into calendar events you can review and keep.') +
            (feedback ? notice(feedback.title, feedback.body, feedback.type, 'input-feedback') : '') +
            `<form id="uploadForm"><input type="file" id="image" name="image" accept="${config.allowedImageTypes.join(',')}" multiple hidden><button type="button" class="upload-zone" id="chooseImages" data-action="choose">${imageIcon}<strong>${files.length ? 'Add another image' : 'Choose images'}</strong><small>Up to 5 images, ${config.maxImageSize / 1024 / 1024} MB each</small><small>JPG, PNG, or TIFF</small></button>${files.length ? `<div class="section-head"><h2>Selected images</h2><span class="badge">${files.length} of 5</span></div>${thumbnails()}` : ''}<div class="field"><label for="text">Details or instructions <span>${files.length ? '(optional)' : ''}</span></label><textarea id="text" name="text" aria-describedby="details-hint${feedback ? ' input-feedback' : ''}" placeholder="Dinner at Oak House on October 8, 6 to 8 pm. Or tell us what to extract from your images.">${escape(details)}</textarea><p class="hint" id="details-hint">You can also start with just text. Include the year when it matters.</p></div><div class="primary-row"><button type="submit" class="primary" id="processButton">Find my events</button><p class="fineprint">You will review everything before exporting.</p></div></form>`;
    }

    function processingView() {
        return intro('Reading your details', 'Let’s find your events.', 'Keep this page open while we turn your details into a calendar draft.', true) +
            `<div class="status-card" role="status" aria-busy="true"><div class="loader" aria-hidden="true"></div><h2>Analyzing your request</h2><p>Busy schedules can take a little longer. We will show your events when they are ready.</p><ul class="status-steps"><li>${files.length ? `${files.length} ${files.length === 1 ? 'image' : 'images'}${details.trim() ? ' and instructions' : ''}` : 'Your event details'}<span>Received</span></li><li>Finding dates and details<span>In progress</span></li></ul></div><div class="primary-row"><button type="button" class="primary" disabled>Finding events...</button></div>`;
    }

    function eventCard(event, index) {
        const start = new Date(event.start_time);
        const end = new Date(event.end_time);
        const dateOptions = { timeZone: timezone, weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' };
        const timeOptions = { timeZone: timezone, hour: 'numeric', minute: '2-digit', timeZoneName: 'short' };
        const date = start.toLocaleDateString(undefined, dateOptions);
        const sameDay = date === end.toLocaleDateString(undefined, dateOptions);
        const time = `${start.toLocaleTimeString(undefined, timeOptions)} to ${sameDay ? '' : `${end.toLocaleDateString(undefined, dateOptions)}, `}${end.toLocaleTimeString(undefined, timeOptions)}`;
        let location = (event.location || [event.location_name, event.location_address].filter(Boolean).join(', ')).trim();
        if (/^(unknown|none|n\/a)[\s,\-]*$/i.test(location)) location = '';
        const changed = previousEvents.length && JSON.stringify(previousEvents[index]) !== JSON.stringify(event);
        return `<article class="event"><div class="date-label">${escape(date)}</div><h3>${escape(event.title || 'Untitled event')}</h3><p class="time">${escape(time)}</p>${location ? `<p class="location"><a href="https://www.google.com/maps/search/?api=1&amp;query=${encodeURIComponent(location)}" target="_blank" rel="noopener noreferrer">${escape(location)}</a></p>` : ''}${event.description ? `<p class="description">${escape(event.description)}</p>` : ''}${changed ? '<span class="badge changed">Updated</span>' : ''}</article>`;
    }

    function reviewView() {
        return intro('Your calendar draft', 'A little more organized.', `We found ${eventCount()}. Give ${events.length === 1 ? 'it' : 'them'} a quick look, then make ${events.length === 1 ? 'it' : 'them'} yours.`, true) +
            `<details class="source"><summary>Your request / ${files.length ? `${files.length} ${files.length === 1 ? 'image' : 'images'}${details.trim() ? ' + instructions' : ''}` : 'text details'}</summary>${details.trim() ? `<p>${escape(details)}</p>` : ''}${files.length ? thumbnails(false) : ''}</details>` +
            notice('A quick check before you export', 'AI can miss a detail. Check dates, times, and especially addresses.', '') +
            `<div class="section-head"><h2>${eventCount()}</h2><p>${escape(timezone)}</p></div><section id="eventsDisplay" aria-label="Your events">${events.map(eventCard).join('')}</section><section class="correction" aria-labelledby="correction-heading"><h2 id="correction-heading">Need to change something?</h2><p>Tell us what to fix. We will update the events above.</p>${messages.length ? `<div class="chat-log" role="log" aria-label="Corrections" tabindex="0">${messages.map(message => `<div class="bubble ${message.role}"><strong>${message.role === 'user' ? 'You' : 'Calendar Helper'}</strong>${escape(message.text)}</div>`).join('')}</div>` : ''}${correctionError ? notice('That correction did not go through.', correctionError, 'error', 'correction-error') : ''}<form id="chatForm"><div class="field"><label for="chatInput">Your correction</label><textarea id="chatInput" ${busy ? 'disabled' : ''} ${correctionError ? 'aria-describedby="correction-error" aria-invalid="true"' : ''} placeholder="Move dinner to 7 pm and keep it two hours long.">${escape(correction)}</textarea></div><button type="submit" class="secondary" ${busy ? 'disabled' : ''}>${busy === 'correcting' ? 'Updating events...' : 'Update events'}</button></form></section><section class="export">${exportError ? notice('We could not prepare your file.', exportError) : ''}<button type="button" class="primary" id="downloadButton" data-action="export" ${busy ? 'disabled' : ''}>${busy === 'exporting' ? 'Preparing calendar...' : 'Download calendar file'}</button><p class="fineprint">An .ics file for Apple, Google, or Outlook Calendar.</p><button type="button" class="text-button reset" data-dialog="reset" ${busy ? 'disabled' : ''}>Start over</button></section>`;
    }

    function exportedView() {
        return intro('Ready for your calendar', 'Your day, in place.', 'Your calendar download has started. Open the file to add these events to your calendar.', true) +
            `<div class="status-card"><div class="complete-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m5 12 4 4 10-10"/></svg></div><div class="download-file"><strong>events.ics</strong><span>${eventCount()} / ${escape(timezone)}</span></div><p>Downloading does not add events automatically.</p></div><ol class="instructions"><li>Find <strong>events.ics</strong> in your downloads.</li><li>Open it with your calendar app, or use its import option.</li><li>Review the destination calendar, then confirm.</li></ol>${exportError ? notice('We could not prepare your file.', exportError) : ''}<button type="button" class="primary" data-action="review" ${busy ? 'disabled' : ''}>Back to my events</button><button type="button" class="text-button reset" data-action="export" ${busy ? 'disabled' : ''}>${busy ? 'Preparing calendar...' : 'Download file again'}</button><button type="button" class="text-button reset" data-dialog="reset" ${busy ? 'disabled' : ''}>Start a new calendar</button>`;
    }

    function render(focus = false) {
        const step = view === 'exported' || busy === 'exporting' ? 3 : view === 'review' ? 2 : 1;
        document.querySelectorAll('[data-step]').forEach(element => {
            const n = Number(element.dataset.step);
            element.className = n === step ? 'active' : n < step ? 'done' : '';
            if (n === step) element.setAttribute('aria-current', 'step');
            else element.removeAttribute('aria-current');
        });
        screen.setAttribute('aria-busy', String(Boolean(busy)));
        screen.innerHTML = '<div id="sessionNotice"></div>' + ({ upload: uploadView, processing: processingView, review: reviewView, exported: exportedView })[view]();
        renderExpiryWarning();
        if (focus) {
            if (modal.open) modal.close();
            document.querySelector('#screen-heading').focus();
            window.scrollTo({ top: 0, behavior: 'instant' });
        }
    }

    function keepWorking() {
        expiresAt = Date.now() + SESSION_MS;
        expiryWarning = false;
        renderExpiryWarning();
    }

    function renderExpiryWarning() {
        const container = document.querySelector('#sessionNotice');
        if (!container) return;
        container.innerHTML = expiryWarning ? '<div class="notice session-notice" role="status"><strong>Your session ends soon.</strong>Download your calendar or keep working to extend it by an hour.<button type="button" class="text-button" data-action="continue">Keep working</button></div>' : '';
    }

    function clearSession(expired = false) {
        files.forEach(({ url }) => URL.revokeObjectURL(url));
        files = []; details = ''; correction = ''; events = []; previousEvents = []; messages = [];
        busy = false; expiresAt = null; expiryWarning = false; correctionError = ''; exportError = '';
        feedback = expired ? { title: 'Your session has ended.', body: 'Add your details again to create a new calendar file.', type: '' } : null;
        view = 'upload';
        if (modal.open) modal.close();
        render(true);
        announce(expired ? 'Your session has ended.' : 'Ready for a new calendar.');
    }

    function addFiles(incoming) {
        const errors = [];
        for (const file of incoming) {
            if (files.some(item => item.file.name === file.name && item.file.size === file.size && item.file.lastModified === file.lastModified)) continue;
            if (files.length >= MAX_FILES) { errors.push('You can add up to 5 images. Remove one before adding another.'); break; }
            if (!config.allowedImageTypes.includes(file.type)) { errors.push(`${file.name}: choose a JPG, PNG, or TIFF image.`); continue; }
            if (file.size > config.maxImageSize) { errors.push(`${file.name} is too large. Choose an image no larger than ${config.maxImageSize / 1024 / 1024} MB.`); continue; }
            files.push({ file, url: URL.createObjectURL(file) });
        }
        feedback = errors.length ? { title: 'Check your images', body: errors.join('\n'), type: 'error' } : null;
        render();
        document.querySelector('#chooseImages').focus();
        announce(`${files.length} ${files.length === 1 ? 'image' : 'images'} selected.`);
    }

    async function request(url, options) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 120000);
        try {
            const response = await fetch(url, { ...options, signal: controller.signal, headers: { 'X-Timezone': timezone, ...options.headers } });
            let data;
            try { data = await response.json(); } catch { throw new Error('The server returned an unreadable response. Your details are still here; please try again.'); }
            if (!response.ok || !data.success) {
                const error = new Error(data.user_message || 'We could not complete that request. Please try again.');
                error.kind = data.error_type;
                throw error;
            }
            return data;
        } catch (error) {
            if (error.name === 'AbortError') throw new Error('This is taking longer than expected. Your details are still here. Try a smaller request.');
            if (error instanceof TypeError) throw new Error('We could not connect. Check your connection, then try again. Your details are still here.');
            throw error;
        } finally { clearTimeout(timer); }
    }

    function validateEvents(data) {
        if (!Array.isArray(data) || !data.length || data.some(event => !event || typeof event !== 'object' || !Number.isFinite(Date.parse(event.start_time)) || !Number.isFinite(Date.parse(event.end_time)))) {
            throw new Error('We could not read the event dates in that response. Please try again with the date and time included.');
        }
        return data;
    }

    async function processRequest() {
        if (busy) return;
        if (!files.length && !details.trim()) {
            feedback = { title: 'Add a little detail first.', body: 'Choose an image, or enter the event name, date, and time.', type: 'error' };
            render(); document.querySelector('#text').focus(); return;
        }
        const body = new FormData();
        files.forEach(({ file }) => body.append('image', file));
        body.append('text', details.trim());
        busy = 'processing'; view = 'processing'; feedback = null;
        render(true); announce('Finding your events.');
        try {
            const data = await request('/process', { method: 'POST', body });
            events = validateEvents(data.events);
            previousEvents = []; messages = []; view = 'review'; keepWorking();
            announce(`${eventCount()} ready to review.`);
        } catch (error) {
            view = 'upload';
            feedback = { title: error.kind === 'no_events' ? 'No events found this time.' : 'We could not find your events.', body: error.message, type: error.kind === 'no_events' ? '' : 'error' };
            announce(feedback.title);
        } finally { busy = false; render(true); }
    }

    async function correctEvents() {
        if (busy) return;
        if (!correction.trim()) {
            correctionError = 'Tell us what you want to change first.';
            render(); document.querySelector('#chatInput').focus(); return;
        }
        busy = 'correcting'; correctionError = ''; exportError = ''; keepWorking();
        messages.push({ role: 'user', text: correction.trim() });
        render(); announce('Applying your correction.');
        try {
            const data = await request('/correct', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ correction: correction.trim(), current_events: events }) });
            const updated = validateEvents(data.events);
            previousEvents = events;
            const changed = JSON.stringify(updated) !== JSON.stringify(events);
            events = updated; correction = '';
            messages.push({ role: 'assistant', text: changed ? 'Your calendar draft has been updated. Review the events above before downloading.' : 'The event details are unchanged. Try a more specific correction if needed.' });
            announce(changed ? 'Your events have been updated.' : 'Your events are unchanged.');
        } catch (error) {
            correctionError = `${error.message} Your previous events have not changed.`;
            messages.push({ role: 'assistant', text: 'That correction did not go through. Your events have not changed.' });
            announce('Correction failed. Your previous events are still here.');
        } finally {
            busy = false; keepWorking(); render();
            document.querySelector('#chatInput').focus({ preventScroll: true });
            const log = document.querySelector('.chat-log');
            if (log) log.scrollTop = log.scrollHeight;
        }
    }

    async function exportEvents() {
        if (busy || !events.length) return;
        busy = 'exporting'; exportError = ''; keepWorking(); render(); announce('Preparing your calendar file.');
        let succeeded = false;
        try {
            const data = await request('/download-ics', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ events }) });
            if (typeof data.ics_content !== 'string' || !data.ics_content.includes('BEGIN:VCALENDAR')) throw new Error('The server did not return a calendar file. Please try again.');
            const url = URL.createObjectURL(new Blob([data.ics_content], { type: 'text/calendar;charset=utf-8' }));
            const link = document.createElement('a');
            link.href = url; link.download = 'events.ics'; document.body.append(link); link.click(); link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 60000);
            view = 'exported'; succeeded = true; announce('Your calendar download has started.');
        } catch (error) { exportError = error.message; announce('Download failed. Your events are still here.'); }
        finally {
            busy = false; keepWorking(); render(succeeded);
            if (!succeeded) document.querySelector('[data-action="export"]').focus({ preventScroll: true });
        }
    }

    function showImage(index) {
        imageIndex = index;
        const item = files[index];
        if (!item) return;
        modalContent.innerHTML = `<h2 id="modal-title">${escape(item.file.name)}</h2><p>Image ${index + 1} of ${files.length}</p><a href="${item.url}" target="_blank" rel="noopener" aria-label="Open full-size ${escape(item.file.name)}"><img class="dialog-image" src="${item.url}" alt="${escape(item.file.name)}"></a><p class="hint">Select the image to open it at full size in a new tab.</p>${files.length > 1 ? `<div class="image-navigation"><button type="button" class="secondary" data-action="previous-image" ${index === 0 ? 'disabled' : ''}>Previous</button><button type="button" class="secondary" data-action="next-image" ${index === files.length - 1 ? 'disabled' : ''}>Next</button></div>` : ''}`;
    }

    async function openDialog(kind, opener, index) {
        dialogOpener = opener;
        const generation = ++dialogGeneration;
        if (kind === 'image') showImage(index);
        else if (kind === 'reset') modalContent.innerHTML = '<h2 id="modal-title">Start a new calendar?</h2><p>This clears the images, details, corrections, and events from this session. Download your calendar first if you want to keep it.</p><button type="button" class="secondary" data-action="close" autofocus>Keep working</button><button type="button" class="danger" data-action="reset">Clear and start over</button>';
        else modalContent.innerHTML = `<h2 id="modal-title">${kind === 'terms' ? 'Terms of Service' : 'One photo. A few plans.'}</h2><div id="dialog-document"><p role="status">Loading...</p></div>`;
        modal.showModal();
        if (kind !== 'terms' && kind !== 'example') return;
        try {
            const response = await fetch(kind === 'terms' ? '/static/terms.html' : '/static/example-images-and-prompts.html');
            if (!response.ok) throw new Error('unavailable');
            const html = await response.text();
            if (generation !== dialogGeneration || !modal.open) return;
            const parsed = new DOMParser().parseFromString(html, 'text/html');
            const target = document.querySelector('#dialog-document');
            // Only application-owned static documents are loaded here, never AI or user content.
            target.replaceChildren(...Array.from(parsed.body.childNodes));
        } catch {
            if (generation === dialogGeneration && modal.open) document.querySelector('#dialog-document').innerHTML = '<p role="alert">We could not load this page. Close this dialog and try again.</p>';
        }
    }

    document.addEventListener('input', event => {
        if (event.target.id === 'text') details = event.target.value;
        if (event.target.id === 'chatInput') { correction = event.target.value; keepWorking(); }
    });
    document.addEventListener('change', event => {
        if (event.target.id === 'image' && !busy) addFiles(Array.from(event.target.files));
    });
    document.addEventListener('submit', event => {
        if (event.target.id === 'uploadForm') { event.preventDefault(); processRequest(); }
        if (event.target.id === 'chatForm') { event.preventDefault(); correctEvents(); }
    });
    document.addEventListener('click', event => {
        const trigger = event.target.closest('[data-action], [data-dialog], [data-image], [data-remove]');
        if (!trigger || trigger.disabled) return;
        if (trigger.dataset.dialog) return openDialog(trigger.dataset.dialog, trigger);
        if (trigger.dataset.image !== undefined) return openDialog('image', trigger, Number(trigger.dataset.image));
        if (trigger.dataset.remove !== undefined && !busy) {
            const index = Number(trigger.dataset.remove);
            URL.revokeObjectURL(files[index].url); files.splice(index, 1); feedback = null; render();
            const next = document.querySelector(`[data-remove="${Math.min(index, files.length - 1)}"]`) || document.querySelector('#chooseImages');
            next.focus(); announce(`${files.length} images selected.`); return;
        }
        switch (trigger.dataset.action) {
            case 'choose': document.querySelector('#image').click(); break;
            case 'export': exportEvents(); break;
            case 'review': view = 'review'; keepWorking(); render(true); break;
            case 'reset': if (!busy) clearSession(); break;
            case 'continue': keepWorking(); announce('Your session has been extended by one hour.'); break;
            case 'close': modal.close(); break;
            case 'previous-image': showImage(imageIndex - 1); break;
            case 'next-image': showImage(imageIndex + 1); break;
        }
    });
    document.querySelector('#close-modal').addEventListener('click', () => modal.close());
    modal.addEventListener('close', () => { ++dialogGeneration; if (dialogOpener?.isConnected) dialogOpener.focus(); });
    modal.addEventListener('click', event => {
        const rect = modal.getBoundingClientRect();
        if (event.target === modal && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) modal.close();
    });
    setInterval(() => {
        if (!expiresAt || busy) return;
        const remaining = expiresAt - Date.now();
        if (remaining <= 0) clearSession(true);
        else if (remaining <= 5 * 60 * 1000 && !expiryWarning) { expiryWarning = true; renderExpiryWarning(); }
    }, 30000);
    render();
    fetch('/api/config').then(response => response.ok ? response.json() : Promise.reject()).then(data => {
        if (Number.isFinite(data.maxImageSize) && data.maxImageSize > 0) config.maxImageSize = data.maxImageSize;
        if (Array.isArray(data.allowedImageTypes) && data.allowedImageTypes.every(type => /^image\/[a-z]+$/.test(type))) config.allowedImageTypes = data.allowedImageTypes;
        // The default limits match the service, so a config failure never blocks input.
    }).catch(() => {});
})();
