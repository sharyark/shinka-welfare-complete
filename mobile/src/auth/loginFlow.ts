/** Values carried between login screens. Kept in memory (not in the URL) so the PIN token never appears in history. */
export const loginFlow: { phone: string; pinToken: string } = { phone: '', pinToken: '' };
