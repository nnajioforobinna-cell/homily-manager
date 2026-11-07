#!/bin/bash
# Homily Manager - double-click this file to start the app.
# It sets things up the first time, starts the app, and opens it in your browser.

cd "$(dirname "$0")" || exit 1

# Make this launcher double-clickable from now on (the first run may be started
# from Terminal or a coding assistant; after that, double-clicking works).
chmod +x "$0" 2>/dev/null
xattr -d com.apple.quarantine "$0" 2>/dev/null

echo "Starting Homily Manager..."
echo

# Keep a private Python setup inside this folder, so nothing else on your mac
# is touched. This first-time step happens only once.
if [ ! -d ".venv" ]; then
  echo "Setting up for the first time (this happens only once, please wait)..."
  python3 -m venv .venv || {
    echo
    echo "Could not set up Python. Please make sure Python 3 is installed."
    read -n 1 -s -r -p "Press any key to close this window."
    exit 1
  }
fi

source .venv/bin/activate
pip install --quiet --upgrade pip >/dev/null 2>&1
pip install --quiet -r requirements.txt || {
  echo
  echo "Could not install what the app needs. Please check your internet connection."
  read -n 1 -s -r -p "Press any key to close this window."
  exit 1
}

echo "Opening Homily Manager in your browser..."
( sleep 3; open "http://127.0.0.1:5050" ) &

echo
echo "The app is now running."
echo "Keep this window open while you use it."
echo "To stop the app, close this window or press Control-C."
echo
python3 server.py
