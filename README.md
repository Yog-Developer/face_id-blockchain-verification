## Blockchain Details

**Network:** Solana Devnet
**Program ID:** `2yzcW6ix3X3AJ16ypF1XUVs9PNb6v1gtRjLqe2CbBhmZ`
**Explorer:** https://explorer.solana.com/address/2yzcW6ix3X3AJ16ypF1XUVs9PNb6v1gtRjLqe2CbBhmZ?cluster=devnet

The verification pipeline works as follows:
1. A face match's metadata (content hash, source URL, similarity score) is canonicalized and hashed with SHA-256.
2. `store_record()` writes this data to a Solana program account, derived as a PDA (Program Derived Address) from the submitter's wallet and the content hash — each record lives at its own unique on-chain address rather than an incrementing ID.
3. `get_record()` reads the account back from-chain.
4. `verify_on_chain()` recomputes the hash and compares it against the on-chain value, returning `VERIFIED` or `TAMPERED`.

### Why Solana (not Ethereum/Polygon)
The project initially targeted Polygon Amoy testnet but switched to Solana devnet after repeated funding friction — several Polygon faucets required a pre-existing Ethereum mainnet balance as an anti-abuse measure, which a fresh development wallet couldn't clear. Solana's devnet faucets have no such requirement, making it a more practical fit for a time-constrained hackathon build.

### Known limitations
- Uses Solana devnet, not mainnet — tokens and program state have no real value and may be reset by the network at any time.
- Deployed via a personal free-tier RPC provider (Helius); a production version would use a dedicated/paid endpoint for reliability.
