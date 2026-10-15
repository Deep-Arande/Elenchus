import type { Language } from "./proto";

// Harmless, long-debunked example claims (AGENTS.md section 10.1).
export const SAMPLE_CLAIMS: { language: Language; label: string; text: string }[] = [
  {
    language: "en",
    label: "UNESCO anthem (EN)",
    text: "UNESCO declared Jana Gana Mana the best national anthem in the world.",
  },
  {
    language: "en",
    label: "₹2000 GPS chip (EN)",
    text: "The new ₹2000 note has a GPS nano-chip that can be tracked by satellite.",
  },
  {
    language: "hi",
    label: "यूनेस्को राष्ट्रगान (HI)",
    text: "यूनेस्को ने जन गण मन को दुनिया का सर्वश्रेष्ठ राष्ट्रगान घोषित किया।",
  },
  {
    language: "mr",
    label: "₹2000 जीपीएस चिप (MR)",
    text: "नव्या ₹2000 च्या नोटेत उपग्रहाद्वारे ट्रॅक करता येणारी जीपीएस नॅनो-चिप आहे.",
  },
];
