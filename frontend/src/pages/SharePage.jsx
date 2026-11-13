import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Download, Eye, FileText, Image as ImageIcon, FileSpreadsheet, Clock3, ShieldCheck, UserRound, Lock, ArrowUpRight, Link2, Globe, KeyRound, Infinity as InfinityIcon } from "lucide-react";
import { api, errorText } from "../lib/api";
import { BarongMascot } from "../components/BarongMascot";
import { OrbitBackdrop } from "../components/OrbitBackdrop";
import { PdfPages, needsPdfCanvas } from "../components/PdfPages";
import { expiryLabel } from "../components/ShareDialog";
import "../components/share.css";

const BASE = `${process.env.REACT_APP_BACKEND_URL}/api/public/shares`;
const PORTAL_URL = "https://portal.maiharta.com/";
const ease = [0.22, 1, 0.36, 1];
const rise = (i) => ({ initial: { opacity: 0, y: 26, filter: "blur(6px)" }, animate: { opacity: 1, y: 0, filter: "blur(0px)" }, transition: { duration: 0.7, delay: 0.25 + i * 0.09, ease } });
const sizeLabel = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} byte`);
const kindOf = (t = "") => (t.startsWith("image/") ? "image" : t === "application/pdf" ? "pdf" : t.startsWith("text/") ? "text" : "other");
const FileIcon = ({ type = "" }) => { const k = kindOf(type); return k === "image" ? <ImageIcon size={26} /> : type.includes("sheet") || type.includes("csv") ? <FileSpreadsheet size={26} /> : <FileText size={26} />; };
const FX = { download: "cloud", tab: "window" };

function useCountdown(target) {
  const [nowTs, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const left = Math.max(0, new Date(target || 0).getTime() - nowTs);
  return { left, parts: [Math.floor(left / 864e5), Math.floor(left / 36e5) % 24, Math.floor(left / 6e4) % 60, Math.floor(left / 1e3) % 60] };
}

// Flips once at expiry instead of re-rendering the whole page every second (the per-second tick lives in Countdown).
function useExpired(target) {
  const ms = () => new Date(target || 0).getTime() - Date.now();
  const [left, setLeft] = useState(() => (target ? Math.max(0, ms()) : 1));
  useEffect(() => {
    if (!target) return;
    const t0 = ms(); setLeft(Math.max(0, t0));
    if (t0 <= 0) return;
    const t = setTimeout(() => setLeft(0), Math.min(t0, 2147483000));
    return () => clearTimeout(t);
  }, [target]); // eslint-disable-line react-hooks/exhaustive-deps
  return { left };
}

// Hover shows a button's barong animation; a click/tap pins it briefly so touch users see it too.
function useBarongAct() {
  const [hover, setHover] = useState(null), [pin, setPin] = useState(null), timer = useRef();
  useEffect(() => () => clearTimeout(timer.current), []);
  const fire = (k, ms = 2200) => { clearTimeout(timer.current); setPin(k); timer.current = setTimeout(() => setPin(null), ms); };
  const bind = (k) => ({ onPointerEnter: (e) => e.pointerType !== "touch" && setHover(k), onPointerLeave: () => setHover(null), onFocus: (e) => e.target.matches?.(":focus-visible") && setHover(k), onBlur: () => setHover(null), "data-fx": k });
  return { act: hover || pin, fire, bind };
}

const Countdown = ({ expires }) => {
  const { parts } = useCountdown(expires);
  return <div className="share-countdown" data-testid="share-countdown">
    {["Hari", "Jam", "Menit", "Detik"].map((l, i) => <div key={l}><motion.b key={parts[i]} initial={{ y: -6 }} animate={{ y: 0 }} transition={{ duration: 0.25 }}>{String(parts[i]).padStart(2, "0")}</motion.b><span>{l}</span></div>)}
  </div>;
};

const Preview = ({ src, info }) => {
  const k = kindOf(info.content_type);
  const [text, setText] = useState("");
  useEffect(() => { if (k === "text") fetch(src).then((r) => r.text()).then((t) => setText(t.slice(0, 20000))).catch(() => setText("Pratinjau tidak dapat dimuat.")); }, [k, src]);
  if (k === "image") return <img className="share-preview-img" src={src} alt={info.name} data-testid="share-preview-image" />;
  if (k === "pdf") return needsPdfCanvas()
    ? <PdfPages src={src} testid="share-preview-pdf" fallback={<a href={src} target="_blank" rel="noopener noreferrer">Buka di tab baru</a>} />
    : <iframe className="share-preview-frame" src={src} title={info.name} data-testid="share-preview-pdf" />;
  if (k === "text") return <pre className="share-preview-text" data-testid="share-preview-text">{text}</pre>;
  return <div className="share-preview-none" data-testid="share-preview-none"><FileIcon type={info.content_type} /><p>Pratinjau tidak tersedia untuk jenis file ini. Buka atau unduh untuk melihat isinya.</p></div>;
};

const PortalButton = ({ bind, fire }) => (
  <a className="share-portal" href={PORTAL_URL} target="_blank" rel="noopener noreferrer" data-testid="share-portal-button" {...bind("portal")} onClick={() => fire("portal", 1600)}>
    <img src="/assets/barong-thumb.webp" alt="" aria-hidden="true" /> <span>Portal MaiHarta</span> <ArrowUpRight size={15} />
  </a>
);

const fileUrl = (token, key, id, download) => {
  const p = new URLSearchParams();
  if (id) p.set("doc", id);
  if (key) p.set("k", key);
  if (download) p.set("download", "true");
  const s = p.toString();
  return `${BASE}/${token}/file${s ? `?${s}` : ""}`;
};

const FileActions = ({ url, info, showPreview, setShowPreview, bind, fire, sfx = "" }) => <>
  <button type="button" className="share-btn ghost" data-testid={`share-view-button${sfx}`} {...bind("view")} onClick={() => { setShowPreview((v) => !v); fire("view", 1400); }}><Eye size={17} /> {showPreview ? "Tutup pratinjau" : "Lihat file"}</button>
  {info.allow_download && <a className="share-btn ghost" href={url(false)} target="_blank" rel="noopener noreferrer" data-testid={`share-open-tab${sfx}`} {...bind("tab")} onClick={() => fire("tab")}><ArrowUpRight size={17} /> Buka di tab baru</a>}
  {info.allow_download
    ? <a className="share-btn primary" href={url(true)} data-testid={`share-download-button${sfx}`} {...bind("download")} onClick={() => fire("download", 2600)}><Download size={17} /> Download</a>
    : <span className="share-view-only" data-testid={`share-view-only${sfx}`}><Lock size={14} /> Pengirim hanya mengizinkan melihat</span>}
</>;

const PasswordGate = ({ token, onUnlock }) => {
  const [pw, setPw] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { const r = await api.post(`/public/shares/${token}/unlock`, { password: pw }); sessionStorage.setItem(`share-key-${token}`, r.data.key); onUnlock(r.data.key); }
    catch (x) { setErr(errorText(x)); } finally { setBusy(false); }
  };
  return <motion.form className="share-card share-lock" {...rise(2)} onSubmit={submit} data-testid="share-password-form">
    <div className="share-file-icon"><KeyRound size={26} /></div>
    <div className="share-file-meta share-lock-body">
      <h3>Link ini dilindungi password</h3>
      <p>Masukkan password dari pengirim untuk membuka dokumen.</p>
      <div className="share-lock-row">
        <input type="password" autoFocus value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Password" data-testid="share-password-field" />
        <button type="submit" className="share-btn primary" disabled={busy || !pw} data-testid="share-password-submit">{busy ? "Memeriksa..." : "Buka"}</button>
      </div>
      {err && <p className="share-lock-error" data-testid="share-password-error">{err}</p>}
    </div>
  </motion.form>;
};

const BundleList = ({ token, info, k, bind, fire, active, setActive }) => (
  <motion.div className="share-bundle" {...rise(2)} data-testid="share-bundle-list">
    <p className="share-by"><UserRound size={13} /> Dibagikan oleh <b data-testid="share-shared-by">{info.shared_by}</b> · {info.files.length} dokumen</p>
    {info.files.map((f) => <div className={`share-card share-bundle-item ${active === f.id ? "is-active" : ""}`} key={f.id} data-testid={`share-bundle-item-${f.id}`}>
      <div className="share-file-icon">{f.document_type === "link" ? <Link2 size={22} /> : <FileIcon type={f.content_type} />}</div>
      <div className="share-file-meta">
        <h3 data-testid={`share-bundle-name-${f.id}`}>{f.name}</h3>
        <p>{f.kind} · {f.document_type === "link" ? "Link" : `${sizeLabel(f.size)} · ${f.filename.split(".").pop().toUpperCase()}`}</p>
      </div>
      <div className="share-bundle-actions">
        {f.document_type === "link"
          ? <a className="share-btn ghost sm" href={f.url} target="_blank" rel="noopener noreferrer" data-testid={`share-bundle-open-${f.id}`}><ArrowUpRight size={15} /> Buka</a>
          : <>
            <button type="button" className="share-btn ghost sm" data-testid={`share-bundle-view-${f.id}`} {...bind("view")} onClick={() => { setActive(active === f.id ? null : f.id); fire("view", 1400); }}><Eye size={15} /> {active === f.id ? "Tutup" : "Lihat"}</button>
            {info.allow_download && <a className="share-btn primary sm" href={fileUrl(token, k, f.id, true)} aria-label={`Download ${f.name}`} title="Download" data-testid={`share-bundle-download-${f.id}`} {...bind("download")} onClick={() => fire("download", 2600)}><Download size={15} /></a>}
          </>}
      </div>
      {active === f.id && <div className="share-preview share-bundle-preview" data-testid={`share-bundle-preview-${f.id}`}><Preview src={fileUrl(token, k, f.id, false)} info={f} /></div>}
    </div>)}
    {!info.allow_download && <span className="share-view-only" data-testid="share-view-only"><Lock size={14} /> Pengirim hanya mengizinkan melihat</span>}
  </motion.div>
);

const LinkCard = ({ info, bind }) => (
  <motion.div className="share-card share-link-card" {...rise(2)} data-testid="share-link-card" {...bind("view")}>
    <div className="share-file-icon"><Link2 size={26} /></div>
    <div className="share-file-meta">
      <h3 data-testid="share-file-name">{info.name}</h3>
      <p>{info.kind} · Dokumen berupa link</p>
      <a className="share-link-url" href={info.url} target="_blank" rel="noopener noreferrer" data-testid="share-link-url"><Globe size={13} /> {info.url}</a>
      <p className="share-by"><UserRound size={13} /> Dibagikan oleh <b data-testid="share-shared-by">{info.shared_by}</b></p>
    </div>
  </motion.div>
);

export default function SharePage() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [error, setError] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [hoverCard, setHoverCard] = useState(false);
  const [mascotVisible, setMascotVisible] = useState(true);
  const [k, setK] = useState(() => sessionStorage.getItem(`share-key-${token}`) || "");
  const [locked, setLocked] = useState(false);
  const [active, setActive] = useState(null);
  const mascotRef = useRef(null);
  const { act, fire, bind } = useBarongAct();
  useEffect(() => {
    document.title = "File dibagikan · CRM Maiharta";
    api.get(`/public/shares/${token}`, { params: k ? { k } : {} }).then((r) => { setInfo(r.data); setLocked(false); setError(null); })
      .catch((e) => { if (e.response?.status === 401) { sessionStorage.removeItem(`share-key-${token}`); setLocked(true); } else setError({ status: e.response?.status, text: errorText(e) }); });
  }, [token, k]);
  useEffect(() => {
    if (!mascotRef.current || !window.IntersectionObserver) return;
    const io = new IntersectionObserver(([e]) => setMascotVisible(e.isIntersecting), { threshold: 0.3 });
    io.observe(mascotRef.current);
    return () => io.disconnect();
  }, []);
  const { left } = useExpired(info?.expires_at);
  const expired = !!error || (info && left <= 0);
  const bundle = (info?.files || []).length > 1;
  const isLink = !bundle && info?.document_type === "link";
  const sparks = useMemo(() => Array.from({ length: 18 }, (_, i) => ({ i, x: Math.random() * 100, d: 6 + Math.random() * 8, delay: Math.random() * 6, s: 2 + Math.random() * 4 })), []);
  const mascot = { eyesClosed: expired && act !== "portal", approved: act === "download" && !expired, showId: hoverCard && !act && !expired,
    glasses: !expired && (act === "view" || (showPreview && !act)), effect: expired ? null : FX[act], shake: act === "portal" };
  return (
    <div className={`share-page ${(showPreview && !isLink && !bundle) || active ? "is-previewing" : ""}`} data-testid="share-page">
      <OrbitBackdrop variant="login-visual" />
      <div className="share-grid-bg" aria-hidden="true" />
      <div className="share-sparks" aria-hidden="true">{sparks.map((p) => <i key={p.i} style={{ left: `${p.x}%`, width: p.s, height: p.s, animationDuration: `${p.d}s`, animationDelay: `${p.delay}s` }} />)}</div>
      <motion.header className="share-top" initial={{ opacity: 0, y: -18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }}>
        <div className="share-brand" data-testid="share-app-name">
          <img src="/assets/logo-mark-white.png" alt="MaiHarta" />
          <span>CRM <b>maiharta</b></span>
        </div>
        <div className="share-top-right">
          <span className="share-secure"><ShieldCheck size={14} /> Tautan berbagi aman</span>
          <PortalButton bind={bind} fire={fire} />
        </div>
      </motion.header>
      <main className="share-main">
        <motion.section ref={mascotRef} className="share-mascot" initial={{ opacity: 0, scale: 0.9, x: -30 }} animate={{ opacity: 1, scale: 1, x: 0 }} transition={{ duration: 0.9, ease }}>
          <div className="share-halo" aria-hidden="true" />
          <BarongMascot {...mascot} />
        </motion.section>
        <section className="share-panel">
          <motion.div className="brand-eyebrow share-eyebrow" {...rise(0)}><span /> MAIHARTA · FILE SHARING</motion.div>
          <motion.h1 {...rise(1)} data-testid="share-heading">{expired ? <>Link ini sudah <em>tidak aktif.</em></> : locked ? <>Dokumen ini <em>dilindungi password.</em></> : bundle ? <>Seseorang berbagi <em>{info.files.length} dokumen untuk Anda.</em></> : isLink ? <>Seseorang berbagi <em>dokumen untuk Anda.</em></> : <>Seseorang berbagi <em>file untuk Anda.</em></>}</motion.h1>
          {locked && !error && <PasswordGate token={token} onUnlock={setK} />}
          {!info && !error && !locked && <motion.div className="share-card share-skeleton" {...rise(2)} data-testid="share-loading"><span /><span /><span /></motion.div>}
          {error && <motion.div className="share-card share-dead" {...rise(2)} data-testid="share-error">
            <Lock size={28} /><div><h3>{error.status === 410 ? "Link kedaluwarsa" : "Link tidak tersedia"}</h3><p>{error.text}</p><p>Minta pengirim membuat link baru melalui CRM Maiharta.</p></div>
          </motion.div>}
          {info && <>
            {bundle ? (left > 0 && <BundleList token={token} info={info} k={k} bind={bind} fire={fire} active={active} setActive={setActive} />) : isLink ? <LinkCard info={info} bind={bind} /> : <motion.div className="share-card" {...rise(2)} data-testid="share-file-card" onMouseEnter={() => setHoverCard(true)} onMouseLeave={() => setHoverCard(false)}>
              <div className="share-file-icon"><FileIcon type={info.content_type} /></div>
              <div className="share-file-meta">
                <h3 data-testid="share-file-name">{info.name}</h3>
                <p>{info.kind} · {sizeLabel(info.size)} · {info.filename.split(".").pop().toUpperCase()}</p>
                <p className="share-by"><UserRound size={13} /> Dibagikan oleh <b data-testid="share-shared-by">{info.shared_by}</b></p>
              </div>
            </motion.div>}
            <motion.div className="share-expiry" {...rise(3)}>
              {info.expires_at
                ? <span data-testid="share-expiry-text"><Clock3 size={14} /> {left > 0 ? `Berlaku hingga ${expiryLabel(info.expires_at)}` : "Masa berlaku telah habis"}</span>
                : <span data-testid="share-expiry-text"><InfinityIcon size={14} /> Link berlaku tanpa batas waktu</span>}
              {left > 0 && info.expires_at && <Countdown expires={info.expires_at} />}
            </motion.div>
            {left > 0 && !bundle && <motion.div className="share-actions" {...rise(4)}>
              {isLink
                ? <a className="share-btn primary" href={info.url} target="_blank" rel="noopener noreferrer" data-testid="share-open-link" {...bind("tab")} onClick={() => fire("tab")}><ArrowUpRight size={17} /> Buka dokumen</a>
                : <FileActions url={(dl) => fileUrl(token, k, "", dl)} info={info} showPreview={showPreview} setShowPreview={setShowPreview} bind={bind} fire={fire} />}
            </motion.div>}
            {!isLink && !bundle && showPreview && left > 0 && <motion.div className="share-preview" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} transition={{ duration: 0.45, ease }} data-testid="share-preview">
              <Preview src={fileUrl(token, k, "", false)} info={info} />
            </motion.div>}
          </>}
          <motion.footer className="share-foot" {...rise(5)}>© {new Date().getFullYear()} CRM Maiharta · Design dan develop by <a href="https://www.maiharta.com" target="_blank" rel="noreferrer">MaiHarta</a></motion.footer>
        </section>
      </main>
      <AnimatePresence>
        {act && act !== "view" && !showPreview && !mascotVisible && !expired && <motion.div key="mini" className="share-mini" data-testid="share-mini-barong" aria-hidden="true"
          initial={{ opacity: 0, y: 50, scale: 0.6 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 50, scale: 0.6 }} transition={{ type: "spring", stiffness: 260, damping: 20 }}>
          <BarongMascot {...mascot} />
        </motion.div>}
      </AnimatePresence>
    </div>
  );
}
