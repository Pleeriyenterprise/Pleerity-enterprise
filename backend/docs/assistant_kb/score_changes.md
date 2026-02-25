# Why a compliance score goes up or down

The compliance score can change when the data in the portal changes. Below are typical reasons for **drops** and **increases**. Use the **score_explanation** and **portfolio_summary** in the portal context to give the user a concrete explanation for *their* score change when that data is available.

## Typical reasons for a score **drop**

- **New overdue items**  
  A requirement passed its due or expiry date without valid evidence (e.g. certificate expired, check not renewed). The overdue penalty component reduces the score until the item is resolved.

- **More items expiring soon**  
  Certificates or checks are now within the “expiring soon” window. The expiry timeline component can reduce the score until they are renewed.

- **Fewer compliant requirements**  
  A requirement that was compliant is no longer satisfied—e.g. evidence was removed, or an expiry date passed so the best evidence no longer counts.

- **Document removed or rejected**  
  A document that was supporting a requirement was deleted or is no longer accepted, reducing document coverage and possibly requirement status.

- **New requirement added**  
  A new requirement (e.g. for a new property or regulation) starts as not satisfied, which can lower the property or portfolio score until evidence is provided.

## Typical reasons for a score **increase**

- **Overdue items resolved**  
  Valid evidence was added for previously overdue requirements (e.g. new certificate uploaded, check completed). The overdue penalty decreases and the status/expiry components can improve.

- **Documents uploaded and verified**  
  New or replacement documents were uploaded and (where applicable) verified, improving document coverage and requirement status.

- **Certificates renewed**  
  Expiring or expired items were renewed (new expiry date in the future), improving the expiry timeline and often the requirement status.

- **Fewer items expiring soon**  
  Items that were “expiring soon” were renewed or removed from scope, so the expiry component no longer penalises them.

When the user asks “why did my score drop?” or “why did my score go up?”, use the **score_explanation** trend sentence (e.g. “Compared to 7 days ago: …”) and the **by_property** key reasons to give a short, accurate answer. If no trend data is available, use the per-property key reasons and the counts in **portfolio_summary** (overdue_requirements_count, expiring_soon_count, compliant_count) to explain in plain language.
