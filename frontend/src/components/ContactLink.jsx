import React from "react";
import { buildContactComposeUrl } from "../lib/contact";

export const ContactLink = () => {
  const email = process.env.REACT_APP_CONTACT_EMAIL;
  const href = buildContactComposeUrl(process.env.REACT_APP_CONTACT_COMPOSE_URL, email);
  if (!href) return (
    <span data-testid="contact-config-unavailable" role="status" title="Konfigurasi email bantuan belum tersedia. Login tetap dapat digunakan.">
      Bantuan email belum tersedia
    </span>
  );
  return (
    <a data-testid="contact-admin" href={href} target="_blank" rel="noopener noreferrer"
      aria-label={`Hubungi kami: tulis email ke ${email.trim()} di Gmail (tab baru)`}>
      Hubungi kami
    </a>
  );
};