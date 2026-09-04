use anchor_lang::prelude::*;

declare_id!("2yzcW6ix3X3AJ16ypF1XUVs9PNb6v1gtRjLqe2CbBhmZ");

#[program]
pub mod face_verification_registry {
    use super::*;

    pub fn store_record(
        ctx: Context<StoreRecord>,
        content_hash: String,
        post_url: String,
        similarity_score: u64,
    ) -> Result<()> {
        let record = &mut ctx.accounts.record;
        record.content_hash = content_hash;
        record.post_url = post_url;
        record.similarity_score = similarity_score;
        record.timestamp = Clock::get()?.unix_timestamp;
        record.submitter = ctx.accounts.submitter.key();
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(content_hash: String, post_url: String)]
pub struct StoreRecord<'info> {
    #[account(
        init,
        payer = submitter,
        space = 8 + 4 + 128 + 4 + 256 + 8 + 8 + 32,
        seeds = [b"record", submitter.key().as_ref(), content_hash.as_bytes()],
        bump
    )]
    pub record: Account<'info, Record>,
    #[account(mut)]
    pub submitter: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct Record {
    pub content_hash: String,
    pub post_url: String,
    pub similarity_score: u64,
    pub timestamp: i64,
    pub submitter: Pubkey,
}
