#!/usr/bin/env python3
import argparse
import json
import os
import time
from decimal import Decimal
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

# Minimal ERC-4626 ABI covering functions used by this script
MIN_ERC4626_ABI = [
    {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}], "name": "maxWithdraw", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "assets", "type": "uint256"}, {"internalType": "address", "name": "receiver", "type": "address"}, {"internalType": "address", "name": "owner", "type": "address"}], "name": "withdraw", "outputs": [{"internalType": "uint256", "name": "shares", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"}
]

DEFAULT_RPC = os.getenv("SONIC_RPC", "https://rpc.soniclabs.com")  # mainnet
CHAIN_ID = 146  # Sonic mainnet

def get_args():
    p = argparse.ArgumentParser(description="Withdraw assets from a Sonic ERC-4626 vault")
    p.add_argument("--rpc", default=DEFAULT_RPC, help="RPC URL (default: %(default)s)")
    p.add_argument("--vault", required=True, help="Vault contract address")
    p.add_argument("--owner", default=os.getenv("EOA_ADDRESS"), help="Your EOA address (owner)")
    p.add_argument("--private-key", default=os.getenv("PRIVATE_KEY"), help="Your private key (hex, 0x...)")
    p.add_argument("--abi-file", help="Path to ABI JSON for the vault (defaults to minimal ERC-4626 ABI)")
    amt = p.add_mutually_exclusive_group(required=True)
    amt.add_argument("--assets", type=int, help="Assets to withdraw (underlying base units)")
    amt.add_argument("--all", action="store_true", help="Withdraw max available")
    p.add_argument("--receiver", help="Receiver address (defaults to --owner)")
    p.add_argument("--gas-multiplier", type=Decimal, default=Decimal("2.0"),
                   help="Multiply estimated gas by this factor (default: 2.0)")
    p.add_argument("--gas-cap", type=int, default=2_000_000, help="Hard cap for gas limit (default: 2,000,000)")
    p.add_argument("--priority-fee-wei", type=int, default=None,
                   help="Override maxPriorityFeePerGas (wei). Default: fetch from node / 1 wei on Sonic")
    p.add_argument("--rounds", type=int, default=1, help="Number of times to run the withdrawal (default: 1)")
    p.add_argument("--pause-on-fail", type=int, default=5, 
                   help="Seconds to pause before next round if pre-flight check fails (default: 5)")
    return p.parse_args()

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    args = get_args()
    if not args.owner:
        raise SystemExit("Missing --owner (or EOA_ADDRESS env)")
    if not args.private_key:
        raise SystemExit("Missing --private-key (or PRIVATE_KEY env)")

    w3 = Web3(Web3.HTTPProvider(args.rpc))
    if not w3.is_connected():
        raise SystemExit(f"Cannot connect to RPC: {args.rpc}")

    acct = Account.from_key(args.private_key)
    if acct.address.lower() != Web3.to_checksum_address(args.owner).lower():
        print(f"Warning: --owner ({args.owner}) does not match private key address ({acct.address})")

    # Load ABI
    if args.abi_file:
        try:
            with open(args.abi_file, "r") as f:
                loaded_abi = json.load(f)
            if isinstance(loaded_abi, list):
                abi = list(loaded_abi) + list(MIN_ERC4626_ABI)
            else:
                abi = MIN_ERC4626_ABI
        except Exception as e:
            print(f"Warning: Failed to read --abi-file: {e}. Using minimal ERC-4626 ABI.")
            abi = MIN_ERC4626_ABI
    else:
        abi = MIN_ERC4626_ABI

    vault = w3.eth.contract(address=Web3.to_checksum_address(args.vault), abi=abi)
    owner = Web3.to_checksum_address(args.owner)
    receiver = Web3.to_checksum_address(args.receiver or args.owner)

    print(f"Vault: {args.vault}")
    print(f"Owner: {owner}")
    print(f"Receiver: {receiver}")
    print(f"Rounds to execute: {args.rounds}\n")

    # Track successful transactions
    successful_txs = 0

    # Run withdrawal for the specified number of rounds
    for round_num in range(1, args.rounds + 1):
        if args.rounds > 1:
            print(f"\n{'='*60}")
            print(f"ROUND {round_num} of {args.rounds}")
            print(f"{'='*60}")

        # Determine amount to withdraw
        if args.all:
            assets = vault.functions.maxWithdraw(owner).call()
            print(f"Withdrawing max: {assets} assets")
        else:
            assets = args.assets
            if assets is None or assets <= 0:
                raise SystemExit("--assets must be a positive integer of underlying base units")
            print(f"Withdrawing: {assets} assets")

        # --- EIP-1559 fee selection for Sonic ---
        latest = w3.eth.get_block('latest')
        base_fee = latest.get('baseFeePerGas', None)

        if args.priority_fee_wei is not None:
            priority_fee = args.priority_fee_wei
        else:
            try:
                priority_fee = int(w3.eth.max_priority_fee)
            except Exception:
                priority_fee = 1  # sensible Sonic default

        if base_fee is None:
            gas_price = int(w3.eth.gas_price)
            fee_kwargs = {"gasPrice": gas_price}
            print(f"Using legacy gasPrice: {gas_price}")
        else:
            max_fee = int(2 * base_fee + priority_fee)
            fee_kwargs = {
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": int(priority_fee),
            }
            print(f"EIP-1559 fees -> baseFee: {base_fee}, priority: {priority_fee}, maxFee: {max_fee}")

        # Build tx skeleton (without gas) - get fresh nonce for each round
        tx_skeleton = {
            "from": owner,
            "nonce": w3.eth.get_transaction_count(owner),
            "chainId": CHAIN_ID,
            **fee_kwargs,
        }

        # Pre-flight check: simulate the transaction to detect reverts before sending
        print("\nRunning pre-flight check...")
        try:
            vault.functions.withdraw(assets, receiver, owner).call({"from": owner})
            print("✓ Pre-flight check passed - transaction should succeed")
        except Exception as e:
            print("✗ Pre-flight check FAILED - transaction would revert!")
            print(f"Revert reason: {e}")
            print("Skipping this transaction.")
            if round_num < args.rounds:
                print(f"Pausing for {args.pause_on_fail} seconds before next round...\n")
                time.sleep(args.pause_on_fail)
            continue

        # Estimate gas, then oversize (with cap)
        try:
            est = vault.functions.withdraw(assets, receiver, owner).estimate_gas(tx_skeleton)
        except Exception as e:
            print("estimate_gas failed; defaulting to conservative limit. Error:", e)
            est = 700_000  # fallback

        gas_limit = min(int(Decimal(est) * args.gas_multiplier), args.gas_cap)
        tx = vault.functions.withdraw(assets, receiver, owner).build_transaction({
            **tx_skeleton,
            "gas": gas_limit,
        })

        # Sign & send
        signed = w3.eth.account.sign_transaction(tx, private_key=args.private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print("Submitted tx:", tx_hash.hex())
        print("View on SonicScan:", f"https://sonicscan.org/tx/{tx_hash.hex()}")

        # Wait for transaction receipt
        print("\nWaiting for transaction to be mined...")
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                print("✅ Transaction successful!")
                print(f"Gas used: {receipt['gasUsed']}")
                successful_txs += 1
            else:
                print("❌ Transaction REVERTED!")
                print(f"Gas used: {receipt['gasUsed']}")
                
                # Try to get revert reason
                try:
                    w3.eth.call(tx, block_identifier=receipt['blockNumber'])
                except Exception as e:
                    revert_reason = str(e)
                    print(f"Revert reason: {revert_reason}")
                    
        except Exception as e:
            print(f"Error waiting for transaction: {e}")

    # Print summary
    print("\n--- Withdrawal Summary ---")
    print(f"Total Rounds: {args.rounds}")
    print(f"Successful Transactions: {successful_txs}")
    print(f"Failed Transactions: {args.rounds - successful_txs}")
    print("----------------------------")

if __name__ == "__main__":
    main()
