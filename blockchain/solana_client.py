"""
blockchain/solana_client.py

Python wrapper around the deployed face_verification_registry Anchor program
on Solana devnet. Equivalent role to the old web3.py-based contract.py, but
adapted to Solana's account model: each record lives at its own on-chain
address (a PDA derived from the submitter's wallet + content_hash), rather
than an auto-incrementing integer ID like Ethereum's mapping-based storage.

IMPORTANT INTERFACE CHANGE vs the Polygon version: store_record() now returns
"record_address" (a string) instead of "record_id" (an int) — this needs to
be flagged to Person C, since their main.py will receive this address and
pass it into get_record() instead of an integer.
"""

import os
import json
import asyncio

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import ID as SYS_PROGRAM_ID
from solana.rpc.async_api import AsyncClient
from anchorpy import Program, Provider, Wallet, Context, Idl
from dotenv import load_dotenv

load_dotenv()

SCORE_SCALE = 1000


def _load_wallet(keypair_path: str) -> Keypair:
    with open(keypair_path) as f:
        secret = json.load(f)
    return Keypair.from_bytes(bytes(secret))


def _derive_record_pda(program_id: Pubkey, submitter: Pubkey, content_hash: str) -> Pubkey:
    """Must exactly match the seeds used in the Rust program's #[account(seeds=...)]."""
    seeds = [b"record", bytes(submitter), content_hash.encode("utf-8")]
    pda, _bump = Pubkey.find_program_address(seeds, program_id)
    return pda


async def _get_program() -> Program:
    rpc_url = os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com")
    wallet_path = os.environ["SOLANA_WALLET_PATH"]
    program_id = Pubkey.from_string(os.environ["PROGRAM_ID"])

    client = AsyncClient(rpc_url)
    keypair = _load_wallet(wallet_path)
    provider = Provider(client, Wallet(keypair))

    idl_path = os.environ.get(
        "IDL_PATH",
        "/home/yog/face_verification_registry/target/idl/face_verification_registry.json",
    )
    with open(idl_path) as f:
        raw_idl = f.read()
    idl = Idl.from_json(raw_idl)
    program = Program(idl, program_id, provider)
    return program


async def store_record_async(content_hash: str, post_url: str, similarity_score: float) -> dict:
    program = await _get_program()
    try:
        score_int = int(round(similarity_score * SCORE_SCALE))
        submitter = program.provider.wallet.public_key
        record_pda = _derive_record_pda(program.program_id, submitter, content_hash)

        tx_sig = await program.rpc["store_record"](
            content_hash,
            post_url,
            score_int,
            ctx=Context(
                accounts={
                    "record": record_pda,
                    "submitter": submitter,
                    "system_program": SYS_PROGRAM_ID,
                },
            ),
        )

        # Wait for FINALIZED (not just confirmed) commitment — needed for
        # reliable visibility, especially important now that we've also
        # switched off the shared public RPC to a dedicated Alchemy one.
        await program.provider.connection.confirm_transaction(tx_sig, commitment="finalized")

        return {
            "record_address": str(record_pda),
            "tx_hash": str(tx_sig),
        }
    finally:
        await program.close()


async def get_record_async(record_address: str, max_retries: int = 10) -> dict:
    program = await _get_program()
    try:
        address = Pubkey.from_string(record_address)
        last_error = None
        for attempt in range(max_retries):
            try:
                account = await program.account["Record"].fetch(address, commitment="finalized")
                return {
                    "content_hash": account.content_hash,
                    "post_url": account.post_url,
                    "similarity_score": account.similarity_score / SCORE_SCALE,
                    "timestamp": account.timestamp,
                    "submitter": str(account.submitter),
                }
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
        raise ValueError(
            f"No on-chain record found at address={record_address}: {last_error}"
        ) from last_error
    finally:
        await program.close()


def store_record(content_hash: str, post_url: str, similarity_score: float) -> dict:
    return asyncio.run(store_record_async(content_hash, post_url, similarity_score))


def get_record(record_address: str) -> dict:
    return asyncio.run(get_record_async(record_address))


def verify_on_chain(record_address: str, expected_content_hash: str) -> str:
    record = get_record(record_address)
    return "VERIFIED" if record["content_hash"] == expected_content_hash else "TAMPERED"
