# CMOS Debt Collection Voice Agent

## Project Overview
This is a telephony voice agent for **CMOS** (pronounced "Sea-moss" - like the ocean and the thing that grows on rocks), a debt collection agency.

## Call Flow

### 1. Reference Number Collection
- Ask caller for their reference number at the start
- Use this to look up their account information

### 2. GDPR Verification (2 of 3 required)
Ask verification questions in this order:
1. **Date of birth** (easiest, ask first)
2. **Name** (ask second if needed)
3. **Address** (ask only if still need verification)

**Verification Rules:**
- Need 2 out of 3 correct to pass
- For date of birth: normalize different formats (e.g., "January 5th 1990", "01/05/1990", "5th of Jan 90") and semantically match
- For name: allow close matches (e.g., "Jonathan" vs "John") - inform user we have something similar on record and ask them to try again
- For address: flexible matching

### 3. Account Information Disclosure
Once GDPR verified, read out:
- Account balance
- Client they owe it to
- State: "We need payment of that in full today"

### 4. Payment Response Handling
- **If YES**: "Great, we'll text you the payment details"
- **If NO**: "That's unfortunate, but hopefully we can negotiate more in the future"

## Technical Notes
- Currently using **mocked API** for account lookups
- Keep responses concise and professional
- Use conversational verification (semantic matching, not exact string matching)
- Start simple, will add complexity incrementally

## Voice Configuration
- Cartesia TTS with professional voice
- Slower speaking speed (0.9) for clarity
- Telephony-optimized (16kHz sample rate)
