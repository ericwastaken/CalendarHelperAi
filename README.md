## Chat with a calendar assistant

Ever been handed multiple reminder cards after booking appointments—at the dentist, a massage therapist, or even a pedicure—only to shove them in your pocket, promising yourself you'll add them to your digital calendar later? (And then... forget? 😅)

This chatbot solves this problem in seconds.

📸 How it works:

1️⃣ Launch the app on your phone (or computer), tap Choose File, and upload one or more photos of your reminder cards (up to 5 images at once).

2️⃣ Give the AI chatbot some quick instructions.

3️⃣ It extracts the appointment details, formats them properly, and shows a preview.

4️⃣ You can refine the results with chat, claryfying dates and times, adding or correcting a location, etc. Chat for as long as you want until the calendar items are exactly how you want them!

5️⃣ When satisfied, download a single calendar file. On phones, most phones will offer to add the appointments directly to your calendar with one tap! On computers, you will download the file then double click to open and process into your calendar.

## Hosting

This app is hosted on [DigitalOcean](https://www.digitalocean.com/). Development happens locally on `DEV`, with production releases from `main`.

Check out a LIVE VERSION at [CalendarHelperAI.com](https://calendarhelperai.com).

## Getting Started

For DigitalOcean App Platform, see [DEPLOYMENT.md](DEPLOYMENT.md). The deployment configuration is in `.do/app.yaml`, with Python 3.11 selected by `.python-version` and Gunicorn startup defined in `Procfile`.

The [production app](https://calendarhelperai.com) is hosted on DigitalOcean. Local development uses `DEV`; reviewed releases go to `main`. See [deployment instructions](DEPLOYMENT.md) for generic setup and validation. Account-specific operations and deployment history are maintained privately.

The approved UI design is documented in [docs/design-system/paper-pine-2026-09/DESIGN_SYSTEM.md](docs/design-system/paper-pine-2026-09/DESIGN_SYSTEM.md), with an interactive [design preview](docs/design-system/paper-pine-2026-09/preview.html). It keeps the application at a 460px maximum width on desktop and adapts to smaller mobile screens. The implementation is being tested locally on DEV; production releases are separate. See [design system history](docs/design-system/README.md).

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ericwastaken/CalendarHelperAi.git
   ```
2. **Set up environment variables:**
   Create a `.env` file with the following variables:
   ```bash
   OPENAI_API_KEY=your_api_key
   FLASK_SECRET_KEY=your_random_secret_key
   DEBUG_LOGGING=false
   DEBUG_LOG_IMAGE=false
   OPENAI_HTTP_CLIENT_LEVEL=ERROR
   OPENAI_API_LEVEL=ERROR
   ```

   Note: FLASK_SECRET_KEY signs Flask session cookies. Appointment results and uploads are held in the browser during the current page session; there is no server-side appointment database. You can generate a secure key using:
   ```bash
   python -c 'import secrets; print(secrets.token_hex(16))'
   ```

   Also, in development environments, you can enable logs to see much more information both in the server log as well as the browser logs.

4. **Install dependencies:**
   ```bash
   python -m pip install -e .
   ```

5. **Run the application:**
   ```bash
   python -m flask --app main run --host 0.0.0.0 --port 5055 --no-debugger --no-reload
   ```

The application listens on all IPv4 interfaces at port 5055. On this computer, open http://127.0.0.1:5055; from another device, use this computer's LAN or Tailscale IPv4 address with port 5055. The debugger and reloader stay disabled for network testing. Use `DEV` for local work. Keep credentials in your ignored `.env` or process environment; never put them in this repository. Processing synthetic test requests still uses your OpenAI API account.

## Example images

The [sample image guide](docs/example_images/README.md) includes two realistic, AI-generated photos with fictional events for manual upload testing. The app's Example dialog uses the event-card photo served from `static/images/example-event-cards-2026-09.png`.

## Project Structure

```
├── app.py                # Flask application setup
├── routes.py             # API endpoints
├── utils/
│   ├── ai_processor.py   # OpenAI integration
│   ├── calendar.py       # iCalendar generation
│   └── location_service.py # Location services
├── static/               # Frontend assets
├── docs/design-system/   # Versioned design systems and implementation notes
├── docs/example_images/  # Calendar sample photos and usage guide
└── templates/            # HTML templates
```

## API Endpoints

- `GET /`: Main application interface
- `GET /api/config`: Get application configuration (version, max image size, allowed image types, debug settings)
- `POST /process`: Process image/text and generate events
- `POST /correct`: Apply corrections to existing events
- `POST /download-ics`: Generate and download iCalendar file

The `/api/config` endpoint is called automatically when the application loads to configure client-side validation and debugging. It returns:
- Maximum allowed image size
- List of allowed image types (jpg, png, etc.)
- Application version
- Debug logging settings

The `utils/config.py` file is central to the operation of the application as it houses constants that are accessed by the `/api/config` endpoint. These constants include settings that affect how the application runs, such as version numbers, maximum image sizes, accepted image formats, among other configuration details. By consolidating these constants in a single file, the application can maintain clarity and make updates to configuration settings straightforward.

### Backend Implementation

The backend implementation is primarily responsible for handling requests from the frontend and leveraging OpenAI's capabilities to process images, text, and facilitate interactive chat sessions for event correction. When the frontend submits data, typically an image and initial text, the backend receives these through defined API endpoints.

Upon receiving an image, the backend employs OpenAI to extract appointment details by interpreting the visual and textual data. These extracted details are then previewed for the user in the chat interface on the frontend, enabling them to see the AI's interpretation.

One of the core features of the backend is to initiate and manage chat sessions that allow users to make corrections or add details through conversation. This part of the system also utilizes OpenAI, enabling dynamic interaction where users can refine the extracted events based on feedback and further input. Additionally, locations are processed using OpenAI to ensure accurate venue details are attached to events.

All OpenAI prompts used across these functionalities are maintained separately, as explained in the Prompts section. This separation ensures that the AI interactions are structured, contextual, and adaptable to the application's flow. By keeping prompts separate, the application can flexibly adapt queries and responses to align with user inputs and contextual nuances.

### Prompts

Prompts are maintained within the `utils/prompts.py` file. This file contains declarations for all the prompts in a format that is suitable for processing by the AI model. These prompts are static but contain dynamic elements that are injected based on user input and other contextual data gathered during the app's execution (for example, the user's location based on their IP address, the current date, etc.)

Once a prompt is constructed, it is sent through API calls to the OpenAI service where it undergoes processing. The processed output is then returned to the application, where it is used to extract information or make corrections as part of the application's flow. This dynamic prompt handling enables the AI feature to respond intelligently to user interactions, providing relevant and accurate results.

## Frontend Implementation

The frontend uses vanilla JavaScript, local CSS, system fonts, and native dialogs. The Paper + Pine design constrains the desktop app to 460px and adapts to narrow mobile screens. No third-party UI scripts or fonts are required. The main workflow consists of:

1. **Initial Load**:
   - Fetches configuration from `/api/config`
   - Sets up event listeners for file upload and chat
   - Initializes UI components

2. **User Interaction Flow**:
   - Upload Section: Handles image uploads and initial text input
   - Processing Display: Shows loading states during API calls
   - Results Display: Renders extracted events in cards
   - Chat Interface: Enables real-time corrections through conversation
   - Calendar Download: Generates and downloads .ics files

3. **Key Features**:
   - Real-time image preview
   - Interactive chat for corrections
   - Dynamic event card updates
   - Mobile-responsive design
   - Client-side validation for uploads

The UI maintains state in memory during the session and clears one hour after the latest successful processing or session extension. Corrections and exports extend the session, and a warning appears in the final five minutes with a Keep working action. Manual reset requires confirmation when reviewing results.

## Contributing

1. Fork this project
2. Create your feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request with a clear description of your changes

### Contribution Guidelines

- Follow the existing code style
- Add comments for complex logic
- Update documentation as needed
- Include tests for new features

## Privacy & Security

- Images are processed temporarily in memory only (with DEBUG_LOGGING=false and DEBUG_LOG_IMAGE=false)
- Text is processed temporarily in memory only (with DEBUG_LOGGING=false)
- No data is permanently stored (with DEBUG_LOGGING=false)
- No server-side session data is used or stored ever, even with logging enabled.
- Debug logs can be enabled for development (see the environment variables)
- All processing complies with GDPR, CCPA, and LGPD requirements
- See `static/terms.html` for complete terms of service

## License

This project is licensed under the MIT License - see the LICENSE file for details.
