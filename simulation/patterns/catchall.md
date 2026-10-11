# Pattern: catchall / noise (~20–25% of volume)

Classes observed, all low-state:

- **Marketing blasts** (pet-store chains, pet brands): emoji-heavy subjects,
  promo body, unsubscribe footers, zero-width junk characters. Machine
  texture; deterministic templates, no LLM needed.
- **Drive/doc share notifications**: no-reply sender, "Document shared with
  you" subject, boilerplate body with a link and abuse-report footer.
- **Form-processor artifacts**: the application dumps (see application.md)
  are themselves machine mail.
- **Volunteer offers**: short self-introductions ("happy to help with
  transport on weekends"), sometimes with constraints; get a warm ack and a
  "we'll reach out" close.
- **Vague interest / one-liners**: "do you have any small dogs right now?"
  with no prior context; answered briefly with a pointer to the site/events.
- **Donation receipts and thank-yous**: processor-generated receipts;
  occasional personal thank-you exchanges.
- **Lost-dog / found-dog inquiries**: misdirected to a rescue; politely
  redirected to animal control / lost-pet groups.
- **Provider footers**: webmail ad footers, corporate auto-footers riding
  otherwise-normal mail.

Purpose in the universe: realistic noise floor for the table-builder to
route around; a handful (vague interest, volunteer offers) carry weak state
worth a catchall bucket rather than a table row.
