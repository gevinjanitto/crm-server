import { buildContactComposeUrl } from "./contact";

describe("buildContactComposeUrl", () => {
  test("returns null for undefined inputs (original crash path)", () => {
    expect(buildContactComposeUrl(undefined, "cvmaiharta@gmail.com")).toBeNull();
    expect(buildContactComposeUrl("https://mail.google.com/mail/", undefined)).toBeNull();
  });

  test("returns null for blank inputs", () => {
    expect(buildContactComposeUrl("", "cvmaiharta@gmail.com")).toBeNull();
    expect(buildContactComposeUrl("https://mail.google.com/mail/", "   ")).toBeNull();
  });

  test("returns null for malformed base URL", () => {
    expect(buildContactComposeUrl("not-a-url", "cvmaiharta@gmail.com")).toBeNull();
  });

  test("returns null for non-https URL", () => {
    expect(buildContactComposeUrl("http://mail.google.com/mail/", "cvmaiharta@gmail.com")).toBeNull();
  });

  test("returns null when URL includes credentials", () => {
    expect(
      buildContactComposeUrl("https://user:pass@mail.google.com/mail/", "cvmaiharta@gmail.com")
    ).toBeNull();
  });

  test("returns null for invalid email", () => {
    expect(buildContactComposeUrl("https://mail.google.com/mail/", "not-an-email")).toBeNull();
  });

  test("builds Gmail compose URL for valid inputs", () => {
    const href = buildContactComposeUrl("https://mail.google.com/mail/", "cvmaiharta@gmail.com");
    expect(href).toBe("https://mail.google.com/mail/?view=cm&fs=1&to=cvmaiharta%40gmail.com");
  });

  test("trims email before composing URL", () => {
    const href = buildContactComposeUrl("https://mail.google.com/mail/", "  cvmaiharta@gmail.com  ");
    expect(href).toContain("to=cvmaiharta%40gmail.com");
  });
});
