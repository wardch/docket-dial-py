#!/usr/bin/env python3
"""
Test script for Stripe payment integration.

This script tests:
1. Stripe API key is valid
2. Creating a PaymentIntent with minimum amount
3. Retrieving payment status

Run with: python test_stripe_payment.py
"""

import os
import sys
from dotenv import load_dotenv
import stripe

# Load environment variables
load_dotenv()

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def test_stripe_connection():
    """Test 1: Verify Stripe API key is valid"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}TEST 1: Verifying Stripe API Key{Colors.RESET}")

    stripe_key = os.getenv("STRIPE_SECRET_KEY")

    if not stripe_key:
        print(f"{Colors.RED}❌ FAILED: STRIPE_SECRET_KEY not found in .env file{Colors.RESET}")
        print(f"{Colors.YELLOW}   Add your Stripe secret key to .env:{Colors.RESET}")
        print(f"{Colors.YELLOW}   STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE{Colors.RESET}")
        return False

    if stripe_key == "sk_test_YOUR_STRIPE_SECRET_KEY_HERE":
        print(f"{Colors.RED}❌ FAILED: You need to replace the placeholder Stripe key{Colors.RESET}")
        print(f"{Colors.YELLOW}   Get your key from: https://dashboard.stripe.com/test/apikeys{Colors.RESET}")
        return False

    stripe.api_key = stripe_key

    try:
        # Try to retrieve account info to verify key works
        account = stripe.Account.retrieve()
        print(f"{Colors.GREEN}✅ PASSED: Stripe API key is valid{Colors.RESET}")
        print(f"{Colors.CYAN}   Account ID: {account.id}{Colors.RESET}")
        print(f"{Colors.CYAN}   Mode: {'TEST' if 'test' in stripe_key else 'LIVE'}{Colors.RESET}")
        return True
    except stripe.error.AuthenticationError as e:
        print(f"{Colors.RED}❌ FAILED: Invalid Stripe API key{Colors.RESET}")
        print(f"{Colors.RED}   Error: {str(e)}{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}❌ FAILED: Unexpected error{Colors.RESET}")
        print(f"{Colors.RED}   Error: {str(e)}{Colors.RESET}")
        return False

def test_minimum_payment():
    """Test 2: Create PaymentIntent with minimum amount (€0.50)"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}TEST 2: Creating PaymentIntent with Minimum Amount{Colors.RESET}")

    try:
        # Create payment intent for €0.50 (50 cents - minimum for EUR)
        amount_euros = 0.50
        amount_cents = int(amount_euros * 100)

        print(f"{Colors.CYAN}   Creating payment for €{amount_euros:.2f} ({amount_cents} cents)...{Colors.RESET}")

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="eur",
            metadata={
                "test": "true",
                "account_id": "TEST_ACCOUNT_001",
                "reference_number": "TEST123"
            },
            description="Test payment for CMOS debt collection"
        )

        print(f"{Colors.GREEN}✅ PASSED: PaymentIntent created successfully{Colors.RESET}")
        print(f"{Colors.CYAN}   PaymentIntent ID: {payment_intent.id}{Colors.RESET}")
        print(f"{Colors.CYAN}   Amount: €{amount_euros:.2f}{Colors.RESET}")
        print(f"{Colors.CYAN}   Status: {payment_intent.status}{Colors.RESET}")
        print(f"{Colors.CYAN}   Currency: {payment_intent.currency.upper()}{Colors.RESET}")

        return payment_intent.id
    except stripe.error.InvalidRequestError as e:
        print(f"{Colors.RED}❌ FAILED: Invalid request{Colors.RESET}")
        print(f"{Colors.RED}   Error: {str(e)}{Colors.RESET}")
        return None
    except Exception as e:
        print(f"{Colors.RED}❌ FAILED: Unexpected error{Colors.RESET}")
        print(f"{Colors.RED}   Error: {str(e)}{Colors.RESET}")
        return None

def test_payment_retrieval(payment_intent_id):
    """Test 3: Retrieve payment status"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}TEST 3: Retrieving Payment Status{Colors.RESET}")

    if not payment_intent_id:
        print(f"{Colors.YELLOW}⚠️  SKIPPED: No payment intent ID from previous test{Colors.RESET}")
        return False

    try:
        print(f"{Colors.CYAN}   Retrieving PaymentIntent {payment_intent_id}...{Colors.RESET}")

        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        print(f"{Colors.GREEN}✅ PASSED: Successfully retrieved payment{Colors.RESET}")
        print(f"{Colors.CYAN}   ID: {payment_intent.id}{Colors.RESET}")
        print(f"{Colors.CYAN}   Status: {payment_intent.status}{Colors.RESET}")
        print(f"{Colors.CYAN}   Amount: €{payment_intent.amount / 100:.2f}{Colors.RESET}")
        print(f"{Colors.CYAN}   Created: {payment_intent.created}{Colors.RESET}")

        return True
    except Exception as e:
        print(f"{Colors.RED}❌ FAILED: Could not retrieve payment{Colors.RESET}")
        print(f"{Colors.RED}   Error: {str(e)}{Colors.RESET}")
        return False

def test_different_amounts():
    """Test 4: Test various payment amounts"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}TEST 4: Testing Various Payment Amounts{Colors.RESET}")

    test_amounts = [0.50, 1.00, 10.00, 100.00, 322.15]  # Last one is the mock balance

    results = []
    for amount in test_amounts:
        try:
            amount_cents = int(amount * 100)
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="eur",
                metadata={"test": "amount_test"},
                description=f"Test payment €{amount:.2f}"
            )
            print(f"{Colors.GREEN}   ✅ €{amount:.2f} - Created: {payment_intent.id}{Colors.RESET}")
            results.append(True)
        except Exception as e:
            print(f"{Colors.RED}   ❌ €{amount:.2f} - Failed: {str(e)}{Colors.RESET}")
            results.append(False)

    if all(results):
        print(f"{Colors.GREEN}✅ PASSED: All amounts tested successfully{Colors.RESET}")
        return True
    else:
        print(f"{Colors.RED}❌ FAILED: Some amounts failed{Colors.RESET}")
        return False

def print_test_card_info():
    """Display Stripe test card numbers"""
    print(f"\n{Colors.MAGENTA}{Colors.BOLD}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.MAGENTA}{Colors.BOLD}STRIPE TEST CARD NUMBERS{Colors.RESET}")
    print(f"{Colors.MAGENTA}{Colors.BOLD}{'=' * 70}{Colors.RESET}")

    print(f"\n{Colors.CYAN}✅ SUCCESS CARDS:{Colors.RESET}")
    print(f"   4242 4242 4242 4242  - Basic success (no authentication)")
    print(f"   5555 5555 5555 4444  - Mastercard success")
    print(f"   3782 822463 10005    - American Express success")

    print(f"\n{Colors.YELLOW}🔐 AUTHENTICATION REQUIRED:{Colors.RESET}")
    print(f"   4000 0025 0000 3155  - Requires 3D Secure authentication")
    print(f"   4000 0027 6000 3184  - Requires 3D Secure 2 authentication")

    print(f"\n{Colors.RED}❌ DECLINE CARDS:{Colors.RESET}")
    print(f"   4000 0000 0000 9995  - Declined (generic)")
    print(f"   4000 0000 0000 0002  - Declined (insufficient funds)")
    print(f"   4000 0000 0000 9987  - Declined (lost card)")
    print(f"   4000 0000 0000 9979  - Declined (stolen card)")

    print(f"\n{Colors.CYAN}💡 NOTES:{Colors.RESET}")
    print(f"   - Use any future expiry date (e.g., 12/34)")
    print(f"   - Use any 3-digit CVC (e.g., 123)")
    print(f"   - Use any postal code (e.g., 12345)")

    print(f"\n{Colors.BLUE}📚 Full documentation:{Colors.RESET}")
    print(f"   https://docs.stripe.com/testing#cards")
    print(f"{Colors.MAGENTA}{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║     STRIPE PAYMENT INTEGRATION TEST SUITE                      ║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════════════════════════════╝{Colors.RESET}\n")

    results = []

    # Test 1: API Key
    results.append(("Stripe API Connection", test_stripe_connection()))

    if not results[0][1]:
        print(f"\n{Colors.RED}{Colors.BOLD}⛔ STOPPING: Fix Stripe API key before continuing{Colors.RESET}\n")
        return

    # Test 2: Minimum Payment
    payment_id = test_minimum_payment()
    results.append(("Minimum Payment Creation", payment_id is not None))

    # Test 3: Payment Retrieval
    results.append(("Payment Retrieval", test_payment_retrieval(payment_id)))

    # Test 4: Different Amounts
    results.append(("Various Payment Amounts", test_different_amounts()))

    # Summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}TEST SUMMARY{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASSED{Colors.RESET}" if result else f"{Colors.RED}❌ FAILED{Colors.RESET}"
        print(f"   {status} - {test_name}")

    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")

    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}\n🎉 ALL TESTS PASSED! Your Stripe integration is working.{Colors.RESET}\n")
        print_test_card_info()
    else:
        print(f"{Colors.RED}{Colors.BOLD}\n⚠️  SOME TESTS FAILED - Check errors above{Colors.RESET}\n")

    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.RESET}\n")

if __name__ == "__main__":
    main()
