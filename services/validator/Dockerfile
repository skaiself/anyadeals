FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

WORKDIR /app

# Install real Chrome (for channel="chrome" — real TLS fingerprint)
RUN apt-get update && apt-get install -y wget gnupg \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p results screenshots

EXPOSE 8002

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]
