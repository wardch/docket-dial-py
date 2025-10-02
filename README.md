# Docket Dial - LiveKit Telephony Voice Agents

AI-powered voice agents for phone calls and real-time conversations using LiveKit, OpenAI, Deepgram, and Cartesia.

## Features

- 🎙️ **Real-time voice conversations** with AI
- 📞 **Telephony-optimized** agent for phone calls
- 🗣️ **Speech-to-Text** powered by Deepgram Nova-3
- 🤖 **LLM responses** using OpenAI GPT-4o-mini
- 🔊 **Text-to-Speech** with Cartesia Sonic-2
- 🎯 **Voice Activity Detection** using Silero VAD
- 🔧 **Function tools** for dynamic capabilities

## Agents

### `agent.py`
Simple voice assistant with:
- Class-based Agent architecture
- Turn detection for natural conversations
- Noise cancellation (LiveKit Cloud BVC)
- General purpose web/app use

### `telephony_agent.py`
Phone-optimized agent with:
- Telephony-specific audio settings (16kHz)
- Time-based personalized greetings
- Function tools (current time)
- Named agent for dispatch routing

## Setup

1. **Install dependencies**
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install "livekit-agents[deepgram,openai,cartesia,silero,turn-detector]~=1.0" \
               "livekit-plugins-noise-cancellation~=0.2" \
               "python-dotenv"
   ```

2. **Configure environment variables**

   Create a `.env` file:
   ```env
   LIVEKIT_URL=wss://your-livekit-server.livekit.cloud
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret

   DEEPGRAM_API_KEY=your_deepgram_key
   OPENAI_API_KEY=your_openai_key
   CARTESIA_API_KEY=your_cartesia_key
   ```

## Usage

### Run the simple agent
```bash
python agent.py dev
```

### Run the telephony agent
```bash
python telephony_agent.py start
```

### Development mode with auto-reload
```bash
python telephony_agent.py dev
```

## LiveKit Cloud Setup

1. Create a LiveKit Cloud account at [livekit.io](https://livekit.io)
2. Create a new project and get your credentials
3. Set up a dispatch rule to route calls to `telephony_agent`
4. Configure your SIP trunk for phone integration

## Architecture

```
Phone Call → LiveKit Cloud → Dispatch Rule → telephony_agent
                                ↓
                         Speech Pipeline:
                    VAD → STT → LLM → TTS → Audio Output
```

## Requirements

- Python 3.9+
- LiveKit Cloud account
- API keys for Deepgram, OpenAI, and Cartesia

## License

MIT
