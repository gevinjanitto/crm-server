import React, { useEffect, useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import ReCAPTCHA from "react-google-recaptcha";
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  UserRound,
  RotateCw,
  ShieldCheck,
  ArrowUpRight,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { useAuth } from "../App";
import { api, errorText } from "../lib/api";
import { sessionMessage } from "../lib/session";
import { BarongMascot } from '../components/BarongMascot';
import { OrbitBackdrop } from '../components/OrbitBackdrop';
import { ContactLink } from '../components/ContactLink';

export default function Login() {
  const { user, completeLogin, loading, logoutReason } = useAuth();
  const [captcha, setCaptcha] = useState(null),
    [visible, setVisible] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [recaptchaToken, setRecaptchaToken] = useState(""),
    [passwordFocus, setPasswordFocus] = useState(false),
    [usernameFocus, setUsernameFocus] = useState(false);
  const recaptchaRef = useRef(null);
  const siteKey = process.env.REACT_APP_RECAPTCHA_SITE_KEY;
  const [form, setForm] = useState({
    username: "",
    password: "",
    captcha_answer: "",
    remember: false,
  });
  const refresh = async () => {
    try {
      const r = await api.get("/auth/captcha");
      setCaptcha(r.data);
      setForm((f) => ({ ...f, captcha_answer: "" }));
      setRecaptchaToken("");
      recaptchaRef.current?.reset();
    } catch (e) {
      setError("CAPTCHA belum dapat dimuat. Silakan coba kembali.");
    }
  };
  useEffect(() => {
    refresh();
  }, []);
  const update = (e) =>
    setForm({
      ...form,
      [e.target.name]:
        e.target.type === "checkbox" ? e.target.checked : e.target.value,
    });
  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const r = await api.post("/auth/login", {
        ...form,
        captcha_id: captcha?.id || "",
        recaptcha_token: recaptchaToken,
      });
      completeLogin(r.data);
    } catch (e) {
      setError(errorText(e));
      refresh();
    } finally {
      setBusy(false);
    }
  };
  const sum = (captcha?.question || "").match(/(\d+)\s*\+\s*(\d+)/);
  const verified = captcha?.provider === "recaptcha"
    ? Boolean(recaptchaToken)
    : Boolean(sum && form.captcha_answer.trim() === String(+sum[1] + +sum[2]));
  if (user && !loading) return <Navigate to="/" replace />;
  return (
    <div
      className="login-page"
      data-testid="login-page"
    >
      <main className="login-stage">
        <section className="login-visual">
          <OrbitBackdrop variant="login-visual" />
          <div className="visual-grid" />
          <div className="login-visual-copy">
            <div className="brand-eyebrow" data-testid="login-eyebrow">
              <span /> MAIHARTA · SOFTWARE HOUSE
            </div>
            <h1 data-testid="login-brand-title">
              Ide besar.
              <br />
              Kolaborasi <em>tanpa batas.</em>
            </h1>
            <p data-testid="login-tagline">
              Satu ruang untuk setiap langkah hebat Anda.
            </p>
          </div>
          <BarongMascot eyesClosed={passwordFocus && !visible} approved={verified} showId={usernameFocus} />
          <div className="visual-bottom" data-testid="login-visual-bottom">
            <span data-testid="login-copyright">
              © {new Date().getFullYear()} CRM Maiharta
            </span>
            <span>
              <i />
              <i />
              <i />
            </span>
          </div>
        </section>
        <section className="login-form-panel">
          <OrbitBackdrop variant="login-form" />
          <div className="form-panel-inner">
            <div className="workspace-mark" data-testid="workspace-mark">
              <img
                src="/assets/logo-mark.webp"
                alt="MaiHarta"
                className="mini-brand"
                data-testid="login-brand-mark"
              />
              <span>
                CRM <b>maiharta</b>
              </span>
              <span className="workspace-pill">WORKSPACE</span>
            </div>
            <div className="login-heading">
              <div
                className="welcome-eyebrow"
                data-testid="login-welcome-label"
              >
                SELAMAT DATANG KEMBALI
              </div>
              <h2 data-testid="login-title">
                Hal hebat dimulai
                <br />
                dari sini<span>.</span>
              </h2>
              <p data-testid="login-description">
                Masuk dan lanjutkan perjalanan project Anda.
              </p>
            </div>
            {sessionMessage(logoutReason) && <div className="login-session-notice" role="status" data-testid="session-ended-notice"><ShieldCheck size={17} /><span>{sessionMessage(logoutReason)}</span></div>}
            <form
              onSubmit={submit}
              className="login-form"
              data-testid="login-form"
            >
              <label className="login-field">
                <span>Username</span>
                <div className="input-with-icon">
                  <UserRound size={18} />
                  <input
                    data-testid="login-username"
                    name="username"
                    autoComplete="username"
                    onFocus={() => setUsernameFocus(true)}
                    onBlur={() => setUsernameFocus(false)}
                    placeholder="Masukkan username Anda"
                    value={form.username}
                    onChange={update}
                    required
                  />
                </div>
              </label>
              <label className="login-field">
                <span>Password</span>
                <div
                  className="input-with-icon"
                  onFocus={() => setPasswordFocus(true)}
                  onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setPasswordFocus(false); }}
                >
                  <LockKeyhole size={18} />
                  <input
                    data-testid="login-password"
                    name="password"
                    type={visible ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Masukkan password Anda"
                    value={form.password}
                    onChange={update}
                    required
                  />
                  <button
                    data-testid="toggle-password"
                    type="button"
                    title={
                      visible ? "Sembunyikan password" : "Tampilkan password"
                    }
                    onClick={() => setVisible(!visible)}
                  >
                    {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </label>
              <div className="captcha-block">
                {captcha?.provider === "recaptcha" ? (
                  <div className="login-field">
                    <span>Verifikasi keamanan</span>
                    <div className="recaptcha-wrap" data-testid="recaptcha-widget">
                      <ReCAPTCHA
                        ref={recaptchaRef}
                        sitekey={captcha.site_key || siteKey}
                        hl="id"
                        onChange={(t) => setRecaptchaToken(t || "")}
                        onExpired={() => setRecaptchaToken("")}
                        onErrored={() =>
                          setError("reCAPTCHA belum dapat dimuat. Muat ulang halaman.")
                        }
                      />
                    </div>
                  </div>
                ) : (
                <label className="login-field">
                  <span>Verifikasi keamanan</span>
                  <div className="captcha-row">
                    <div
                      className="captcha-challenge"
                      data-testid="captcha-question"
                    >
                      {captcha?.question || "..."}
                    </div>
                    <button
                      type="button"
                      data-testid="refresh-captcha"
                      className="captcha-refresh"
                      onClick={refresh}
                      title="Ganti CAPTCHA"
                    >
                      <RotateCw size={17} />
                    </button>
                    <input
                      data-testid="captcha-answer"
                      aria-label="Jawaban CAPTCHA"
                      name="captcha_answer"
                      inputMode="numeric"
                      placeholder="Jawaban"
                      value={form.captcha_answer}
                      onChange={update}
                      required
                    />
                  </div>
                </label>
                )}
              </div>
              <div className="login-options">
                <label>
                  <input
                    type="checkbox"
                    name="remember"
                    checked={form.remember}
                    onChange={update}
                    data-testid="remember-me"
                  />{" "}
                  Ingat saya
                </label>
                <span
                  data-testid="login-help"
                  title="Tulis email bantuan melalui Gmail"
                >
                  Lupa password?{" "}
                  <ContactLink />
                </span>
              </div>
              {error && (
                <p
                  className="login-error"
                  role="alert"
                  data-testid="login-error"
                >
                  {error}
                </p>
              )}
              <Button
                data-testid="login-submit"
                type="submit"
                className="login-submit"
                disabled={
                  busy ||
                  !captcha ||
                  (captcha.provider === "recaptcha" && !recaptchaToken)
                }
              >
                {busy ? "Sedang masuk..." : "Masuk ke workspace"}
                <ArrowRight size={18} />
              </Button>
            </form>
            <div className="login-secure" data-testid="login-security-note">
              <ShieldCheck size={15} /> Ruang kerja aman untuk tim & client
              MaiHarta
            </div>
          </div>
          <div className="panel-bottom" data-testid="login-panel-bottom">
            <span>
              Design dan develop by{" "}
              <a
                href="https://www.maiharta.com"
                target="_blank"
                rel="noreferrer"
                data-testid="login-credit-link"
              >
                MaiHarta <ArrowUpRight size={12} />
              </a>
            </span>
          </div>
        </section>
      </main>
    </div>
  );
}
