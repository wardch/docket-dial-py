import asyncio
import logging
import os
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
from livekit import api, rtc
from livekit.plugins import deepgram, openai, cartesia, silero
import stripe

load_dotenv()

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ANSI color codes for terminal output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

logger = logging.getLogger("cmos-agent")

# Global state to store account data for the current call
current_account = None
gdpr_verified = False
payment_status = None
current_room_name = None
current_participant_identity = None

# Mock API function to look up account by reference number
async def lookup_account(reference_number: str) -> dict:
    """Mock API call to look up account information."""
    # This is a mock response - in production, this would call a real API
    mock_data = {
        "success": True,
        "data": {
            "accountId": "IW1003",
            "referenceNumber": reference_number,
            "debtorName": "Jimmy Flanagan",
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
    logger.info(f"{Colors.CYAN}🔍 Looking up account for reference: {reference_number}{Colors.RESET}")
    return mock_data

def normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD."""
    original_input = date_str
    date_str = date_str.lower().strip()

    logger.info(f"{Colors.MAGENTA}📅 Normalizing date input: '{original_input}'{Colors.RESET}")

    # Handle spoken number formats like "nineteen seventy five eleven twenty two"
    # Convert to "1975 11 22"
    number_words = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19', 'twenty': '20', 'thirty': '30',
        'forty': '40', 'fifty': '50', 'sixty': '60', 'seventy': '70',
        'eighty': '80', 'ninety': '90'
    }

    # Replace word numbers with digits
    converted = date_str
    for word, digit in number_words.items():
        converted = converted.replace(word, digit)

    logger.info(f"{Colors.MAGENTA}   ↳ After word-to-number conversion: '{converted}'{Colors.RESET}")

    # Common date formats to try
    formats = [
        "%Y-%m-%d", "%Y %m %d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%B %d %Y", "%d %B %Y", "%b %d %Y", "%d %b %Y",
        "%B %d, %Y", "%d %B, %Y", "%b %d, %Y", "%d %b, %Y",
        "%d %m %Y", "%Y/%m/%d"
    ]

    for fmt in formats:
        try:
            parsed_date = datetime.strptime(converted, fmt)
            normalized = parsed_date.strftime("%Y-%m-%d")
            logger.info(f"{Colors.MAGENTA}   ✓ Successfully parsed as '{normalized}' using format '{fmt}'{Colors.RESET}")
            return normalized
        except ValueError:
            continue

    logger.warning(f"{Colors.YELLOW}⚠️  Could not parse date: '{original_input}' (converted: '{converted}'){Colors.RESET}")
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

    logger.info(f"{Colors.BLUE}{Colors.BOLD}🎂 DOB VERIFICATION{Colors.RESET}")
    logger.info(f"{Colors.BLUE}   Stated: '{stated_dob}'{Colors.RESET}")
    normalized_dob = normalize_date(stated_dob)
    actual_dob = current_account["dateOfBirth"]

    logger.info(f"{Colors.BLUE}   Comparison: '{normalized_dob}' vs '{actual_dob}'{Colors.RESET}")

    if normalized_dob == actual_dob:
        logger.info(f"{Colors.GREEN}{Colors.BOLD}   ✅ DOB VERIFICATION: PASSED{Colors.RESET}")
        return "verified"

    logger.warning(f"{Colors.RED}{Colors.BOLD}   ❌ DOB VERIFICATION: FAILED{Colors.RESET}")
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
    import re
    global current_account
    if not current_account:
        return "Error: No account loaded"

    actual_address = current_account["debtorAddress"]
    logger.info(f"{Colors.CYAN}{Colors.BOLD}🏠 ADDRESS VERIFICATION{Colors.RESET}")
    logger.info(f"{Colors.CYAN}   Stated: '{stated_address}'{Colors.RESET}")
    logger.info(f"{Colors.CYAN}   On file: '{actual_address}'{Colors.RESET}")

    # Normalize addresses for comparison - remove postcodes and extra punctuation
    def normalize_address(addr: str) -> str:
        # Convert to lowercase and remove common punctuation
        addr = addr.lower().strip()
        # Remove postcodes (common Irish format: H91 XY56 or similar)
        addr = re.sub(r'\b[a-z]\d{2}\s*[a-z0-9]{4}\b', '', addr, flags=re.IGNORECASE)
        # Remove extra punctuation and multiple spaces
        addr = re.sub(r'[,.]', '', addr)
        addr = re.sub(r'\s+', ' ', addr).strip()
        return addr

    normalized_stated = normalize_address(stated_address)
    normalized_actual = normalize_address(actual_address)

    logger.info(f"{Colors.CYAN}   Normalized stated: '{normalized_stated}'{Colors.RESET}")
    logger.info(f"{Colors.CYAN}   Normalized actual: '{normalized_actual}'{Colors.RESET}")

    # Check if the stated address is contained in the actual address or vice versa
    # This handles partial address matches like "89 Elm Row, Galway" vs "89 Elm Row, Galway, H91 XY56"
    if normalized_stated in normalized_actual or normalized_actual in normalized_stated:
        logger.info(f"{Colors.GREEN}{Colors.BOLD}   ✅ ADDRESS VERIFICATION: PASSED (substring match){Colors.RESET}")
        return "verified"

    # Fall back to similarity matching
    similarity = name_similarity(normalized_stated, normalized_actual)
    logger.info(f"{Colors.CYAN}   Similarity score: {similarity:.2f}{Colors.RESET}")

    if similarity >= 0.7:  # Allow some flexibility for address
        logger.info(f"{Colors.GREEN}{Colors.BOLD}   ✅ ADDRESS VERIFICATION: PASSED (similarity match){Colors.RESET}")
        return "verified"

    logger.warning(f"{Colors.RED}{Colors.BOLD}   ❌ ADDRESS VERIFICATION: FAILED (similarity {similarity:.2f} < 0.7){Colors.RESET}")
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

@function_tool
async def initiate_payment(amount_euros: float) -> str:
    """
    Initiate a Stripe payment for the caller.

    This creates a PaymentIntent for the specified amount.
    For Twilio Pay integration, you'll need to:
    1. Enable PCI Mode in Twilio Console
    2. Install Stripe Connector in Twilio Console (Voice > Manage > Pay Connectors)
    3. Connect your Stripe account to Twilio

    Args:
        amount_euros: The amount to charge in euros

    Returns:
        Status message for the agent
    """
    global current_account, payment_status

    if not current_account:
        return "Error: No account loaded"

    try:
        # Convert euros to cents (Stripe uses smallest currency unit)
        amount_cents = int(amount_euros * 100)

        logger.info(f"{Colors.MAGENTA}{Colors.BOLD}💳 CREATING PAYMENT INTENT{Colors.RESET}")
        logger.info(f"{Colors.MAGENTA}   Amount: €{amount_euros:.2f} ({amount_cents} cents){Colors.RESET}")

        # Create a PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="eur",
            metadata={
                "account_id": current_account["accountId"],
                "reference_number": current_account["referenceNumber"],
                "debtor_name": current_account["debtorName"],
                "client": current_account["client"]["name"]
            },
            description=f"Payment for {current_account['client']['name']} - Ref: {current_account['referenceNumber']}"
        )

        payment_status = {
            "payment_intent_id": payment_intent.id,
            "amount": amount_euros,
            "status": "initiated"
        }

        logger.info(f"{Colors.GREEN}{Colors.BOLD}   ✅ PaymentIntent created: {payment_intent.id}{Colors.RESET}")
        logger.info(f"{Colors.GREEN}   Status: {payment_intent.status}{Colors.RESET}")

        return f"payment_initiated - PaymentIntent ID: {payment_intent.id}"

    except stripe.error.StripeError as e:
        logger.error(f"{Colors.RED}{Colors.BOLD}   ❌ STRIPE ERROR: {str(e)}{Colors.RESET}")
        payment_status = {"status": "failed", "error": str(e)}
        return f"payment_failed - {str(e)}"

@function_tool
async def check_payment_status(payment_intent_id: str) -> str:
    """
    Check the status of a payment.

    Args:
        payment_intent_id: The Stripe PaymentIntent ID to check

    Returns:
        Current status of the payment
    """
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        logger.info(f"{Colors.CYAN}🔍 PAYMENT STATUS CHECK{Colors.RESET}")
        logger.info(f"{Colors.CYAN}   PaymentIntent: {payment_intent_id}{Colors.RESET}")
        logger.info(f"{Colors.CYAN}   Status: {payment_intent.status}{Colors.RESET}")

        return f"status: {payment_intent.status}"

    except stripe.error.StripeError as e:
        logger.error(f"{Colors.RED}❌ Error checking payment: {str(e)}{Colors.RESET}")
        return f"error: {str(e)}"

@function_tool
async def transfer_to_person() -> str:
    """
    Transfer the caller to speak with a real person.

    This should be called when the caller requests to speak with a person,
    representative, human, or similar request.

    Returns:
        Status message indicating transfer is in progress
    """
    global current_room_name, current_participant_identity

    logger.info(f"{Colors.MAGENTA}{Colors.BOLD}📞 CALL TRANSFER INITIATED{Colors.RESET}")
    logger.info(f"{Colors.MAGENTA}   Transferring to: +12097638338{Colors.RESET}")

    if not current_room_name or not current_participant_identity:
        logger.error(f"{Colors.RED}❌ Missing room or participant info{Colors.RESET}")
        return "transfer_failed - missing room/participant info"

    try:
        # Transfer to US number (Irish number requires Twilio geo permissions)
        transfer_to_number = "tel:+12097638338"

        logger.info(f"{Colors.CYAN}📋 Transfer Details:{Colors.RESET}")
        logger.info(f"{Colors.CYAN}   Room: {current_room_name}{Colors.RESET}")
        logger.info(f"{Colors.CYAN}   Participant: {current_participant_identity}{Colors.RESET}")
        logger.info(f"{Colors.CYAN}   Transfer To: {transfer_to_number}{Colors.RESET}")

        logger.info(f"{Colors.YELLOW}🔧 Creating TransferSIPParticipantRequest...{Colors.RESET}")
        transfer_request = api.TransferSIPParticipantRequest(
            participant_identity=current_participant_identity,
            room_name=current_room_name,
            transfer_to=transfer_to_number,
            play_dialtone=False
        )
        logger.info(f"{Colors.GREEN}✓ Transfer request created{Colors.RESET}")

        logger.info(f"{Colors.YELLOW}🔧 Initializing LiveKit API client...{Colors.RESET}")
        async with api.LiveKitAPI() as livekit_api:
            logger.info(f"{Colors.YELLOW}⏳ Sending transfer request to LiveKit API...{Colors.RESET}")
            result = await livekit_api.sip.transfer_sip_participant(transfer_request)
            logger.info(f"{Colors.GREEN}{Colors.BOLD}✅ Call transferred successfully{Colors.RESET}")
            logger.info(f"{Colors.GREEN}   API Response: {result}{Colors.RESET}")
            return "transfer_successful"

    except Exception as e:
        logger.error(f"{Colors.RED}{Colors.BOLD}❌ TRANSFER ERROR: {str(e)}{Colors.RESET}")
        logger.error(f"{Colors.RED}   Error type: {type(e).__name__}{Colors.RESET}")
        import traceback
        logger.error(f"{Colors.RED}   Traceback: {traceback.format_exc()}{Colors.RESET}")
        return f"transfer_failed - {str(e)}"

async def entrypoint(ctx: JobContext):
    """Main entry point for CMOS debt collection telephony agent."""
    await ctx.connect()

    # Wait for participant (caller) to join
    participant = await ctx.wait_for_participant()
    logger.info(f"{Colors.GREEN}{Colors.BOLD}📞 CALL CONNECTED - Participant: {participant.identity}{Colors.RESET}")

    # Store room and participant info for potential transfer
    global current_room_name, current_participant_identity
    room_name = ctx.room.name
    participant_identity = participant.identity
    current_room_name = room_name
    current_participant_identity = participant_identity

    # Initialize the CMOS debt collection agent
    agent = Agent(
        instructions="""You are a professional debt collection agent for CMOS (pronounced "Sea-moss").

        IMPORTANT - TRANSFER TO PERSON:
        If at ANY point during the call the caller asks to speak with a person, representative, human, supervisor,
        manager, or makes any similar request, you MUST immediately call the transfer_to_person() tool.
        Say something like "Of course, let me transfer you to someone who can help" and then call the tool.

        CALL FLOW:
        1. Ask for their reference number
        2. Verify their identity with GDPR questions (need 2 of 3 correct):
           - Date of birth (ask first, easiest)
           - Name (ask second if needed)
           - Address (ask only if still need verification)
        3. Once GDPR verified (2 of 3 passed), MUST call get_account_balance() tool and use the EXACT values returned
        4. State the exact balance and client, then say: "We need payment of that in full today"
        5. Handle payment response:
           - If YES to pay now:
             a) Call initiate_payment() tool with the full balance amount
             b) Say: "I'm now going to securely collect your payment information over the phone. You'll be asked to enter your card details using your phone keypad. This is completely secure and PCI compliant."
             c) Inform them: "Please have your card ready. You'll need to enter the card number, expiry date, and security code."
             d) IMPORTANT: After saying this, tell them you're ready to start and that they should follow the prompts
           - If NO: "That's unfortunate, but hopefully we can negotiate more in the future"

        CRITICAL SECURITY RULE - NEVER REVEAL GDPR DATA:
        - NEVER tell the caller what information you have on file
        - NEVER ask confirming questions like "Can you confirm your name is John Murphy?"
        - ALWAYS ask open questions: "What is your date of birth?", "What is the name on the account?", "What is your address?"
        - ONLY after they answer should you say "That's correct" or "That doesn't match what we have"
        - This is a security requirement - you must make them prove they know the information

        VERIFICATION RULES:
        - For dates: Accept any reasonable format (22nd November 1975, 22/11/75, etc.)
        - For names: If close but not exact (e.g., "Jonathan" vs "John"), say "I have something similar on record but not exactly that. Can you try again?"
        - For address: Allow flexibility
        - Need 2 out of 3 to pass

        TONE & SPEECH STYLE:
        - Professional but not aggressive
        - Sound natural and human-like with occasional fillers like "um", "uh", "let me just", "okay so", "right"
        - Use ellipses (...) to create natural pauses for thinking or processing
        - Use brief pauses when looking things up: "Let me just check that... okay"
        - Occasionally use Irish conversational phrases: "Alright", "I see", "Perfect", "there"
        - Add natural hesitations at the start of sentences: "So...", "Right...", "Okay..."
        - Don't sound robotic - vary your phrasing and add slight imperfections
        - Be empathetic but firm about payment
        - Keep responses under 20 seconds for phone clarity

        EXAMPLES OF NATURAL SPEECH WITH PAUSES:
        - "Okay... let me just... pull that up for you there"
        - "Right... so I have your account here"
        - "Uh... just to verify - can you confirm your date of birth for me?"
        - "Perfect... yeah that matches what we have"
        - "I see... okay so... the balance is..."
        - "Right... let me just check that for you... okay"
        - "Right... so just to confirm..."
        - "Um... let me see here..."

        Use these patterns naturally but don't overdo it - stay professional and conversational.""",
        tools=[
            verify_reference_number,
            verify_date_of_birth,
            verify_name,
            verify_address,
            get_account_balance,
            initiate_payment,
            check_payment_status,
            transfer_to_person
        ]
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
            temperature=0.7,
        ),


        # voice="1463a4e1-56a1-4b41-b257-728d56e93605",  # Professional fancy male voice


        # Text-to-Speech - Cartesia Sonic-2
        tts=cartesia.TTS(
            model="sonic-2",
            voice="1463a4e1-56a1-4b41-b257-728d56e93605",  # Professional british male voice
            language="en",
            speed=0.95,
            sample_rate=24000
        )
    )

    # Add event listeners for transcription logging
    @session.on("user_speech_committed")
    def on_user_speech(msg):  # type: ignore
        logger.info(f"{Colors.YELLOW}👤 USER: {msg.message}{Colors.RESET}")

    @session.on("agent_speech_committed")
    def on_agent_speech(msg):  # type: ignore
        logger.info(f"{Colors.GREEN}🤖 AGENT: {msg.message}{Colors.RESET}")

    @session.on("function_call_finished")
    def on_function_call(event):  # type: ignore
        logger.info(f"{Colors.BLUE}🔔 function_call_finished event: {event.function_name}{Colors.RESET}")
        if event.function_name == "transfer_to_person":
            logger.info(f"{Colors.MAGENTA}{Colors.BOLD}🔄 Executing call transfer...{Colors.RESET}")

            async def do_transfer():
                logger.info(f"{Colors.YELLOW}⚙️  Starting do_transfer() function...{Colors.RESET}")
                try:
                    transfer_to_number = "tel:+12097638338"

                    logger.info(f"{Colors.CYAN}📋 Transfer Details:{Colors.RESET}")
                    logger.info(f"{Colors.CYAN}   Room: {room_name}{Colors.RESET}")
                    logger.info(f"{Colors.CYAN}   Participant: {participant_identity}{Colors.RESET}")
                    logger.info(f"{Colors.CYAN}   Transfer To: {transfer_to_number}{Colors.RESET}")

                    logger.info(f"{Colors.YELLOW}🔧 Creating TransferSIPParticipantRequest...{Colors.RESET}")
                    transfer_request = api.TransferSIPParticipantRequest(
                        participant_identity=participant_identity,
                        room_name=room_name,
                        transfer_to=transfer_to_number,
                        play_dialtone=False
                    )
                    logger.info(f"{Colors.GREEN}✓ Transfer request created{Colors.RESET}")

                    # Use context manager for proper API cleanup
                    logger.info(f"{Colors.YELLOW}🔧 Initializing LiveKit API client...{Colors.RESET}")
                    async with api.LiveKitAPI() as livekit_api:
                        logger.info(f"{Colors.YELLOW}⏳ Sending transfer request to LiveKit API...{Colors.RESET}")
                        result = await livekit_api.sip.transfer_sip_participant(transfer_request)
                        logger.info(f"{Colors.GREEN}{Colors.BOLD}✅ Call transferred successfully{Colors.RESET}")
                        logger.info(f"{Colors.GREEN}   API Response: {result}{Colors.RESET}")
                except Exception as e:
                    logger.error(f"{Colors.RED}{Colors.BOLD}❌ TRANSFER ERROR: {str(e)}{Colors.RESET}")
                    logger.error(f"{Colors.RED}   Error type: {type(e).__name__}{Colors.RESET}")
                    import traceback
                    logger.error(f"{Colors.RED}   Traceback: {traceback.format_exc()}{Colors.RESET}")
                finally:
                    logger.info(f"{Colors.YELLOW}🏁 do_transfer() function completed{Colors.RESET}")

            # Get the current event loop and create the task properly
            try:
                loop = asyncio.get_running_loop()
                logger.info(f"{Colors.YELLOW}🔧 Got event loop, creating transfer task...{Colors.RESET}")
                task = loop.create_task(do_transfer())

                def handle_task_result(task):
                    try:
                        task.result()
                    except Exception as e:
                        logger.error(f"{Colors.RED}{Colors.BOLD}❌ TASK ERROR: {str(e)}{Colors.RESET}")

                task.add_done_callback(handle_task_result)
            except Exception as e:
                logger.error(f"{Colors.RED}{Colors.BOLD}❌ Failed to create transfer task: {str(e)}{Colors.RESET}")

    # Start the agent session
    await session.start(agent=agent, room=ctx.room)

    # Initial greeting - more natural with pauses
    greeting = "Hello there, how's it going, my name is Declan... you're through to Sea Moss. Uh... for security purposes, can I just take your reference number there please whenever you're ready?"
    logger.info(f"{Colors.GREEN}🤖 AGENT: {greeting}{Colors.RESET}")
    await session.generate_reply(
        instructions=f"""Say: '{greeting}'
        Use natural pauses (represented by ...) and speak conversationally."""
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
