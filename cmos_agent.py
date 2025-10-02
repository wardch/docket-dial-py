import asyncio
import logging
from datetime import datetime
from difflib import SequenceMatcher
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    function_tool
)
from livekit.plugins import deepgram, openai, cartesia, silero

load_dotenv()
logger = logging.getLogger("cmos-agent")

# Global state to store account data for the current call
current_account = None

# Mock API function to look up account by reference number
async def lookup_account(reference_number: str) -> dict:
    """Mock API call to look up account information."""
    # This is a mock response - in production, this would call a real API
    mock_data = {
        "success": True,
        "data": {
            "accountId": "IW1003",
            "referenceNumber": reference_number,
            "debtorName": "John Murphy",
            "dateOfBirth": "1975-11-22",
            "balanceDue": 322.15,
            "client": {
                "id": "a37b560e-fbb4-4458-adbb-77ae7ddf0594",
                "name": "Irish Water"
            },
            "phoneNumber": "+353872223344",
            "notes": "Prefers SMS follow-up",
            "status": "pending",
            "debtorAddress": "89 Elm Row, Galway, H91 XY56"
        }
    }
    logger.info(f"Looking up account for reference: {reference_number}")
    return mock_data

def normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD."""
    date_str = date_str.lower().strip()

    # Common date formats to try
    formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%B %d %Y", "%d %B %Y", "%b %d %Y", "%d %b %Y",
        "%B %d, %Y", "%d %B, %Y", "%b %d, %Y", "%d %b, %Y"
    ]

    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str  # Return original if no match

def name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names (0-1 scale)."""
    return SequenceMatcher(None, name1.lower().strip(), name2.lower().strip()).ratio()

@function_tool
async def verify_reference_number(reference_number: str) -> str:
    """Look up and store account information by reference number. Returns account details if found."""
    global current_account
    result = await lookup_account(reference_number)
    if result["success"]:
        current_account = result["data"]
        return f"Account found. Name on file: {current_account['debtorName']}, DOB: {current_account['dateOfBirth']}"
    return "Account not found"

@function_tool
async def verify_date_of_birth(stated_dob: str) -> str:
    """Verify the caller's date of birth. Returns 'verified' or 'failed'."""
    global current_account
    if not current_account:
        return "Error: No account loaded"

    normalized_dob = normalize_date(stated_dob)
    actual_dob = current_account["dateOfBirth"]

    if normalized_dob == actual_dob:
        return "verified"
    return "failed"

@function_tool
async def verify_name(stated_name: str) -> str:
    """Verify the caller's name. Returns 'verified', 'similar' with actual name, or 'failed'."""
    global current_account
    if not current_account:
        return "Error: No account loaded"

    actual_name = current_account["debtorName"]
    similarity = name_similarity(stated_name, actual_name)

    if similarity >= 0.9:  # Exact or very close match
        return "verified"
    elif similarity >= 0.6:  # Similar but not quite
        return f"similar - we have '{actual_name}' on record"
    return "failed"

@function_tool
async def verify_address(stated_address: str) -> str:
    """Verify the caller's address. Returns 'verified' or 'failed'."""
    global current_account
    if not current_account:
        return "Error: No account loaded"

    actual_address = current_account["debtorAddress"]
    similarity = name_similarity(stated_address, actual_address)

    if similarity >= 0.7:  # Allow some flexibility for address
        return "verified"
    return "failed"

@function_tool
async def get_account_balance() -> str:
    """Get the current account balance and client information."""
    global current_account
    if not current_account:
        return "Error: No account loaded"

    balance = current_account["balanceDue"]
    client = current_account["client"]["name"]
    return f"Balance: €{balance:.2f} owed to {client}"

async def entrypoint(ctx: JobContext):
    """Main entry point for CMOS debt collection telephony agent."""
    await ctx.connect()

    # Wait for participant (caller) to join
    participant = await ctx.wait_for_participant()
    logger.info(f"CMOS call connected from participant: {participant.identity}")

    # Initialize the CMOS debt collection agent
    agent = Agent(
        instructions="""You are a professional debt collection agent for CMOS (pronounced "Sea-moss").

        CALL FLOW:
        1. Ask for their reference number
        2. Verify their identity with GDPR questions (need 2 of 3 correct):
           - Date of birth (ask first, easiest)
           - Name (ask second if needed)
           - Address (ask only if still need verification)
        3. Once verified, read account balance and client they owe
        4. State: "We need payment of that in full today"
        5. Handle response:
           - If YES: "Great, we'll text you the payment details"
           - If NO: "That's unfortunate, but hopefully we can negotiate more in the future"

        VERIFICATION RULES:
        - For dates: Accept any reasonable format (22nd November 1975, 22/11/75, etc.)
        - For names: If close but not exact (e.g., "Jonathan" vs "John"), say "I have something similar on record but not exactly that. Can you try again?"
        - For address: Allow flexibility
        - Need 2 out of 3 to pass

        TONE:
        - Professional but not aggressive
        - Clear and concise for phone calls
        - Speak at moderate pace
        - Be empathetic but firm about payment

        Keep responses under 20 seconds for phone clarity.""",
        tools=[verify_reference_number, verify_date_of_birth, verify_name, verify_address, get_account_balance]
    )

    # Configure the voice processing pipeline optimized for telephony
    session = AgentSession(
        # Voice Activity Detection
        vad=silero.VAD.load(),

        # Speech-to-Text - Deepgram Nova-3
        stt=deepgram.STT(
            model="nova-3",
            language="en-US",
            interim_results=True,
            punctuate=True,
            smart_format=True,
            filler_words=True,
            endpointing_ms=25,
            sample_rate=16000
        ),

        # Large Language Model - GPT-4o-mini
        llm=openai.LLM(
            model="gpt-4o-mini",
            temperature=0.7
        ),

        # Text-to-Speech - Cartesia Sonic-2
        tts=cartesia.TTS(
            model="sonic-2",
            voice="1463a4e1-56a1-4b41-b257-728d56e93605",  # Professional british male voice
            language="en",
            speed=0.9,
            sample_rate=24000
        )
    )

    # Start the agent session
    await session.start(agent=agent, room=ctx.room)

    # Initial greeting
    await session.generate_reply(
        instructions="""Say: 'Hello, you're through to CMOS. For security purposes, can I take your reference number please?'
        Speak professionally and clearly at a moderate pace."""
    )

if __name__ == "__main__":
    # Configure logging for better debugging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run the agent with the name that matches your dispatch rule
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="cmos_agent"
    ))
