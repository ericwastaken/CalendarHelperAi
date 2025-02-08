git clone https://github.com/yourusername/calendar-helper-ai.git
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables:
   ```bash
   export OPENAI_API_KEY=your_api_key
   export FLASK_SECRET_KEY=your_secret_key
   ```

2. Run the application:
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
├── app.py                 # Flask app initialization
├── routes.py             # API endpoints
├── utils/
│   ├── ai_processor.py   # OpenAI integration
│   ├── calendar.py       # iCalendar generation
│   └── location_service.py # Location services
├── static/               # Frontend assets
└── templates/            # HTML templates
```

## Contributing

1. Fork the project on Replit
2. Create a new branch for your feature
3. Make your changes
4. Test thoroughly
5. Submit a pull request with a clear description of your changes

### Contribution Guidelines

- Follow the existing code style
- Add comments for complex logic
- Update documentation as needed
- Include tests for new features

## Privacy & Data Handling

- Images and text are processed temporarily in memory only
- No data is permanently stored
- All processing complies with GDPR, CCPA, and LGPD requirements
- See `static/terms.html` for complete terms of service

## License

This project is licensed under the MIT License:

```
MIT License

Copyright (c) 2024 Calendar Helper AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.