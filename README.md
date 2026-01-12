* Setup Ollama
```
Install Ollama: Download it from ollama.com.
export PATH=$PATH:/Applications/Ollama.app/Contents/Resources
/Applications/Ollama.app/Contents/Resources/ollama serve
curl http://localhost:11434 #"Ollama is running"
ollama pull llama3.2:1b
ollama pull llama3.2:3b
```
* Setup uagent
```
pip install uagents
```
* Execute
```
python3.12 camera_agent.py
python3.12 mic_agent.py 

```
* Misc
```
# Move out of the current broken venv
deactivate

# Delete the broken venv folder
rm -rf .venv

# Create a new one using Python 3.12
python3.12 -m venv .venv

# Activate it
source .venv/bin/activate
```