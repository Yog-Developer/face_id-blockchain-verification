import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { FaceVerificationRegistry } from "../target/types/face_verification_registry";
import { assert } from "chai";

describe("face_verification_registry", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.FaceVerificationRegistry as Program<FaceVerificationRegistry>;

  it("stores and reads back a record", async () => {
    const contentHash = "test_hash_123";
    const postUrl = "https://example.com/test";
    const similarityScore = new anchor.BN(913); // scaled x1000, same convention as before

    const [recordPda] = anchor.web3.PublicKey.findProgramAddressSync(
      [
        Buffer.from("record"),
        provider.wallet.publicKey.toBuffer(),
        Buffer.from(contentHash),
      ],
      program.programId
    );

    await program.methods
      .storeRecord(contentHash, postUrl, similarityScore)
      .accounts({
        record: recordPda,
        submitter: provider.wallet.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc();

    const recordAccount = await program.account.record.fetch(recordPda);

    assert.equal(recordAccount.contentHash, contentHash);
    assert.equal(recordAccount.postUrl, postUrl);
    assert.equal(recordAccount.similarityScore.toNumber(), 913);
    console.log("Record stored and verified:", recordAccount);
  });
});
