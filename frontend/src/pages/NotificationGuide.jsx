import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowLeft, Download, Workflow } from 'lucide-react';
import { PageHead, Loading } from '../components/Common';
import './notification-guide.css';

const components = Object.fromEntries(['h1','h2','h3','h4','p','li','pre','code','blockquote'].map(tag => [tag, ({node,children,...props}) => React.createElement(tag, {...props, 'data-testid':`guide-${tag}-${node?.position?.start?.line}`},children)]));
components.table = ({node,children}) => <div className="guide-table-wrap"><table data-testid={`guide-table-${node?.position?.start?.line}`}>{children}</table></div>;
components.a = ({node,href,children}) => <a href={href} data-testid={`guide-link-${node?.position?.start?.line}-${node?.position?.start?.column}`} {...(href?.startsWith('https://') ? {target:'_blank',rel:'noopener noreferrer'} : {})}>{children}</a>;

export default function NotificationGuide() {
  const [content,setContent] = useState(''), [error,setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/panduan-notifikasi.md', {signal:controller.signal}).then(response => {
      if (!response.ok) throw new Error('Panduan tidak tersedia');
      return response.text();
    }).then(setContent).catch(e => { if(e.name!=='AbortError') setError(true); });
    return () => controller.abort();
  },[]);
  return <div className="notification-guide-page" data-testid="notification-guide-page">
    <Link className="back-link" to="/settings" data-testid="guide-back-settings"><ArrowLeft size={14}/>Pengaturan</Link>
    <PageHead eyebrow="PANDUAN KONFIGURASI" title="Email & WhatsApp" description="Gmail via n8n · WhatsApp via n8n + WAHA">
      <a className="guide-download" href="/panduan-notifikasi.md" download data-testid="guide-download-markdown"><Download size={15}/>Unduh panduan</a>
      <a className="guide-download" href="/n8n-waha-workflow.json" download data-testid="guide-download-workflow"><Workflow size={15}/>Workflow WhatsApp</a>
      <a className="guide-download" href="/n8n-gmail-workflow.json" download data-testid="guide-download-gmail-workflow"><Workflow size={15}/>Workflow Email Gmail</a>
    </PageHead>
    {error ? <p role="alert" data-testid="guide-load-error">Panduan belum dapat dimuat. Silakan muat ulang halaman atau unduh panduan di atas.</p> : content ? <article className="notification-guide-content" data-testid="notification-guide-content"><ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{content}</ReactMarkdown></article> : <Loading/>}
  </div>;
}