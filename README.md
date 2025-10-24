# Silo Vault Withdraw

A super quick and dirty vibe-coded script to withdraw assets from Silo vaults on the Sonic blockchain. I created this to quickly withdraw assets from the troubled Main Street vault on Silo to ensure my withdraws went through as soon as Main Street msUSD redemptions were enabled. You can run this script to automate withdrawal attempts from Silo vaults.

Background on Main Street's stablecoin undercollateralization: https://x.com/Main_St_Finance/status/1976972055951147194

<b>IMPORTANT:</b> This script is not audited and should be used at your own risk, it worked for me but I'm not responsible for any losses you may incur.

## Installation

### Prerequisites (if you don't know how to install these, ask Google or ChatGPT):
- Python 3.13 or higher
- `uv` package manager
- git

Clone the repository:
```bash
git clone https://github.com/swang2016/silo-vault-withdraw.git
```

### Navigate to the repository:
```bash
cd silo-vault-withdraw
```

### Install the dependencies and activate the virtual environment:
```bash
uv sync
source .venv/bin/activate
```

## Environment Setup (Optional)

You can set environment variables in a `.env` file to avoid passing private credentials as command-line arguments. To do this, create a `.env` file in the root of the repository and add the following:

```bash
SONIC_RPC=https://rpc.soniclabs.com #optional, defaults to https://rpc.soniclabs.com in the script
EOA_ADDRESS=0xYourAddressHere
PRIVATE_KEY=0xYourPrivateKeyHere
```

The script will load these automatically if they exist. You can also pass the credentials as command-line arguments.

## Usage

Assuming you have the `.env` file set up, you can run the script with:
```bash
python main.py --vault <VAULT_ADDRESS>
```

See Examples section below for more usage examples.

### Key Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--vault` | ✅ Yes | N/A | Vault contract address (ERC-4626 compatible) |
| `--rpc` | No | `https://rpc.soniclabs.com` | RPC endpoint URL for Sonic network (or via `SONIC_RPC` env var) |
| `--owner` | No | From `EOA_ADDRESS` env var | Your EOA address (account that owns vault shares) |
| `--private-key` | No | From `PRIVATE_KEY` env var | Your private key in hex format (0x prefixed, or via `PRIVATE_KEY` env var) |
| `--rounds` | No | `1` | Number of times to execute the withdrawal |
| `--pause-on-fail` | No | `5` | Seconds to wait before next round if pre-flight check fails |

### Withdrawal Amount (Choose One)

| Argument | Description |
|----------|-------------|
| `--assets <AMOUNT>` | Specific number of assets to withdraw (in base units) |
| `--all` | Withdraw your total deposited amount |

### Optional Arguments

| Argument | Description |
|----------|-------------|
| `--receiver` | Address to receive withdrawn assets (defaults to `--owner`) |
| `--abi-file` | Path to custom vault ABI JSON file (uses minimal ERC-4626 ABI by default) |
| `--gas-multiplier` | Multiply estimated gas by this factor (default: `2.0`) |
| `--gas-cap` | Hard cap for gas limit (default: `2,000,000`) |
| `--priority-fee-wei` | Override `maxPriorityFeePerGas` in wei (uses node default if not set) |

## Examples

### Example 1: Withdraw All Assets (Using Environment Variables)

Set up your `.env` file first:
```bash
SONIC_RPC=https://rpc.soniclabs.com
EOA_ADDRESS=0x1234567890123456789012345678901234567890
PRIVATE_KEY=0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd
```

Then run:
```bash
python main.py --vault 0xVaultAddressHere --all
```

### Example 2: Withdraw Specific Amount with All Arguments

```bash
python main.py \
  --vault 0xVaultAddressHere \
  --owner 0x1234567890123456789012345678901234567890 \
  --private-key 0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd \
  --assets 1000000000000000000 \
  --rpc https://rpc.soniclabs.com \
```

### Example 3: Multi-Round Withdrawal with Pause

<b>NOTE:</b> I used this method to withdraw my total deposited amount from the vault in multiple rounds. This will try withdrawing your specified amount (all or some other amount) multiple times with a pause between each try.

Withdraw the maximum 3 times, pausing 10 seconds between rounds if any fails:
```bash
python main.py \
  --vault 0xVaultAddressHere \
  --owner 0x1234567890123456789012345678901234567890 \
  --private-key 0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd \
  --all \
  --rounds 3 \
  --pause-on-fail 10
```

## Support
I vibe coded this in like an hour, I have no intention of supporting it, updating it, or helping you troubleshoot it. Your favorite LLM will probably be very useful.

I'm simply sharing it in case it's useful to someone.

## License

This project is released into the public domain under the [Unlicense](LICENSE).
