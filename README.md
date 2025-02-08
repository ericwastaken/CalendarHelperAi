## Chat with a calendar assistant

Ever been handed a tiny reminder card after booking an appointment—at the dentist, a massage therapist, or even a pedicure—only to shove it in your pocket, promising yourself you'll add it to your digital calendar later? (And then... forget? 😅)

This chatbot solves this problem in seconds.

📸 How it works:

1️⃣ Launch the app on your phone, tap Choose File, and TAKE PHOTO of the reminder card.

2️⃣ Give the AI chatbot some quick instructions.

3️⃣ It extracts the appointment details, formats them properly, and shows a preview.

4️⃣ You can refine the results with chat.

5️⃣ When satisfied, download a single calendar file—on most phones, the file will offer to add the appointments directly to your calendar with one tap!

## Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/calendar-helper-ai.git
   ```
2. **Set up environment variables:**
   ```bash
   export OPENAI_API_KEY=your_api_key
   # Generate a random secret key for Flask session security
   # You can use Python to generate one:
   # python -c 'import secrets; print(secrets.token_hex(16))'
   export FLASK_SECRET_KEY=your_random_secret_key
   export DEBUG_LOGGING=false
   ```

   Note: The FLASK_SECRET_KEY should be a random, secure string used to encrypt session data. Never share this key or commit it to version control. You can generate a secure key using Python's secrets module as shown in the comment above.

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```

The application will be available at port 5000.

## API Endpoints

- `GET /`: Main application interface
- `POST /process`: Process image/text and generate events
- `POST /correct`: Apply corrections to existing events
- `POST /download-ics`: Generate and download iCalendar file

## Project Structure

```
├── app.py                 # Flask application setup
├── routes.py             # API endpoints
├── utils/
│   ├── ai_processor.py   # OpenAI integration
│   ├── calendar.py       # iCalendar generation
│   └── location_service.py # Location services
├── static/               # Frontend assets
└── templates/            # HTML templates
```

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

- Images and text are processed temporarily in memory only (with DEBUG_LOGGING=false)
- No data is permanently stored (with DEBUG_LOGGING=false)
- All processing complies with GDPR, CCPA, and LGPD requirements
- See `static/terms.html` for complete terms of service

## License

This project is licensed under the MIT License - see the LICENSE file for details.